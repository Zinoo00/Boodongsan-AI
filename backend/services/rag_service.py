"""
RAG (Retrieval Augmented Generation) Service for Korean Real Estate AI Chatbot
Orchestrates vector search, AI response generation, and context management
"""

import logging
import time
import asyncio
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime
import json
from functools import wraps

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from pydantic import BaseModel, Field, validator

from ..core.config import settings
from ..core.exceptions import (
    RAGServiceError, AIServiceError, VectorServiceError, ValidationError, 
    ErrorCode, safe_execute
)
from ..core.database import cache_manager
from ..models.property import PropertyFilter, PropertySearchResult
from ..models.user import UserProfile, ConversationHistory
from ..models.policy import PolicyRecommendation
from .vector_service import VectorService
from .ai_service import AIService
from .property_service import PropertyService
from .policy_service import PolicyService
from .user_service import UserService

logger = logging.getLogger(__name__)

# RAG processing configuration
RAG_RETRY_ATTEMPTS = 3
RAG_RETRY_WAIT_MIN = 1
RAG_RETRY_WAIT_MAX = 5
RAG_CACHE_TTL = 1800  # 30 minutes
RAG_MAX_PROCESSING_TIME = 30  # 30 seconds

# Performance metrics
class RAGMetrics:
    """RAG service performance metrics"""
    def __init__(self):
        self.total_queries = 0
        self.successful_queries = 0
        self.failed_queries = 0
        self.avg_processing_time = 0.0
        self.cache_hits = 0
        self.cache_misses = 0
    
    def record_query(self, success: bool, processing_time: float, cache_hit: bool = False):
        self.total_queries += 1
        if success:
            self.successful_queries += 1
        else:
            self.failed_queries += 1
        
        # Update rolling average
        self.avg_processing_time = (
            (self.avg_processing_time * (self.total_queries - 1) + processing_time) / 
            self.total_queries
        )
        
        if cache_hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_queries": self.total_queries,
            "success_rate": self.successful_queries / max(self.total_queries, 1),
            "avg_processing_time_ms": self.avg_processing_time,
            "cache_hit_rate": self.cache_hits / max(self.total_queries, 1)
        }

# Global metrics instance
rag_metrics = RAGMetrics()


class QueryValidation(BaseModel):
    """Input validation for RAG queries"""
    user_query: str = Field(..., min_length=1, max_length=2000, description="User query text")
    user_id: str = Field(..., min_length=1, max_length=100, description="User identifier")
    conversation_id: str = Field(..., min_length=1, max_length=100, description="Conversation identifier")
    session_context: Optional[Dict[str, Any]] = Field(default=None, description="Session context")
    
    @validator('user_query')
    def validate_query(cls, v):
        if not v or v.isspace():
            raise ValueError("Query cannot be empty or whitespace")
        return v.strip()
    
    @validator('user_id', 'conversation_id')
    def validate_ids(cls, v):
        if not v or not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError("ID must contain only alphanumeric characters, hyphens, and underscores")
        return v

class RAGContext:
    """Enhanced RAG context container with validation and caching"""
    
    def __init__(self):
        self.user_query: str = ""
        self.user_id: Optional[str] = None
        self.conversation_id: Optional[str] = None
        self.user_profile: Optional[UserProfile] = None
        self.conversation_history: List[ConversationHistory] = []
        self.extracted_entities: Dict[str, Any] = {}
        self.intent: str = "GENERAL_CHAT"
        self.relevant_properties: List[PropertySearchResult] = []
        self.relevant_policies: List[PolicyRecommendation] = []
        self.market_context: Dict[str, Any] = {}
        self.search_metadata: Dict[str, Any] = {}
        self.processing_metrics: Dict[str, float] = {}
        self.cache_keys: List[str] = []
        self.correlation_id: Optional[str] = None
    
    def add_timing(self, stage: str, duration_ms: float):
        """Add timing information for a processing stage"""
        self.processing_metrics[f"{stage}_duration_ms"] = duration_ms
    
    def get_cache_key(self, prefix: str, *args) -> str:
        """Generate cache key for RAG operations"""
        key_parts = [prefix, self.user_query[:50]]  # Limit query length in key
        key_parts.extend(str(arg) for arg in args if arg is not None)
        cache_key = ":".join(key_parts).replace(" ", "_")
        self.cache_keys.append(cache_key)
        return cache_key


class RAGService:
    """RAG service for Korean Real Estate chatbot"""
    
    def __init__(
        self,
        vector_service: VectorService,
        ai_service: AIService,
        property_service: PropertyService,
        policy_service: PolicyService,
        user_service: UserService
    ):
        self.vector_service = vector_service
        self.ai_service = ai_service
        self.property_service = property_service
        self.policy_service = policy_service
        self.user_service = user_service
        
        # RAG configuration
        self.max_context_length = settings.MAX_CONTEXT_LENGTH
        self.similarity_threshold = settings.SIMILARITY_THRESHOLD
        self.max_search_results = settings.MAX_SEARCH_RESULTS
    
    async def process_query(
        self,
        user_query: str,
        user_id: str,
        conversation_id: str,
        session_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process user query through RAG pipeline
        
        Args:
            user_query: User's natural language query
            user_id: User identifier
            conversation_id: Conversation identifier
            session_context: Additional session context
            
        Returns:
            Complete RAG response with properties, policies, and generated text
        """
        start_time = datetime.utcnow()
        
        try:
            # Generate correlation ID for request tracking
            correlation_id = f"rag_{int(time.time() * 1000)}"
            
            # Initialize RAG context
            context = RAGContext()
            context.user_query = user_query
            context.user_id = user_id
            context.conversation_id = conversation_id
            context.correlation_id = correlation_id
            
            # Step 1: Load user profile and conversation history
            await self._load_user_context(context, user_id, conversation_id)
            
            # Step 2: Extract entities and classify intent
            await self._extract_entities_and_intent(context)
            
            # Step 3: Perform vector search for relevant content
            await self._perform_vector_search(context)
            
            # Step 4: Retrieve relevant properties
            await self._retrieve_relevant_properties(context)
            
            # Step 5: Match government policies
            await self._match_government_policies(context)
            
            # Step 6: Gather market context
            await self._gather_market_context(context)
            
            # Step 7: Generate AI response
            ai_response = await self._generate_ai_response(context)
            
            # Step 8: Save conversation history
            await self._save_conversation_history(
                context, user_id, conversation_id, ai_response
            )
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Compile final response
            response = {
                "response": ai_response["text"],
                "intent": context.intent,
                "entities": context.extracted_entities,
                "properties": [
                    {
                        "id": str(prop.property.id),
                        "address": prop.property.address,
                        "price": prop.property.price,
                        "property_type": prop.property.property_type,
                        "transaction_type": prop.property.transaction_type,
                        "area_m2": prop.property.area_m2,
                        "area_pyeong": prop.property.area_pyeong,
                        "relevance_score": prop.relevance_score,
                        "matching_criteria": prop.matching_criteria
                    }
                    for prop in context.relevant_properties[:5]  # Top 5 properties
                ],
                "policies": [
                    {
                        "id": str(policy.policy.id),
                        "policy_name": policy.policy.policy_name,
                        "policy_type": policy.policy.policy_type,
                        "organizing_institution": policy.policy.organizing_institution,
                        "match_score": policy.match_score,
                        "eligibility_status": policy.eligibility_status,
                        "recommendation_reason": policy.recommendation_reason,
                        "next_steps": policy.next_steps
                    }
                    for policy in context.relevant_policies[:3]  # Top 3 policies
                ],
                "market_insights": context.market_context,
                "confidence_score": ai_response.get("confidence_score", 0.0),
                "processing_time_ms": int(processing_time),
                "search_metadata": context.search_metadata
            }
            
            logger.info(f"RAG query processed successfully in {processing_time:.0f}ms")
            return response
            
        except Exception as e:
            logger.error(f"RAG query processing failed: {str(e)}")
            # Return fallback response
            return {
                "response": "죄송합니다. 요청을 처리하는 중 오류가 발생했습니다. 다시 시도해 주세요.",
                "intent": "ERROR",
                "entities": {},
                "properties": [],
                "policies": [],
                "market_insights": {},
                "confidence_score": 0.0,
                "processing_time_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                "error": str(e)
            }
    
    async def _load_user_context(
        self, 
        context: RAGContext, 
        user_id: str, 
        conversation_id: str
    ):
        """Load user profile and conversation history"""
        try:
            # Load user profile
            context.user_profile = await self.user_service.get_primary_profile(user_id)
            
            # Load recent conversation history (last 10 messages)
            context.conversation_history = await self.user_service.get_conversation_history(
                user_id, conversation_id, limit=10
            )
            
        except Exception as e:
            logger.warning(f"Failed to load user context: {str(e)}")
    
    async def _extract_entities_and_intent(self, context: RAGContext):
        """Extract entities and classify intent using AI service"""
        try:
            # Extract entities
            context.extracted_entities = await self.ai_service.extract_entities(
                context.user_query
            )
            
            # Classify intent
            context.intent = await self.ai_service.classify_intent(
                context.user_query
            )
            
        except Exception as e:
            logger.error(f"Entity extraction/intent classification failed: {str(e)}")
            context.intent = "GENERAL_CHAT"
            context.extracted_entities = {}
    
    async def _perform_vector_search(self, context: RAGContext):
        """Perform vector search for relevant content"""
        try:
            # Generate query embedding
            query_embedding = await self.vector_service.generate_embedding(
                context.user_query,
                correlation_id=context.correlation_id
            )
            
            # Search for similar content
            search_results = await self.vector_service.hybrid_search(
                query_embedding=query_embedding,
                query_text=context.user_query,
                limit=self.max_search_results,
                threshold=self.similarity_threshold,
                filters=self._build_search_filters(context),
                correlation_id=context.correlation_id
            )
            
            context.search_metadata = {
                "total_results": len(search_results),
                "avg_similarity": sum(r.score for r in search_results) / len(search_results) if search_results else 0,
                "search_filters_applied": bool(context.extracted_entities)
            }
            
        except Exception as e:
            logger.error(f"Vector search failed: {str(e)}")
            context.search_metadata = {"error": str(e)}
    
    async def _retrieve_relevant_properties(self, context: RAGContext):
        """Retrieve relevant properties based on search results and entities"""
        try:
            # Build property filter from entities and user profile
            property_filter = self._build_property_filter(context)
            
            # Search properties
            properties = await self.property_service.search_properties(
                filter=property_filter,
                limit=self.max_search_results
            )
            
            # Convert to PropertySearchResult with relevance scoring
            context.relevant_properties = []
            for prop in properties:
                relevance_score = self._calculate_property_relevance(prop, context)
                matching_criteria = self._identify_matching_criteria(prop, context)
                
                search_result = PropertySearchResult(
                    property=prop,
                    relevance_score=relevance_score,
                    matching_criteria=matching_criteria
                )
                context.relevant_properties.append(search_result)
            
            # Sort by relevance score
            context.relevant_properties.sort(
                key=lambda x: x.relevance_score, reverse=True
            )
            
        except Exception as e:
            logger.error(f"Property retrieval failed: {str(e)}")
            context.relevant_properties = []
    
    async def _match_government_policies(self, context: RAGContext):
        """Match relevant government policies"""
        try:
            if context.user_profile:
                # Get policy recommendations for user
                context.relevant_policies = await self.policy_service.get_policy_recommendations(
                    user_profile=context.user_profile,
                    query_context=context.extracted_entities,
                    limit=5
                )
            else:
                # General policy search
                context.relevant_policies = await self.policy_service.search_policies_by_query(
                    query=context.user_query,
                    limit=3
                )
                
        except Exception as e:
            logger.error(f"Policy matching failed: {str(e)}")
            context.relevant_policies = []
    
    async def _gather_market_context(self, context: RAGContext):
        """Gather market context and insights"""
        try:
            market_data = {}
            
            # Get area-specific market data if location entities exist
            if "region" in context.extracted_entities:
                region = context.extracted_entities["region"]
                market_data = await self.property_service.get_market_insights(region)
            
            # Add property type insights
            if "property_type" in context.extracted_entities:
                property_type = context.extracted_entities["property_type"]
                type_insights = await self.property_service.get_property_type_insights(
                    property_type
                )
                market_data.update(type_insights)
            
            context.market_context = market_data
            
        except Exception as e:
            logger.error(f"Market context gathering failed: {str(e)}")
            context.market_context = {}
    
    async def _generate_ai_response(self, context: RAGContext) -> Dict[str, Any]:
        """Generate AI response using all gathered context"""
        try:
            # Prepare context for AI model
            ai_context = {
                "user_query": context.user_query,
                "intent": context.intent,
                "entities": context.extracted_entities,
                "user_profile": context.user_profile.dict() if context.user_profile else None,
                "properties": [prop.dict() for prop in context.relevant_properties[:5]],
                "policies": [policy.dict() for policy in context.relevant_policies[:3]],
                "market_context": context.market_context,
                "conversation_history": [
                    {"role": conv.role, "content": conv.content}
                    for conv in context.conversation_history[-5:]  # Last 5 messages
                ]
            }
            
            # Generate response
            response = await self.ai_service.generate_rag_response(
                context=ai_context,
                max_tokens=settings.RESPONSE_MAX_TOKENS
            )
            
            return response
            
        except Exception as e:
            logger.error(f"AI response generation failed: {str(e)}")
            return {
                "text": "죄송합니다. 응답을 생성하는 중 오류가 발생했습니다.",
                "confidence_score": 0.0
            }
    
    async def _save_conversation_history(
        self,
        context: RAGContext,
        user_id: str,
        conversation_id: str,
        ai_response: Dict[str, Any]
    ):
        """Save conversation history"""
        try:
            # Save user message
            await self.user_service.save_conversation_message(
                user_id=user_id,
                conversation_id=conversation_id,
                role="user",
                content=context.user_query,
                intent=context.intent,
                entities=context.extracted_entities,
                search_results=[str(prop.property.id) for prop in context.relevant_properties[:5]],
                recommended_policies=[str(policy.policy.id) for policy in context.relevant_policies[:3]]
            )
            
            # Save assistant response
            await self.user_service.save_conversation_message(
                user_id=user_id,
                conversation_id=conversation_id,
                role="assistant",
                content=ai_response["text"],
                confidence_score=ai_response.get("confidence_score", 0.0),
                model_used=ai_response.get("model_used", "unknown")
            )
            
        except Exception as e:
            logger.error(f"Failed to save conversation history: {str(e)}")
    
    def _build_search_filters(self, context: RAGContext) -> Dict[str, Any]:
        """Build search filters from extracted entities"""
        filters = {}
        
        if "region" in context.extracted_entities:
            filters["region"] = context.extracted_entities["region"]
        
        if "property_type" in context.extracted_entities:
            filters["property_type"] = context.extracted_entities["property_type"]
        
        if "transaction_type" in context.extracted_entities:
            filters["transaction_type"] = context.extracted_entities["transaction_type"]
        
        return filters
    
    def _build_property_filter(self, context: RAGContext) -> PropertyFilter:
        """Build property filter from entities and user profile"""
        filter_data = {}
        
        # Extract from entities
        entities = context.extracted_entities
        
        if "region" in entities:
            # Parse region (could be sido, sigungu, or dong)
            region = entities["region"]
            if "구" in region or "시" in region:
                filter_data["sigungu"] = region
            elif "동" in region:
                filter_data["dong"] = region
        
        if "property_type" in entities:
            filter_data["property_types"] = [entities["property_type"]]
        
        if "transaction_type" in entities:
            filter_data["transaction_types"] = [entities["transaction_type"]]
        
        if "budget_min" in entities:
            filter_data["min_price"] = entities["budget_min"]
        
        if "budget_max" in entities:
            filter_data["max_price"] = entities["budget_max"]
        
        if "room_count" in entities:
            filter_data["min_room_count"] = entities["room_count"]
            filter_data["max_room_count"] = entities["room_count"]
        
        if "area" in entities:
            filter_data["min_area_pyeong"] = entities["area"]
        
        # Enhance with user profile if available
        if context.user_profile:
            profile = context.user_profile
            
            # Add preferred locations
            if profile.preferred_locations and not filter_data.get("sigungu"):
                filter_data["sigungu"] = profile.preferred_locations[0]
            
            # Add budget constraints
            if profile.max_budget and not filter_data.get("max_price"):
                filter_data["max_price"] = profile.max_budget
            
            # Add property type preferences
            if profile.preferred_property_types and not filter_data.get("property_types"):
                filter_data["property_types"] = profile.preferred_property_types[:3]
            
            # Add transaction type preferences
            if profile.preferred_transaction_types and not filter_data.get("transaction_types"):
                filter_data["transaction_types"] = profile.preferred_transaction_types
        
        return PropertyFilter(**filter_data)
    
    def _calculate_property_relevance(
        self, 
        property_obj: Any, 
        context: RAGContext
    ) -> float:
        """Calculate property relevance score"""
        score = 0.0
        max_score = 0.0
        
        entities = context.extracted_entities
        
        # Location matching (weight: 0.3)
        if "region" in entities:
            max_score += 0.3
            if entities["region"] in property_obj.address:
                score += 0.3
            elif entities["region"] in property_obj.sigungu:
                score += 0.25
            elif entities["region"] in property_obj.dong:
                score += 0.2
        
        # Property type matching (weight: 0.2)
        if "property_type" in entities:
            max_score += 0.2
            if entities["property_type"] == property_obj.property_type:
                score += 0.2
        
        # Transaction type matching (weight: 0.2)
        if "transaction_type" in entities:
            max_score += 0.2
            if entities["transaction_type"] == property_obj.transaction_type:
                score += 0.2
        
        # Budget matching (weight: 0.2)
        if "budget_max" in entities:
            max_score += 0.2
            if property_obj.price <= entities["budget_max"]:
                score += 0.2
            elif property_obj.price <= entities["budget_max"] * 1.1:  # 10% tolerance
                score += 0.1
        
        # Room count matching (weight: 0.1)
        if "room_count" in entities:
            max_score += 0.1
            if property_obj.room_count == entities["room_count"]:
                score += 0.1
            elif abs(property_obj.room_count - entities["room_count"]) <= 1:
                score += 0.05
        
        # Normalize score
        if max_score > 0:
            return min(score / max_score, 1.0)
        
        return 0.5  # Default relevance for properties without specific criteria
    
    def _identify_matching_criteria(
        self, 
        property_obj: Any, 
        context: RAGContext
    ) -> List[str]:
        """Identify which criteria the property matches"""
        criteria = []
        entities = context.extracted_entities
        
        if "region" in entities and entities["region"] in property_obj.address:
            criteria.append(f"지역: {entities['region']}")
        
        if "property_type" in entities and entities["property_type"] == property_obj.property_type:
            criteria.append(f"유형: {entities['property_type']}")
        
        if "transaction_type" in entities and entities["transaction_type"] == property_obj.transaction_type:
            criteria.append(f"거래: {entities['transaction_type']}")
        
        if "budget_max" in entities and property_obj.price <= entities["budget_max"]:
            criteria.append(f"예산: {entities['budget_max']:,}원 이하")
        
        if "room_count" in entities and property_obj.room_count == entities["room_count"]:
            criteria.append(f"방 개수: {entities['room_count']}개")
        
        return criteria
    
    async def _cache_response(
        self, 
        validated_input: QueryValidation, 
        response: Dict[str, Any], 
        correlation_id: str
    ):
        """Cache successful response for future use"""
        try:
            if not self._cache_enabled or response.get("error"):
                return
            
            cache_key = f"rag_query:{validated_input.user_id}:{hash(validated_input.user_query)}"
            
            # Prepare cacheable response (remove sensitive data)
            cacheable_response = response.copy()
            cacheable_response.pop("correlation_id", None)
            cacheable_response["cached_at"] = datetime.utcnow().isoformat()
            
            await cache_manager.set_json(cache_key, cacheable_response, ttl=RAG_CACHE_TTL)
            
        except Exception as e:
            logger.warning(f"Failed to cache response: {str(e)}", extra={"correlation_id": correlation_id})
    
    def _compile_response(
        self, 
        context: RAGContext, 
        ai_response: Dict[str, Any], 
        pipeline_start: float
    ) -> Dict[str, Any]:
        """Compile final response with all gathered information"""
        processing_time = (time.time() - pipeline_start) * 1000
        
        return {
            "response": ai_response["text"],
            "intent": context.intent,
            "entities": context.extracted_entities,
            "properties": [
                {
                    "id": str(prop.property.id),
                    "address": prop.property.address,
                    "price": prop.property.price,
                    "property_type": prop.property.property_type,
                    "transaction_type": prop.property.transaction_type,
                    "area_m2": prop.property.area_m2,
                    "area_pyeong": prop.property.area_pyeong,
                    "relevance_score": prop.relevance_score,
                    "matching_criteria": prop.matching_criteria
                }
                for prop in context.relevant_properties[:5]  # Top 5 properties
            ],
            "policies": [
                {
                    "id": str(policy.policy.id),
                    "policy_name": policy.policy.policy_name,
                    "policy_type": policy.policy.policy_type,
                    "organizing_institution": policy.policy.organizing_institution,
                    "match_score": policy.match_score,
                    "eligibility_status": policy.eligibility_status,
                    "recommendation_reason": policy.recommendation_reason,
                    "next_steps": policy.next_steps
                }
                for policy in context.relevant_policies[:3]  # Top 3 policies
            ],
            "market_insights": context.market_context,
            "confidence_score": ai_response.get("confidence_score", 0.0),
            "processing_time_ms": int(processing_time),
            "search_metadata": context.search_metadata,
            "stage_timings": context.processing_metrics,
            "correlation_id": context.correlation_id,
            "cache_hit": False
        }
    
    def _create_timeout_response(self, start_time: float) -> Dict[str, Any]:
        """Create response for timeout errors"""
        return {
            "response": "죄송합니다. 요청 처리 시간이 초과되었습니다. 질문을 더 간단히 하여 다시 시도해 주세요.",
            "intent": "ERROR",
            "entities": {},
            "properties": [],
            "policies": [],
            "market_insights": {},
            "confidence_score": 0.0,
            "processing_time_ms": int((time.time() - start_time) * 1000),
            "error": "Request timeout",
            "error_type": "TIMEOUT"
        }
    
    def _create_validation_error_response(self, start_time: float, error_msg: str) -> Dict[str, Any]:
        """Create response for validation errors"""
        return {
            "response": "입력값에 오류가 있습니다. 올바른 형식으로 다시 시도해 주세요.",
            "intent": "ERROR",
            "entities": {},
            "properties": [],
            "policies": [],
            "market_insights": {},
            "confidence_score": 0.0,
            "processing_time_ms": int((time.time() - start_time) * 1000),
            "error": error_msg,
            "error_type": "VALIDATION_ERROR"
        }
    
    def _create_service_error_response(self, start_time: float, error_msg: str) -> Dict[str, Any]:
        """Create response for service errors"""
        return {
            "response": "죄송합니다. 일시적인 서비스 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            "intent": "ERROR",
            "entities": {},
            "properties": [],
            "policies": [],
            "market_insights": {},
            "confidence_score": 0.0,
            "processing_time_ms": int((time.time() - start_time) * 1000),
            "error": error_msg,
            "error_type": "SERVICE_ERROR"
        }
    
    def _create_general_error_response(self, start_time: float, error_msg: str) -> Dict[str, Any]:
        """Create response for general errors"""
        return {
            "response": "죄송합니다. 요청을 처리하는 중 오류가 발생했습니다. 다시 시도해 주세요.",
            "intent": "ERROR",
            "entities": {},
            "properties": [],
            "policies": [],
            "market_insights": {},
            "confidence_score": 0.0,
            "processing_time_ms": int((time.time() - start_time) * 1000),
            "error": error_msg,
            "error_type": "GENERAL_ERROR"
        }
    
    async def get_service_health(self) -> Dict[str, Any]:
        """Get RAG service health and metrics"""
        return {
            "service_name": "RAG Service",
            "status": "healthy",
            "metrics": rag_metrics.get_stats(),
            "cache_enabled": self._cache_enabled,
            "config": {
                "max_context_length": self.max_context_length,
                "similarity_threshold": self.similarity_threshold,
                "max_search_results": self.max_search_results,
                "max_processing_time": RAG_MAX_PROCESSING_TIME
            }
        }
    
    async def clear_cache(self, pattern: str = "rag_*") -> int:
        """Clear RAG service cache"""
        try:
            cleared_count = await cache_manager.clear_pattern(pattern)
            logger.info(f"Cleared {cleared_count} cache entries with pattern '{pattern}'")
            return cleared_count
        except Exception as e:
            logger.error(f"Failed to clear cache: {str(e)}")
            return 0