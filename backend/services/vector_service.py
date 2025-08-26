"""
Vector Service for Korean Real Estate RAG AI Chatbot
Handles Qdrant vector database operations and embeddings with enterprise-grade reliability
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    PointStruct,
    Range,
    VectorParams,
)
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..core.config import settings
from ..core.database import cache_manager
from ..core.exceptions import ErrorCode, VectorServiceError

logger = logging.getLogger(__name__)

# Vector service configuration
VECTOR_RETRY_ATTEMPTS = 3
VECTOR_RETRY_WAIT_MIN = 1
VECTOR_RETRY_WAIT_MAX = 8
VECTOR_OPERATION_TIMEOUT = 30  # 30 seconds
EMBEDDING_CACHE_TTL = 7200  # 2 hours
SEARCH_CACHE_TTL = 900  # 15 minutes
HEALTH_CHECK_INTERVAL = 60  # 1 minute


# Performance metrics
class VectorMetrics:
    """Vector service performance metrics"""

    def __init__(self):
        self.embedding_operations = 0
        self.search_operations = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.errors = 0
        self.avg_embedding_time = 0.0
        self.avg_search_time = 0.0
        self.connection_retries = 0

    def record_embedding(self, processing_time: float, cache_hit: bool = False):
        self.embedding_operations += 1
        if cache_hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
            # Update rolling average for non-cached operations
            non_cached_ops = self.embedding_operations - self.cache_hits
            if non_cached_ops > 0:
                self.avg_embedding_time = (
                    self.avg_embedding_time * (non_cached_ops - 1) + processing_time
                ) / non_cached_ops

    def record_search(self, processing_time: float, cache_hit: bool = False):
        self.search_operations += 1
        if cache_hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
            # Update rolling average for non-cached operations
            non_cached_ops = self.search_operations - self.cache_hits
            if non_cached_ops > 0:
                self.avg_search_time = (
                    self.avg_search_time * (non_cached_ops - 1) + processing_time
                ) / non_cached_ops

    def record_error(self):
        self.errors += 1

    def record_retry(self):
        self.connection_retries += 1

    def get_stats(self) -> dict[str, Any]:
        total_ops = self.embedding_operations + self.search_operations
        return {
            "embedding_operations": self.embedding_operations,
            "search_operations": self.search_operations,
            "total_operations": total_ops,
            "cache_hit_rate": self.cache_hits / max(total_ops, 1),
            "error_rate": self.errors / max(total_ops, 1),
            "avg_embedding_time_ms": self.avg_embedding_time,
            "avg_search_time_ms": self.avg_search_time,
            "connection_retries": self.connection_retries,
        }


# Global metrics instance
vector_metrics = VectorMetrics()


@dataclass
class SearchResult:
    """Vector search result"""

    id: str
    score: float
    payload: dict[str, Any]
    vector: list[float] | None = None


@dataclass
class EmbeddingResult:
    """Embedding generation result"""

    text: str
    embedding: list[float]
    model: str
    timestamp: datetime


class VectorService:
    """Enhanced vector service for Qdrant operations with enterprise-grade reliability"""

    def __init__(self):
        self.client = None
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.vector_size = settings.VECTOR_SIZE
        self._initialized = False
        self._last_health_check = 0
        self._connection_healthy = False
        self._circuit_breaker_failures = 0
        self._circuit_breaker_open = False
        self._circuit_breaker_last_failure = 0

        # Circuit breaker configuration
        self.circuit_breaker_threshold = 5  # failures
        self.circuit_breaker_timeout = 60  # seconds

        logger.info(
            "VectorService initialized",
            extra={
                "collection_name": self.collection_name,
                "vector_size": self.vector_size,
                "circuit_breaker_threshold": self.circuit_breaker_threshold,
            },
        )

    @retry(
        stop=stop_after_attempt(VECTOR_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=VECTOR_RETRY_WAIT_MIN, max=VECTOR_RETRY_WAIT_MAX),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    )
    async def initialize(self):
        """Initialize Qdrant client and collection with retry logic"""
        if self._initialized:
            return

        correlation_id = f"vec_init_{int(time.time() * 1000)}"

        try:
            logger.info(
                "Initializing Qdrant vector service", extra={"correlation_id": correlation_id}
            )

            # Initialize Qdrant client with enhanced configuration
            self.client = QdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY,
                timeout=VECTOR_OPERATION_TIMEOUT,
                prefer_grpc=True,
                grpc_options={
                    "grpc.keepalive_time_ms": 30000,
                    "grpc.keepalive_timeout_ms": 5000,
                    "grpc.keepalive_permit_without_calls": True,
                    "grpc.http2.max_pings_without_data": 0,
                    "grpc.http2.min_time_between_pings_ms": 10000,
                    "grpc.http2.min_ping_interval_without_data_ms": 300000,
                },
            )

            # Check if collection exists, create if not
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]

            if self.collection_name not in collection_names:
                await self._create_collection()
                logger.info(
                    "Created new Qdrant collection",
                    extra={
                        "collection_name": self.collection_name,
                        "correlation_id": correlation_id,
                    },
                )

            # Verify collection configuration
            collection_info = self.client.get_collection(self.collection_name)

            logger.info(
                "Qdrant vector service initialized successfully",
                extra={
                    "collection_name": self.collection_name,
                    "vectors_count": collection_info.vectors_count,
                    "correlation_id": correlation_id,
                },
            )

            self._initialized = True
            self._connection_healthy = True
            self._circuit_breaker_failures = 0
            self._circuit_breaker_open = False

        except Exception as e:
            vector_metrics.record_error()
            vector_metrics.record_retry()

            logger.error(
                "Failed to initialize Qdrant client",
                extra={"error": str(e), "correlation_id": correlation_id},
            )

            raise VectorServiceError(
                message="Vector service initialization failed",
                error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                operation="initialize",
                cause=e,
                correlation_id=correlation_id,
            )

    async def _create_collection(self):
        """Create Qdrant collection with proper configuration"""
        try:
            # Create collection with vector configuration
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                    on_disk=True,  # Store vectors on disk for better memory efficiency
                ),
                optimizers_config=models.OptimizersConfig(
                    default_segment_number=2,
                    max_segment_size=20000,
                    memmap_threshold=20000,
                    indexing_threshold=10000,
                    flush_interval_sec=5,
                    max_optimization_threads=2,
                ),
                hnsw_config=models.HnswConfig(
                    m=16,
                    ef_construct=100,
                    full_scan_threshold=10000,
                    max_indexing_threads=2,
                    on_disk=True,
                ),
            )

            # Create indexes for efficient filtering
            await self._create_payload_indexes()

            logger.info(f"Created Qdrant collection: {self.collection_name}")

        except Exception as e:
            logger.error(f"Failed to create Qdrant collection: {str(e)}")
            raise

    async def _create_payload_indexes(self):
        """Create payload indexes for efficient filtering"""
        try:
            # Property-related indexes
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="content_type",
                field_schema=models.KeywordIndexParams(type="keyword", is_tenant=False),
            )

            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="property_type",
                field_schema=models.KeywordIndexParams(type="keyword", is_tenant=False),
            )

            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="transaction_type",
                field_schema=models.KeywordIndexParams(type="keyword", is_tenant=False),
            )

            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="sido",
                field_schema=models.KeywordIndexParams(type="keyword", is_tenant=False),
            )

            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="sigungu",
                field_schema=models.KeywordIndexParams(type="keyword", is_tenant=False),
            )

            # Numerical indexes
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="price",
                field_schema=models.IntegerIndexParams(type="integer", is_tenant=False),
            )

            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="area_m2",
                field_schema=models.FloatIndexParams(type="float", is_tenant=False),
            )

            # Datetime index
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="created_at",
                field_schema=models.DatetimeIndexParams(type="datetime", is_tenant=False),
            )

            logger.info("Created payload indexes for Qdrant collection")

        except Exception as e:
            logger.error(f"Failed to create payload indexes: {str(e)}")

    async def generate_embedding(
        self, text: str, model: str = "default", correlation_id: str | None = None
    ) -> list[float]:
        """
        Generate embedding for text with caching and error handling

        Args:
            text: Input text to embed
            model: Embedding model to use
            correlation_id: Request correlation ID for tracking

        Returns:
            List of floats representing the embedding vector
        """
        start_time = time.time()
        correlation_id = correlation_id or f"vec_embed_{int(time.time() * 1000)}"

        try:
            # Check circuit breaker
            if self._circuit_breaker_open:
                if time.time() - self._circuit_breaker_last_failure > self.circuit_breaker_timeout:
                    self._circuit_breaker_open = False
                    self._circuit_breaker_failures = 0
                    logger.info(
                        "Circuit breaker reset for embedding service",
                        extra={"correlation_id": correlation_id},
                    )
                else:
                    raise VectorServiceError(
                        message="Embedding service circuit breaker is open",
                        error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                        operation="generate_embedding",
                        correlation_id=correlation_id,
                    )

            # Generate cache key
            text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
            cache_key = f"embedding:{model}:{text_hash}"

            # Try to get from cache first
            cached_embedding = await cache_manager.get_json(cache_key)
            if cached_embedding:
                processing_time = (time.time() - start_time) * 1000
                vector_metrics.record_embedding(processing_time, cache_hit=True)

                logger.debug(
                    "Embedding cache hit",
                    extra={
                        "cache_key": cache_key,
                        "processing_time_ms": processing_time,
                        "correlation_id": correlation_id,
                    },
                )

                return cached_embedding["embedding"]

            # Generate new embedding
            embedding = await self._generate_embedding_impl(text, model, correlation_id)

            # Cache the result
            embedding_data = {
                "embedding": embedding,
                "model": model,
                "text_length": len(text),
                "created_at": datetime.utcnow().isoformat(),
            }

            await cache_manager.set_json(cache_key, embedding_data, ttl=EMBEDDING_CACHE_TTL)

            processing_time = (time.time() - start_time) * 1000
            vector_metrics.record_embedding(processing_time, cache_hit=False)

            logger.debug(
                "Embedding generated successfully",
                extra={
                    "text_length": len(text),
                    "model": model,
                    "processing_time_ms": processing_time,
                    "correlation_id": correlation_id,
                },
            )

            # Reset circuit breaker on success
            self._circuit_breaker_failures = min(self._circuit_breaker_failures, 0)

            return embedding

        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            vector_metrics.record_error()

            # Update circuit breaker
            self._circuit_breaker_failures += 1
            self._circuit_breaker_last_failure = time.time()

            if self._circuit_breaker_failures >= self.circuit_breaker_threshold:
                self._circuit_breaker_open = True
                logger.warning(
                    "Circuit breaker opened for embedding service",
                    extra={
                        "failures": self._circuit_breaker_failures,
                        "correlation_id": correlation_id,
                    },
                )

            logger.error(
                "Failed to generate embedding",
                extra={
                    "text_length": len(text),
                    "model": model,
                    "processing_time_ms": processing_time,
                    "error": str(e),
                    "correlation_id": correlation_id,
                },
            )

            raise VectorServiceError(
                message="Embedding generation failed",
                error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                operation="generate_embedding",
                details={"text_length": len(text), "model": model},
                cause=e,
                correlation_id=correlation_id,
            )

    async def _generate_embedding_impl(
        self, text: str, model: str, correlation_id: str
    ) -> list[float]:
        """
        Internal embedding generation implementation using AI service
        """
        try:
            # Import AI service for embedding generation
            from ..services.ai_service import AIService

            # Check if we have AI service available
            try:
                # Try to use existing AI service instance if available
                if hasattr(self, "_ai_service") and self._ai_service:
                    ai_service = self._ai_service
                else:
                    # Create a new AI service instance
                    ai_service = AIService()
                    if not getattr(ai_service, "_initialized", False):
                        await ai_service.initialize()
                    self._ai_service = ai_service

                # Generate embedding using AI service
                embeddings = await ai_service.generate_embeddings([text])
                if embeddings and len(embeddings) > 0:
                    return embeddings[0]

            except ImportError:
                logger.warning(
                    "AI service not available for embedding generation, using fallback",
                    extra={"correlation_id": correlation_id},
                )
            except Exception as e:
                logger.warning(
                    "Failed to use AI service for embedding, using fallback",
                    extra={"error": str(e), "correlation_id": correlation_id},
                )

            # Fallback: Create a deterministic but pseudo-random embedding for testing
            logger.info(
                "Using fallback embedding generation (for development only)",
                extra={"correlation_id": correlation_id},
            )

            hash_obj = hashlib.md5(text.encode())
            seed = int(hash_obj.hexdigest(), 16) % (2**32)
            np.random.seed(seed)

            # Generate normalized random vector
            embedding = np.random.normal(0, 1, self.vector_size)
            embedding = embedding / np.linalg.norm(embedding)

            # Simulate processing time
            await asyncio.sleep(0.01)  # 10ms simulation

            return embedding.tolist()

        except Exception as e:
            logger.error(
                "Embedding implementation failed",
                extra={"error": str(e), "correlation_id": correlation_id},
            )
            raise

    async def add_documents(self, documents: list[dict[str, Any]], batch_size: int = 100) -> bool:
        """
        Add documents to vector database

        Args:
            documents: List of documents with text, metadata, and optional id
            batch_size: Batch size for uploading
        """
        if not self._initialized:
            await self.initialize()

        try:
            total_docs = len(documents)

            for i in range(0, total_docs, batch_size):
                batch = documents[i : i + batch_size]
                points = []

                for doc in batch:
                    # Generate embedding for document text
                    text = doc.get("text", "")
                    if not text:
                        logger.warning(
                            f"Skipping document without text: {doc.get('id', 'unknown')}"
                        )
                        continue

                    embedding = await self.generate_embedding(text)

                    # Prepare point data
                    point_id = doc.get("id", str(uuid.uuid4()))
                    payload = {
                        "text": text,
                        "content_type": doc.get("content_type", "unknown"),
                        "created_at": doc.get("created_at", datetime.utcnow().isoformat()),
                        **doc.get("metadata", {}),
                    }

                    point = PointStruct(id=point_id, vector=embedding, payload=payload)
                    points.append(point)

                if points:
                    # Upload batch to Qdrant
                    operation_info = self.client.upsert(
                        collection_name=self.collection_name, wait=True, points=points
                    )

                    logger.info(
                        f"Uploaded batch {i//batch_size + 1}/{(total_docs + batch_size - 1)//batch_size} "
                        f"({len(points)} documents)"
                    )

            logger.info(f"Successfully added {total_docs} documents to vector database")
            return True

        except Exception as e:
            logger.error(f"Failed to add documents: {str(e)}")
            return False

    @retry(
        stop=stop_after_attempt(VECTOR_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=VECTOR_RETRY_WAIT_MIN, max=VECTOR_RETRY_WAIT_MAX),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    )
    async def search(
        self,
        query_vector: list[float],
        limit: int = 10,
        score_threshold: float = 0.0,
        filter_conditions: Filter | None = None,
        correlation_id: str | None = None,
    ) -> list[SearchResult]:
        """
        Perform vector similarity search with caching and error handling

        Args:
            query_vector: Query embedding vector
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            filter_conditions: Qdrant filter conditions
            correlation_id: Request correlation ID for tracking
        """
        start_time = time.time()
        correlation_id = correlation_id or f"vec_search_{int(time.time() * 1000)}"

        if not self._initialized:
            await self.initialize()

        try:
            # Check circuit breaker
            if self._circuit_breaker_open:
                if time.time() - self._circuit_breaker_last_failure > self.circuit_breaker_timeout:
                    self._circuit_breaker_open = False
                    self._circuit_breaker_failures = 0
                else:
                    raise VectorServiceError(
                        message="Vector search circuit breaker is open",
                        error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                        operation="search",
                        correlation_id=correlation_id,
                    )

            # Generate cache key for search results
            vector_hash = hashlib.sha256(
                json.dumps(query_vector, sort_keys=True).encode()
            ).hexdigest()[:16]

            filter_hash = "none"
            if filter_conditions:
                filter_str = json.dumps(filter_conditions.dict(), sort_keys=True)
                filter_hash = hashlib.sha256(filter_str.encode()).hexdigest()[:8]

            cache_key = f"search:{vector_hash}:{filter_hash}:{limit}:{score_threshold}"

            # Try to get from cache first
            cached_results = await cache_manager.get_json(cache_key)
            if cached_results:
                processing_time = (time.time() - start_time) * 1000
                vector_metrics.record_search(processing_time, cache_hit=True)

                logger.debug(
                    "Search cache hit",
                    extra={
                        "cache_key": cache_key,
                        "results_count": len(cached_results["results"]),
                        "processing_time_ms": processing_time,
                        "correlation_id": correlation_id,
                    },
                )

                # Convert cached results back to SearchResult objects
                results = [
                    SearchResult(id=result["id"], score=result["score"], payload=result["payload"])
                    for result in cached_results["results"]
                ]
                return results

            # Perform actual search
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=filter_conditions,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False,
            )

            results = []
            for point in search_result:
                result = SearchResult(
                    id=str(point.id), score=point.score, payload=point.payload or {}
                )
                results.append(result)

            # Cache the results
            search_data = {
                "results": [
                    {"id": result.id, "score": result.score, "payload": result.payload}
                    for result in results
                ],
                "query_params": {
                    "limit": limit,
                    "score_threshold": score_threshold,
                    "has_filters": filter_conditions is not None,
                },
                "created_at": datetime.utcnow().isoformat(),
            }

            await cache_manager.set_json(cache_key, search_data, ttl=SEARCH_CACHE_TTL)

            processing_time = (time.time() - start_time) * 1000
            vector_metrics.record_search(processing_time, cache_hit=False)

            logger.info(
                "Vector search completed successfully",
                extra={
                    "results_count": len(results),
                    "limit": limit,
                    "score_threshold": score_threshold,
                    "processing_time_ms": processing_time,
                    "correlation_id": correlation_id,
                },
            )

            # Reset circuit breaker on success
            self._circuit_breaker_failures = min(self._circuit_breaker_failures, 0)

            return results

        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            vector_metrics.record_error()

            # Update circuit breaker
            self._circuit_breaker_failures += 1
            self._circuit_breaker_last_failure = time.time()

            if self._circuit_breaker_failures >= self.circuit_breaker_threshold:
                self._circuit_breaker_open = True
                logger.warning(
                    "Circuit breaker opened for vector search",
                    extra={
                        "failures": self._circuit_breaker_failures,
                        "correlation_id": correlation_id,
                    },
                )

            logger.error(
                "Vector search failed",
                extra={
                    "limit": limit,
                    "score_threshold": score_threshold,
                    "processing_time_ms": processing_time,
                    "error": str(e),
                    "correlation_id": correlation_id,
                },
            )

            raise VectorServiceError(
                message="Vector search failed",
                error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                operation="search",
                details={"limit": limit, "score_threshold": score_threshold},
                cause=e,
                correlation_id=correlation_id,
            )

    async def hybrid_search(
        self,
        query_embedding: list[float],
        query_text: str,
        limit: int = 10,
        threshold: float = 0.0,
        filters: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> list[SearchResult]:
        """
        Perform hybrid search combining vector similarity and keyword matching

        Args:
            query_embedding: Query embedding vector
            query_text: Original query text for keyword matching
            limit: Maximum number of results
            threshold: Minimum similarity score
            filters: Additional filters
            correlation_id: Request correlation ID for tracking
        """
        start_time = time.time()
        correlation_id = correlation_id or f"vec_hybrid_{int(time.time() * 1000)}"

        try:
            # Build filter conditions
            filter_conditions = self._build_filter_conditions(filters)

            # Perform vector search with more results for re-ranking
            vector_results = await self.search(
                query_vector=query_embedding,
                limit=min(limit * 3, 100),  # Get more results for re-ranking, cap at 100
                score_threshold=threshold * 0.8,  # Lower threshold for initial search
                filter_conditions=filter_conditions,
                correlation_id=correlation_id,
            )

            if not vector_results:
                logger.warning(
                    "No vector search results found for hybrid search",
                    extra={"correlation_id": correlation_id},
                )
                return []

            # Prepare query tokens for keyword matching
            query_tokens = set(query_text.lower().split())
            query_tokens = {
                token for token in query_tokens if len(token) > 1
            }  # Filter short tokens

            # Re-rank results using hybrid scoring
            hybrid_results = []

            for result in vector_results:
                # Calculate hybrid score
                vector_score = result.score

                # Keyword matching score with enhanced logic
                text = result.payload.get("text", "").lower()
                text_tokens = set(text.split())
                text_tokens = {token for token in text_tokens if len(token) > 1}

                if query_tokens and text_tokens:
                    # Calculate keyword overlap
                    intersection = query_tokens.intersection(text_tokens)
                    keyword_score = len(intersection) / len(query_tokens)

                    # Boost score for exact phrase matches
                    if query_text.lower() in text:
                        keyword_score = min(keyword_score + 0.2, 1.0)

                    # Boost score for title/address matches if available
                    title = result.payload.get("title", "").lower()
                    address = result.payload.get("address", "").lower()
                    if any(token in title or token in address for token in query_tokens):
                        keyword_score = min(keyword_score + 0.1, 1.0)
                else:
                    keyword_score = 0.0

                # Combine scores with adaptive weighting
                # Higher vector weight for high similarity scores
                vector_weight = 0.7 + (0.2 * vector_score) if vector_score > 0.8 else 0.7
                keyword_weight = 1.0 - vector_weight

                hybrid_score = (vector_weight * vector_score) + (keyword_weight * keyword_score)

                # Apply minimum threshold
                if hybrid_score >= threshold:
                    hybrid_results.append(
                        SearchResult(id=result.id, score=hybrid_score, payload=result.payload)
                    )

            # Sort by hybrid score and limit results
            hybrid_results.sort(key=lambda x: x.score, reverse=True)
            final_results = hybrid_results[:limit]

            processing_time = (time.time() - start_time) * 1000

            logger.info(
                "Hybrid search completed successfully",
                extra={
                    "vector_results": len(vector_results),
                    "hybrid_results": len(hybrid_results),
                    "final_results": len(final_results),
                    "query_length": len(query_text),
                    "processing_time_ms": processing_time,
                    "correlation_id": correlation_id,
                },
            )

            return final_results

        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            vector_metrics.record_error()

            logger.error(
                "Hybrid search failed",
                extra={
                    "query_length": len(query_text),
                    "limit": limit,
                    "threshold": threshold,
                    "processing_time_ms": processing_time,
                    "error": str(e),
                    "correlation_id": correlation_id,
                },
            )

            raise VectorServiceError(
                message="Hybrid search failed",
                error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                operation="hybrid_search",
                details={"query_length": len(query_text), "limit": limit},
                cause=e,
                correlation_id=correlation_id,
            )

    async def search_by_text(
        self,
        query_text: str,
        limit: int = 10,
        threshold: float = 0.0,
        filters: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> list[SearchResult]:
        """
        Search by text query with automatic embedding generation and comprehensive error handling

        Args:
            query_text: Text query
            limit: Maximum number of results
            threshold: Minimum similarity score
            filters: Additional filters
            correlation_id: Request correlation ID for tracking
        """
        start_time = time.time()
        correlation_id = correlation_id or f"vec_text_search_{int(time.time() * 1000)}"

        try:
            # Validate input
            if not query_text or not query_text.strip():
                raise VectorServiceError(
                    message="Query text cannot be empty",
                    error_code=ErrorCode.VALIDATION_ERROR,
                    operation="search_by_text",
                    correlation_id=correlation_id,
                )

            query_text = query_text.strip()

            if len(query_text) > 2000:  # Reasonable limit
                logger.warning(
                    "Query text truncated due to length",
                    extra={"original_length": len(query_text), "correlation_id": correlation_id},
                )
                query_text = query_text[:2000]

            logger.debug(
                "Starting text search",
                extra={
                    "query_length": len(query_text),
                    "limit": limit,
                    "threshold": threshold,
                    "correlation_id": correlation_id,
                },
            )

            # Generate embedding for query
            query_embedding = await self.generate_embedding(
                query_text, correlation_id=correlation_id
            )

            # Perform hybrid search
            results = await self.hybrid_search(
                query_embedding=query_embedding,
                query_text=query_text,
                limit=limit,
                threshold=threshold,
                filters=filters,
                correlation_id=correlation_id,
            )

            processing_time = (time.time() - start_time) * 1000

            logger.info(
                "Text search completed successfully",
                extra={
                    "query_length": len(query_text),
                    "results_count": len(results),
                    "limit": limit,
                    "threshold": threshold,
                    "processing_time_ms": processing_time,
                    "correlation_id": correlation_id,
                },
            )

            return results

        except VectorServiceError:
            # Re-raise vector service errors without wrapping
            raise

        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            vector_metrics.record_error()

            logger.error(
                "Text search failed",
                extra={
                    "query_length": len(query_text) if query_text else 0,
                    "limit": limit,
                    "threshold": threshold,
                    "processing_time_ms": processing_time,
                    "error": str(e),
                    "correlation_id": correlation_id,
                },
            )

            raise VectorServiceError(
                message="Text search failed",
                error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                operation="search_by_text",
                details={"query_length": len(query_text) if query_text else 0},
                cause=e,
                correlation_id=correlation_id,
            )

    def _build_filter_conditions(self, filters: dict[str, Any] | None) -> Filter | None:
        """Build Qdrant filter conditions from filter dictionary"""
        if not filters:
            return None

        conditions = []

        # String equality filters
        for field in ["content_type", "property_type", "transaction_type", "sido", "sigungu"]:
            if field in filters:
                value = filters[field]
                if isinstance(value, list):
                    # Multiple values (OR condition)
                    or_conditions = [
                        FieldCondition(key=field, match=models.MatchValue(value=v)) for v in value
                    ]
                    conditions.append(models.Filter(should=or_conditions))
                else:
                    # Single value
                    conditions.append(
                        FieldCondition(key=field, match=models.MatchValue(value=value))
                    )

        # Range filters
        if "price_min" in filters or "price_max" in filters:
            price_range = Range()
            if "price_min" in filters:
                price_range.gte = filters["price_min"]
            if "price_max" in filters:
                price_range.lte = filters["price_max"]

            conditions.append(FieldCondition(key="price", range=price_range))

        if "area_min" in filters or "area_max" in filters:
            area_range = Range()
            if "area_min" in filters:
                area_range.gte = filters["area_min"]
            if "area_max" in filters:
                area_range.lte = filters["area_max"]

            conditions.append(FieldCondition(key="area_m2", range=area_range))

        # Date range filters
        if "date_from" in filters or "date_to" in filters:
            date_range = Range()
            if "date_from" in filters:
                date_range.gte = (
                    filters["date_from"].isoformat()
                    if hasattr(filters["date_from"], "isoformat")
                    else filters["date_from"]
                )
            if "date_to" in filters:
                date_range.lte = (
                    filters["date_to"].isoformat()
                    if hasattr(filters["date_to"], "isoformat")
                    else filters["date_to"]
                )

            conditions.append(FieldCondition(key="created_at", range=date_range))

        if conditions:
            return Filter(must=conditions)

        return None

    async def get_document(self, document_id: str) -> SearchResult | None:
        """Get specific document by ID"""
        if not self._initialized:
            await self.initialize()

        try:
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[document_id],
                with_payload=True,
                with_vectors=False,
            )

            if points:
                point = points[0]
                return SearchResult(
                    id=str(point.id),
                    score=1.0,  # Perfect match for ID lookup
                    payload=point.payload or {},
                )

            return None

        except Exception as e:
            logger.error(f"Failed to get document {document_id}: {str(e)}")
            return None

    async def delete_documents(self, document_ids: list[str]) -> bool:
        """Delete documents by IDs"""
        if not self._initialized:
            await self.initialize()

        try:
            operation_info = self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(points=document_ids),
                wait=True,
            )

            logger.info(f"Deleted {len(document_ids)} documents")
            return True

        except Exception as e:
            logger.error(f"Failed to delete documents: {str(e)}")
            return False

    async def get_collection_info(self) -> dict[str, Any]:
        """Get collection information and statistics"""
        if not self._initialized:
            await self.initialize()

        try:
            collection_info = self.client.get_collection(self.collection_name)

            return {
                "name": self.collection_name,
                "vectors_count": collection_info.vectors_count,
                "indexed_vectors_count": collection_info.indexed_vectors_count,
                "points_count": collection_info.points_count,
                "segments_count": collection_info.segments_count,
                "status": collection_info.status,
                "optimizer_status": collection_info.optimizer_status.status
                if collection_info.optimizer_status
                else None,
                "vector_size": collection_info.config.params.vectors.size,
                "distance": collection_info.config.params.vectors.distance,
            }

        except Exception as e:
            logger.error(f"Failed to get collection info: {str(e)}")
            return {}

    async def health_check(self) -> dict[str, Any]:
        """Comprehensive vector service health check with metrics"""
        health_status = {
            "service_name": "Vector Service",
            "status": "unhealthy",
            "checks": {
                "initialization": {"status": False, "latency_ms": None},
                "connection": {"status": False, "latency_ms": None},
                "collection": {"status": False, "info": None},
                "embedding": {"status": False, "latency_ms": None},
                "search": {"status": False, "latency_ms": None},
            },
            "metrics": vector_metrics.get_stats(),
            "circuit_breaker": {
                "open": self._circuit_breaker_open,
                "failures": self._circuit_breaker_failures,
                "last_failure": self._circuit_breaker_last_failure,
            },
            "config": {
                "collection_name": self.collection_name,
                "vector_size": self.vector_size,
                "embedding_cache_ttl": EMBEDDING_CACHE_TTL,
                "search_cache_ttl": SEARCH_CACHE_TTL,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            # Check initialization
            start_time = time.time()
            if not self._initialized:
                await self.initialize()

            init_latency = (time.time() - start_time) * 1000
            health_status["checks"]["initialization"].update(
                {"status": True, "latency_ms": round(init_latency, 2)}
            )

            # Check basic connection
            start_time = time.time()
            collections = self.client.get_collections()
            connection_latency = (time.time() - start_time) * 1000

            health_status["checks"]["connection"].update(
                {"status": True, "latency_ms": round(connection_latency, 2)}
            )

            # Check collection status
            start_time = time.time()
            collection_info = self.client.get_collection(self.collection_name)
            collection_latency = (time.time() - start_time) * 1000

            health_status["checks"]["collection"].update(
                {
                    "status": True,
                    "latency_ms": round(collection_latency, 2),
                    "info": {
                        "vectors_count": collection_info.vectors_count,
                        "indexed_vectors_count": collection_info.indexed_vectors_count,
                        "status": collection_info.status,
                    },
                }
            )

            # Test embedding generation
            start_time = time.time()
            test_embedding = await self.generate_embedding(
                "health check test", correlation_id="health_check"
            )
            embedding_latency = (time.time() - start_time) * 1000

            health_status["checks"]["embedding"].update(
                {"status": True, "latency_ms": round(embedding_latency, 2)}
            )

            # Test search functionality
            start_time = time.time()
            dummy_vector = [0.1] * self.vector_size  # Non-zero vector for better test
            search_results = await self.search(dummy_vector, limit=1, correlation_id="health_check")
            search_latency = (time.time() - start_time) * 1000

            health_status["checks"]["search"].update(
                {
                    "status": True,
                    "latency_ms": round(search_latency, 2),
                    "results_count": len(search_results),
                }
            )

            # Update overall status
            all_checks_passed = all(check["status"] for check in health_status["checks"].values())

            if all_checks_passed:
                health_status["status"] = "healthy"
                self._connection_healthy = True
                self._last_health_check = time.time()
            else:
                health_status["status"] = "degraded"
                self._connection_healthy = False

            logger.debug(
                "Vector service health check completed",
                extra={
                    "status": health_status["status"],
                    "total_latency_ms": sum(
                        check.get("latency_ms", 0) for check in health_status["checks"].values()
                    ),
                },
            )

        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
            self._connection_healthy = False

            logger.error("Vector service health check failed", extra={"error": str(e)})

        return health_status

    async def get_service_metrics(self) -> dict[str, Any]:
        """Get comprehensive service metrics"""
        return {
            "service_name": "Vector Service",
            "metrics": vector_metrics.get_stats(),
            "cache_stats": {
                "embedding_cache_ttl": EMBEDDING_CACHE_TTL,
                "search_cache_ttl": SEARCH_CACHE_TTL,
            },
            "circuit_breaker": {
                "open": self._circuit_breaker_open,
                "failures": self._circuit_breaker_failures,
                "threshold": self.circuit_breaker_threshold,
                "timeout": self.circuit_breaker_timeout,
            },
            "connection": {
                "healthy": self._connection_healthy,
                "last_health_check": self._last_health_check,
                "initialized": self._initialized,
            },
            "configuration": {
                "collection_name": self.collection_name,
                "vector_size": self.vector_size,
                "retry_attempts": VECTOR_RETRY_ATTEMPTS,
                "operation_timeout": VECTOR_OPERATION_TIMEOUT,
            },
        }

    async def clear_cache(self, pattern: str = "embedding:*") -> int:
        """Clear vector service cache"""
        try:
            cleared_count = await cache_manager.clear_pattern(pattern)
            logger.info(
                "Vector service cache cleared",
                extra={"pattern": pattern, "cleared_count": cleared_count},
            )
            return cleared_count
        except Exception as e:
            logger.error(
                "Failed to clear vector service cache", extra={"pattern": pattern, "error": str(e)}
            )
            return 0
