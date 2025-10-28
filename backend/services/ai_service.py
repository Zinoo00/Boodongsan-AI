"""
AI Service for Korean Real Estate RAG AI Chatbot
Uses AWS Bedrock (Claude) as primary AI provider
"""

import asyncio
import json
import logging
from enum import Enum
from typing import Any

import boto3
from botocore.exceptions import ClientError

from core.config import settings

logger = logging.getLogger(__name__)


class AIProvider(str, Enum):
    """AI provider types"""

    BEDROCK = "bedrock"
    AUTO = "auto"


class AIRequestType(str, Enum):
    """AI request types for caching"""

    CHAT = "chat"
    PROPERTY_SEARCH = "property_search"
    POLICY_MATCH = "policy_match"
    ENTITY_EXTRACTION = "entity_extraction"
    CONVERSATION = "conversation"


class AIService:
    """AI service with dual provider support"""

    def __init__(self):
        self.bedrock_client = None
        self.bedrock_runtime = None
        self._initialized = False

        # Provider configuration
        self.provider_config = {
            AIProvider.BEDROCK: {
                "model_id": settings.BEDROCK_MODEL_ID,
                "embedding_model_id": settings.BEDROCK_EMBEDDING_MODEL_ID,
                "max_tokens": 4000,
                "temperature": 0.7,
                "top_p": 0.9,
            },
        }

        # Provider selection strategy (모두 Bedrock 사용)
        self.provider_strategy = {
            "simple_chat": AIProvider.BEDROCK,
            "complex_analysis": AIProvider.BEDROCK,
            "entity_extraction": AIProvider.BEDROCK,
            "intent_classification": AIProvider.BEDROCK,
            "rag_response": AIProvider.BEDROCK,
            "embedding": AIProvider.BEDROCK,
        }

    async def initialize(self):
        """Initialize AI service providers"""
        if self._initialized:
            return

        try:
            # Initialize AWS Bedrock
            await self._initialize_bedrock()

            # Test provider
            await self._test_bedrock()

            self._initialized = True
            logger.info("AI service initialized with AWS Bedrock")

        except Exception as e:
            logger.error(f"Failed to initialize AI service: {str(e)}")
            raise

    async def _initialize_bedrock(self):
        """Initialize AWS Bedrock client"""
        try:
            self.bedrock_client = boto3.client(
                service_name="bedrock",
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )

            self.bedrock_runtime = boto3.client(
                service_name="bedrock-runtime",
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )

            logger.info("AWS Bedrock client initialized")

        except Exception as e:
            logger.error(f"Failed to initialize Bedrock: {str(e)}")
            raise

    async def _test_bedrock(self):
        """Test AWS Bedrock connection"""
        try:
            test_message = "Hello"
            response = await self._call_bedrock([{"role": "user", "content": test_message}])
            logger.info("Bedrock connection test successful")

        except Exception as e:
            logger.error(f"Bedrock connection test failed: {str(e)}")
            raise

    async def generate_rag_response(
        self,
        context: dict[str, Any],
        max_tokens: int | None = None,
        provider: AIProvider = AIProvider.AUTO,
    ) -> dict[str, Any]:
        """
        Generate RAG response using context

        Args:
            context: RAG context including query, entities, properties, policies
            max_tokens: Maximum tokens for response
            provider: AI provider to use
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Select provider
            if provider == AIProvider.AUTO:
                provider = self.provider_strategy.get("rag_response", AIProvider.BEDROCK)

            # Build system prompt for RAG
            system_prompt = self._build_rag_system_prompt()

            # Build user message with context
            user_message = self._build_rag_user_message(context)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]

            # Add conversation history
            if context.get("conversation_history"):
                # Insert conversation history before the current query
                history_messages = []
                for msg in context["conversation_history"][-3:]:  # Last 3 messages
                    if msg["role"] in ["user", "assistant"]:
                        history_messages.append(msg)

                messages = (
                    [{"role": "system", "content": system_prompt}]
                    + history_messages
                    + [{"role": "user", "content": user_message}]
                )

            # Generate response
            response_text = await self._generate_response(
                messages=messages,
                provider=provider,
                max_tokens=max_tokens or settings.RESPONSE_MAX_TOKENS,
            )

            # Calculate confidence score based on context completeness
            confidence_score = self._calculate_confidence_score(context, response_text)

            return {
                "text": response_text,
                "confidence_score": confidence_score,
                "model_used": f"{provider.value}_{self.provider_config[provider]['model_id']}",
                "context_used": {
                    "properties_count": len(context.get("properties", [])),
                    "policies_count": len(context.get("policies", [])),
                    "has_user_profile": bool(context.get("user_profile")),
                    "has_market_context": bool(context.get("market_context")),
                },
            }

        except Exception as e:
            logger.error(f"RAG response generation failed: {str(e)}")
            return {
                "text": "죄송합니다. 응답을 생성하는 중 오류가 발생했습니다. 다시 시도해 주세요.",
                "confidence_score": 0.0,
                "error": str(e),
            }

    async def extract_entities(
        self, text: str, provider: AIProvider = AIProvider.AUTO
    ) -> dict[str, Any]:
        """
        Extract entities from user text

        Args:
            text: User input text
            provider: AI provider to use
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Select provider
            if provider == AIProvider.AUTO:
                provider = self.provider_strategy.get("entity_extraction", AIProvider.BEDROCK)

            system_prompt = """
            당신은 부동산 상담 챗봇의 개체 추출 전문가입니다.
            사용자의 메시지에서 다음 정보를 추출해주세요:
            
            - age: 나이 (정수)
            - income: 연봉 (정수, 원 단위)
            - region: 희망 지역 (문자열, 시/구/동 포함)
            - property_type: 부동산 유형 (아파트, 빌라, 오피스텔, 단독주택, 연립주택, 원룸)
            - transaction_type: 거래 유형 (매매, 전세, 월세)
            - budget_min: 최소 예산 (정수, 원 단위)
            - budget_max: 최대 예산 (정수, 원 단위)
            - room_count: 방 개수 (정수)
            - area: 면적 (정수, 평 단위)
            - building_year: 건축년도 (정수)
            - floor_preference: 층수 선호도 (저층, 중층, 고층)
            - parking_needed: 주차장 필요 여부 (true/false)
            
            추출된 정보를 JSON 형태로 반환해주세요.
            정보가 없는 경우 해당 키를 포함하지 마세요.
            예시: {"region": "강남구", "property_type": "아파트", "budget_max": 300000000}
            """

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ]

            response = await self._generate_response(messages, provider, max_tokens=500)

            # Parse JSON response
            try:
                entities = json.loads(response.strip())

                # Validate and clean entities
                cleaned_entities = self._clean_entities(entities)

                return cleaned_entities

            except json.JSONDecodeError:
                logger.warning(f"Failed to parse entity extraction JSON: {response}")
                return {}

        except Exception as e:
            logger.error(f"Entity extraction failed: {str(e)}")
            return {}

    async def classify_intent(self, text: str, provider: AIProvider = AIProvider.AUTO) -> str:
        """
        Classify user intent

        Args:
            text: User input text
            provider: AI provider to use
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Select provider
            if provider == AIProvider.AUTO:
                provider = self.provider_strategy.get(
                    "intent_classification", AIProvider.BEDROCK
                )

            system_prompt = """
            당신은 부동산 상담 챗봇의 의도 분류 전문가입니다.
            사용자의 메시지를 다음 카테고리 중 하나로 분류해주세요:
            
            1. PROPERTY_SEARCH: 부동산 매물 검색 및 추천 요청
            2. POLICY_INQUIRY: 정부 지원 정책 문의
            3. MARKET_INFO: 부동산 시장 정보 및 분석 요청
            4. LOAN_CONSULTATION: 대출 및 금융 상담
            5. AREA_INFO: 지역 정보 및 인프라 문의
            6. GENERAL_CHAT: 일반 대화 및 인사
            7. COMPLAINT: 불만 또는 개선 요청
            
            카테고리명만 정확히 반환해주세요.
            """

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ]

            response = await self._generate_response(messages, provider, max_tokens=50)

            # Validate intent
            valid_intents = [
                "PROPERTY_SEARCH",
                "POLICY_INQUIRY",
                "MARKET_INFO",
                "LOAN_CONSULTATION",
                "AREA_INFO",
                "GENERAL_CHAT",
                "COMPLAINT",
            ]

            intent = response.strip().upper()
            if intent in valid_intents:
                return intent
            else:
                return "GENERAL_CHAT"  # Default intent

        except Exception as e:
            logger.error(f"Intent classification failed: {str(e)}")
            return "GENERAL_CHAT"

    async def generate_embeddings(
        self, texts: list[str], provider: AIProvider = AIProvider.AUTO
    ) -> list[list[float]]:
        """
        Generate embeddings for texts

        Args:
            texts: List of texts to embed
            provider: AI provider to use
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Currently only Bedrock supports embeddings
            embeddings = []

            for text in texts:
                # Use Bedrock Titan embeddings
                body = json.dumps({"inputText": text})

                response = self.bedrock_runtime.invoke_model(
                    modelId=settings.BEDROCK_EMBEDDING_MODEL_ID,
                    body=body,
                    contentType="application/json",
                    accept="application/json",
                )

                response_body = json.loads(response["body"].read())
                embedding = response_body["embedding"]
                embeddings.append(embedding)

            return embeddings

        except Exception as e:
            logger.error(f"Embedding generation failed: {str(e)}")
            # Return dummy embeddings as fallback
            return [[0.0] * 768 for _ in texts]

    async def _generate_response(
        self, messages: list[dict[str, str]], provider: AIProvider, max_tokens: int = 1000
    ) -> str:
        """Generate response using AWS Bedrock"""

        try:
            return await self._call_bedrock(messages, max_tokens)

        except Exception as e:
            logger.error(f"Response generation failed: {str(e)}")
            raise

    async def _call_bedrock(self, messages: list[dict[str, str]], max_tokens: int = 1000) -> str:
        """Call AWS Bedrock Claude model"""

        try:
            # Format messages for Anthropic Claude
            system_content = ""
            anthropic_messages = []

            for message in messages:
                if message["role"] == "system":
                    system_content = message["content"]
                elif message["role"] in ["user", "assistant"]:
                    anthropic_messages.append(
                        {"role": message["role"], "content": message["content"]}
                    )

            # Build request body
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": self.provider_config[AIProvider.BEDROCK]["temperature"],
                "top_p": self.provider_config[AIProvider.BEDROCK]["top_p"],
                "messages": anthropic_messages,
            }

            if system_content:
                body["system"] = system_content

            # Call Bedrock
            response = await asyncio.to_thread(
                self.bedrock_runtime.invoke_model,
                modelId=settings.BEDROCK_MODEL_ID,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(response["body"].read())
            return response_body["content"][0]["text"]

        except ClientError as e:
            logger.error(f"Bedrock API error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Bedrock call failed: {str(e)}")
            raise

    def _build_rag_system_prompt(self) -> str:
        """Build system prompt for RAG responses"""
        return """
당신은 한국 부동산 전문 AI 상담사입니다. 사용자에게 정확하고 도움이 되는 부동산 정보를 제공합니다.

역할과 책임:
1. 부동산 매물 정보를 기반으로 개인맞춤형 추천 제공
2. 정부 지원 정책에 대한 정확한 정보 제공
3. 부동산 시장 동향과 지역 정보 분석
4. 친근하고 전문적인 상담 서비스

응답 가이드라인:
- 제공된 정보를 바탕으로 정확하고 구체적인 답변
- 사용자의 상황과 요구사항을 고려한 개인화된 조언
- 복잡한 내용도 이해하기 쉽게 설명
- 추가 정보가 필요한 경우 구체적인 질문 제시
- 존댓말 사용 및 친근한 톤 유지

정보 우선순위:
1. 사용자가 직접 요청한 정보
2. 사용자 프로필에 맞는 맞춤형 정보
3. 관련 정부 지원 정책
4. 시장 동향 및 지역 정보
"""

    def _build_rag_user_message(self, context: dict[str, Any]) -> str:
        """Build user message with RAG context"""

        message_parts = []

        # User query
        message_parts.append(f"사용자 질문: {context['user_query']}")

        # User profile
        if context.get("user_profile"):
            profile = context["user_profile"]
            profile_info = []

            if profile.get("age"):
                profile_info.append(f"나이: {profile['age']}세")
            if profile.get("annual_income"):
                profile_info.append(f"연봉: {profile['annual_income']:,}원")
            if profile.get("household_size"):
                profile_info.append(f"가구원 수: {profile['household_size']}명")
            if profile.get("max_budget"):
                profile_info.append(f"최대 예산: {profile['max_budget']:,}원")
            if profile.get("preferred_locations"):
                profile_info.append(f"선호 지역: {', '.join(profile['preferred_locations'])}")
            if profile.get("preferred_property_types"):
                profile_info.append(
                    f"선호 부동산 유형: {', '.join(profile['preferred_property_types'])}"
                )

            if profile_info:
                message_parts.append(f"사용자 프로필: {', '.join(profile_info)}")

        # Extracted entities
        if context.get("entities"):
            entities = context["entities"]
            entity_info = []

            for key, value in entities.items():
                if key == "region":
                    entity_info.append(f"희망 지역: {value}")
                elif key == "property_type":
                    entity_info.append(f"부동산 유형: {value}")
                elif key == "transaction_type":
                    entity_info.append(f"거래 유형: {value}")
                elif key == "budget_max":
                    entity_info.append(f"최대 예산: {value:,}원")
                elif key == "room_count":
                    entity_info.append(f"방 개수: {value}개")

            if entity_info:
                message_parts.append(f"추출된 요구사항: {', '.join(entity_info)}")

        # Properties
        if context.get("properties"):
            properties = context["properties"][:3]  # Top 3 properties
            property_info = []

            for i, prop in enumerate(properties, 1):
                prop_str = f"매물 {i}: {prop['address']}, {prop['property_type']}, {prop['transaction_type']}, {prop['price']:,}원"
                if prop.get("area_pyeong"):
                    prop_str += f", {prop['area_pyeong']}평"
                property_info.append(prop_str)

            if property_info:
                message_parts.append("추천 매물:\n" + "\n".join(property_info))

        # Policies
        if context.get("policies"):
            policies = context["policies"][:2]  # Top 2 policies
            policy_info = []

            for i, policy in enumerate(policies, 1):
                policy_str = (
                    f"정책 {i}: {policy['policy_name']} ({policy['organizing_institution']})"
                )
                policy_info.append(policy_str)

            if policy_info:
                message_parts.append("적용 가능한 정부 정책:\n" + "\n".join(policy_info))

        # Market context
        if context.get("market_context"):
            market = context["market_context"]
            market_info = []

            if market.get("average_price"):
                market_info.append(f"평균 가격: {market['average_price']:,}원")
            if market.get("price_trend"):
                market_info.append(f"가격 동향: {market['price_trend']}")

            if market_info:
                message_parts.append(f"시장 정보: {', '.join(market_info)}")

        # LightRAG answer
        if context.get("knowledge_answer"):
            mode = context.get("knowledge_mode") or "hybrid"
            message_parts.append(
                f"LightRAG ({mode}) 결과 요약:\n{context['knowledge_answer']}"
            )

        # Vector search fallback
        vector_results = context.get("vector_results") or []
        if vector_results:
            snippets = []
            for idx, item in enumerate(vector_results[:3], 1):
                document = (item.get("document") or "").strip()
                if not document:
                    document = json.dumps(item.get("metadata", {}), ensure_ascii=False)
                snippets.append(f"- 후보 {idx}: {document[:200]}")
            if snippets:
                message_parts.append("벡터 검색 참고 정보:\n" + "\n".join(snippets))

        return "\n\n".join(message_parts)

    def _clean_entities(self, entities: dict[str, Any]) -> dict[str, Any]:
        """Clean and validate extracted entities"""
        cleaned = {}

        # Integer fields
        for field in ["age", "income", "budget_min", "budget_max", "room_count", "building_year"]:
            if field in entities:
                try:
                    value = int(entities[field])
                    if value > 0:
                        cleaned[field] = value
                except (ValueError, TypeError):
                    pass

        # String fields
        for field in ["region", "property_type", "transaction_type", "floor_preference"]:
            if field in entities and isinstance(entities[field], str):
                cleaned[field] = entities[field].strip()

        # Float fields
        for field in ["area"]:
            if field in entities:
                try:
                    value = float(entities[field])
                    if value > 0:
                        cleaned[field] = value
                except (ValueError, TypeError):
                    pass

        # Boolean fields
        for field in ["parking_needed"]:
            if field in entities:
                if isinstance(entities[field], bool):
                    cleaned[field] = entities[field]
                elif isinstance(entities[field], str):
                    cleaned[field] = entities[field].lower() in ["true", "yes", "1", "참", "필요"]

        return cleaned

    def _generate_cache_key(self, request_type: AIRequestType, *args) -> str:
        """Generate cache key for AI requests"""
        content = ":".join([request_type.value] + [str(arg) for arg in args])
        return f"ai_{hashlib.md5(content.encode()).hexdigest()[:16]}"

    async def _get_cached_response(self, cache_key: str) -> Any | None:
        """Get cached response if available"""
        if not self._cache_enabled:
            return None

        try:
            return await cache_manager.get_json(cache_key)
        except Exception as e:
            logger.warning(f"Cache get failed: {str(e)}")
            return None

    async def _cache_response(self, cache_key: str, response: Any, request_type: AIRequestType):
        """Cache successful response"""
        if not self._cache_enabled:
            return

        try:
            ttl = self._cache_config.get(request_type, AI_CACHE_TTL)
            await cache_manager.set_json(cache_key, response, ttl=ttl)
        except Exception as e:
            logger.warning(f"Cache set failed: {str(e)}")

    async def _build_rag_messages(self, context: dict[str, Any]) -> list[dict[str, str]]:
        """Build and validate RAG messages"""
        # Build system prompt
        system_prompt = self._build_rag_system_prompt()

        # Build user message with context
        user_message = self._build_rag_user_message(context)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        # Add conversation history
        if context.get("conversation_history"):
            history_messages = []
            for msg in context["conversation_history"][-3:]:
                if msg["role"] in ["user", "assistant"]:
                    history_messages.append({"role": msg["role"], "content": msg["content"]})

            # Insert history between system and current user message
            messages = (
                [{"role": "system", "content": system_prompt}]
                + history_messages
                + [{"role": "user", "content": user_message}]
            )

        return messages

    def _create_error_response(
        self, error_message: str, correlation_id: str, request_start: float
    ) -> dict[str, Any]:
        """Create standardized error response"""
        return {
            "text": f"죄송합니다. {error_message}가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            "confidence_score": 0.0,
            "error": error_message,
            "correlation_id": correlation_id,
            "generation_time_ms": (time.time() - request_start) * 1000,
            "cache_hit": False,
        }

    def _calculate_confidence_score(self, context: dict[str, Any], response_text: str) -> float:
        """Calculate confidence score based on available context"""

        score = 0.0

        # Base score for having a response
        if response_text and len(response_text) > 10:
            score += 0.3

        # Entity extraction quality
        entities = context.get("entities", {})
        if entities:
            score += min(len(entities) * 0.1, 0.2)

        # Property data availability
        properties = context.get("properties", [])
        if properties:
            score += min(len(properties) * 0.05, 0.2)

        # Policy data availability
        policies = context.get("policies", [])
        if policies:
            score += min(len(policies) * 0.05, 0.15)

        # User profile completeness
        if context.get("user_profile"):
            score += 0.15

        # Market context availability
        if context.get("market_context"):
            score += 0.1

        return min(score, 1.0)

    async def close(self):
        """Close AI service connections with cleanup"""
        try:
            # Reset circuit breakers
            for provider in self._circuit_breakers:
                self._circuit_breakers[provider] = CircuitBreakerState()

            # Clear rate limiters
            for provider in self._rate_limiter:
                self._rate_limiter[provider].clear()

            self._initialized = False
            logger.info("AI service connections closed and state reset")

        except Exception as e:
            logger.error(f"Error closing AI service: {str(e)}")

    async def health_check(self) -> dict[str, Any]:
        """Comprehensive health check of AI service"""
        health_start = time.time()

        health = {
            "service_status": "healthy",
            "providers": {
                "bedrock": {
                    "available": False,
                    "response_time_ms": None,
                    "circuit_breaker_open": self._is_circuit_breaker_open(AIProvider.BEDROCK),
                    "error": None,
                },
            },
            "metrics": {
                "bedrock": {
                    "success_rate": self._metrics[AIProvider.BEDROCK].get_success_rate(),
                    "avg_response_time_ms": self._metrics[
                        AIProvider.BEDROCK
                    ].get_avg_response_time(),
                    "total_requests": self._metrics[AIProvider.BEDROCK].total_requests,
                    "cache_hit_rate": (
                        self._metrics[AIProvider.BEDROCK].cache_hits
                        / max(self._metrics[AIProvider.BEDROCK].total_requests, 1)
                    ),
                    "circuit_breaker_trips": self._metrics[
                        AIProvider.BEDROCK
                    ].circuit_breaker_trips,
                },
            },
            "cache_enabled": self._cache_enabled,
            "health_check_time_ms": 0,
        }

        try:
            if not self._initialized:
                await self.initialize()

            # Test Bedrock provider
            result = await self._health_check_provider(AIProvider.BEDROCK)

            if isinstance(result, Exception):
                health["providers"]["bedrock"]["error"] = str(result)
                health["service_status"] = "unhealthy"
                logger.debug(f"Bedrock health check failed: {str(result)}")
            else:
                health["providers"]["bedrock"]["available"] = True
                health["providers"]["bedrock"]["response_time_ms"] = result
                health["service_status"] = "healthy"

        except Exception as e:
            logger.error(f"AI service health check failed: {str(e)}")
            health["service_status"] = "unhealthy"
            health["error"] = str(e)

        health["health_check_time_ms"] = (time.time() - health_start) * 1000
        return health

    async def _health_check_provider(self, provider: AIProvider) -> float:
        """Health check for individual provider returning response time"""
        start_time = time.time()

        try:
            test_messages = [{"role": "user", "content": "Health check"}]
            await self._call_bedrock_enhanced(test_messages, max_tokens=5)
            return (time.time() - start_time) * 1000

        except Exception as e:
            raise e

    async def get_metrics(self) -> dict[str, Any]:
        """Get detailed AI service metrics"""
        return {
            "providers": {
                "bedrock": {
                    "total_requests": self._metrics[AIProvider.BEDROCK].total_requests,
                    "successful_requests": self._metrics[AIProvider.BEDROCK].successful_requests,
                    "failed_requests": self._metrics[AIProvider.BEDROCK].failed_requests,
                    "success_rate": self._metrics[AIProvider.BEDROCK].get_success_rate(),
                    "avg_response_time_ms": self._metrics[
                        AIProvider.BEDROCK
                    ].get_avg_response_time(),
                    "cache_hits": self._metrics[AIProvider.BEDROCK].cache_hits,
                    "rate_limit_hits": self._metrics[AIProvider.BEDROCK].rate_limit_hits,
                    "circuit_breaker_trips": self._metrics[
                        AIProvider.BEDROCK
                    ].circuit_breaker_trips,
                    "circuit_breaker_open": self._is_circuit_breaker_open(AIProvider.BEDROCK),
                },
            },
            "cache_enabled": self._cache_enabled,
            "rate_limit_per_minute": AI_RATE_LIMIT_REQUESTS_PER_MINUTE,
            "circuit_breaker_threshold": AI_CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            "circuit_breaker_recovery_timeout_seconds": AI_CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
        }

    async def clear_cache(self, pattern: str = "ai_*") -> int:
        """Clear AI service cache"""
        try:
            cleared_count = await cache_manager.clear_pattern(pattern)
            logger.info(f"Cleared {cleared_count} AI cache entries")
            return cleared_count
        except Exception as e:
            logger.error(f"Failed to clear AI cache: {str(e)}")
            return 0


# Global AI service instance
ai_service = AIService()
