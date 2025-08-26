"""
Hybrid Vector Service for Korean Real Estate RAG AI Chatbot
Manages both Chromadb (primary) and Qdrant (legacy) with seamless failover
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..core.config import settings
from ..core.exceptions import ErrorCode, VectorServiceError
from .chromadb_service import ChromadbService, ChromaSearchResult
from .vector_service import SearchResult, VectorService

logger = logging.getLogger(__name__)


@dataclass
class HybridSearchResult:
    """Unified search result from hybrid vector service"""

    id: str
    score: float
    payload: dict[str, Any]
    source: str  # 'chromadb' or 'qdrant'
    document: str | None = None


class HybridVectorService:
    """
    Hybrid vector service that manages both Chromadb (primary) and Qdrant (fallback)
    Provides seamless switching and failover capabilities
    """

    def __init__(self):
        # Initialize services based on configuration
        self.chromadb_service = None
        self.qdrant_service = None

        # Primary vector database based on architecture
        self.primary_service = "chromadb"  # Per README architecture
        self.fallback_service = "qdrant"

        # Service availability tracking
        self._chromadb_available = False
        self._qdrant_available = False
        self._initialized = False

        # Configuration
        self.max_initialization_retries = 3
        self.service_timeout = 30  # seconds

        logger.info(
            "HybridVectorService initialized",
            extra={
                "primary_service": self.primary_service,
                "fallback_service": self.fallback_service,
            },
        )

    async def initialize(self):
        """Initialize available vector services"""
        if self._initialized:
            return

        correlation_id = f"hybrid_init_{int(time.time() * 1000)}"

        logger.info("Initializing hybrid vector service", extra={"correlation_id": correlation_id})

        # Initialize Chromadb service
        try:
            self.chromadb_service = ChromadbService()
            await self.chromadb_service.initialize()
            self._chromadb_available = True

            logger.info(
                "Chromadb service initialized successfully",
                extra={"correlation_id": correlation_id},
            )
        except Exception as e:
            logger.warning(
                "Failed to initialize Chromadb service",
                extra={"error": str(e), "correlation_id": correlation_id},
            )
            self._chromadb_available = False

        # Initialize Qdrant service (if configured)
        if settings.QDRANT_URL and settings.QDRANT_API_KEY:
            try:
                self.qdrant_service = VectorService()
                await self.qdrant_service.initialize()
                self._qdrant_available = True

                logger.info(
                    "Qdrant service initialized successfully",
                    extra={"correlation_id": correlation_id},
                )
            except Exception as e:
                logger.warning(
                    "Failed to initialize Qdrant service",
                    extra={"error": str(e), "correlation_id": correlation_id},
                )
                self._qdrant_available = False
        else:
            logger.info(
                "Qdrant service not configured, skipping initialization",
                extra={"correlation_id": correlation_id},
            )

        # Verify at least one service is available
        if not self._chromadb_available and not self._qdrant_available:
            raise VectorServiceError(
                message="No vector services available",
                error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                operation="initialize",
                details={
                    "chromadb_available": self._chromadb_available,
                    "qdrant_available": self._qdrant_available,
                },
                correlation_id=correlation_id,
            )

        self._initialized = True

        logger.info(
            "Hybrid vector service initialized successfully",
            extra={
                "chromadb_available": self._chromadb_available,
                "qdrant_available": self._qdrant_available,
                "correlation_id": correlation_id,
            },
        )

    def _get_primary_service(self):
        """Get the primary vector service based on availability"""
        if self.primary_service == "chromadb" and self._chromadb_available:
            return self.chromadb_service, "chromadb"
        elif self.primary_service == "qdrant" and self._qdrant_available:
            return self.qdrant_service, "qdrant"

        # Fallback to any available service
        if self._chromadb_available:
            return self.chromadb_service, "chromadb"
        elif self._qdrant_available:
            return self.qdrant_service, "qdrant"

        return None, None

    def _get_fallback_service(self, primary_service_name: str):
        """Get fallback service when primary fails"""
        if primary_service_name == "chromadb" and self._qdrant_available:
            return self.qdrant_service, "qdrant"
        elif primary_service_name == "qdrant" and self._chromadb_available:
            return self.chromadb_service, "chromadb"

        return None, None

    async def search_by_text(
        self,
        query_text: str,
        limit: int = 10,
        threshold: float = 0.0,
        filters: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> list[HybridSearchResult]:
        """
        Search by text using the best available vector service
        """
        if not self._initialized:
            await self.initialize()

        correlation_id = correlation_id or f"hybrid_search_{int(time.time() * 1000)}"
        start_time = time.time()

        # Get primary service
        primary_service, primary_name = self._get_primary_service()

        if not primary_service:
            raise VectorServiceError(
                message="No vector services available for search",
                error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                operation="search_by_text",
                correlation_id=correlation_id,
            )

        try:
            # Try primary service
            logger.debug(
                f"Using {primary_name} for text search",
                extra={"query_length": len(query_text), "correlation_id": correlation_id},
            )

            if primary_name == "chromadb":
                results = await primary_service.search(
                    query_texts=[query_text],
                    limit=limit,
                    where=self._convert_filters_for_chromadb(filters),
                    correlation_id=correlation_id,
                )

                # Convert Chromadb results to hybrid format
                hybrid_results = [
                    HybridSearchResult(
                        id=result.id,
                        score=result.score,
                        payload=result.metadata,
                        source="chromadb",
                        document=result.document,
                    )
                    for result in results
                    if result.score >= threshold
                ]

            else:  # qdrant
                results = await primary_service.search_by_text(
                    query_text=query_text,
                    limit=limit,
                    threshold=threshold,
                    filters=filters,
                    correlation_id=correlation_id,
                )

                # Convert Qdrant results to hybrid format
                hybrid_results = [
                    HybridSearchResult(
                        id=result.id,
                        score=result.score,
                        payload=result.payload,
                        source="qdrant",
                        document=result.payload.get("text"),
                    )
                    for result in results
                ]

            processing_time = (time.time() - start_time) * 1000

            logger.info(
                "Hybrid text search completed successfully",
                extra={
                    "service_used": primary_name,
                    "query_length": len(query_text),
                    "results_count": len(hybrid_results),
                    "processing_time_ms": processing_time,
                    "correlation_id": correlation_id,
                },
            )

            return hybrid_results

        except Exception as e:
            # Try fallback service
            fallback_service, fallback_name = self._get_fallback_service(primary_name)

            if fallback_service:
                logger.warning(
                    f"{primary_name} search failed, trying {fallback_name}",
                    extra={"primary_error": str(e), "correlation_id": correlation_id},
                )

                try:
                    if fallback_name == "chromadb":
                        results = await fallback_service.search(
                            query_texts=[query_text],
                            limit=limit,
                            where=self._convert_filters_for_chromadb(filters),
                            correlation_id=correlation_id,
                        )

                        hybrid_results = [
                            HybridSearchResult(
                                id=result.id,
                                score=result.score,
                                payload=result.metadata,
                                source="chromadb",
                                document=result.document,
                            )
                            for result in results
                            if result.score >= threshold
                        ]

                    else:  # qdrant
                        results = await fallback_service.search_by_text(
                            query_text=query_text,
                            limit=limit,
                            threshold=threshold,
                            filters=filters,
                            correlation_id=correlation_id,
                        )

                        hybrid_results = [
                            HybridSearchResult(
                                id=result.id,
                                score=result.score,
                                payload=result.payload,
                                source="qdrant",
                                document=result.payload.get("text"),
                            )
                            for result in results
                        ]

                    processing_time = (time.time() - start_time) * 1000

                    logger.info(
                        "Hybrid text search completed with fallback",
                        extra={
                            "service_used": fallback_name,
                            "results_count": len(hybrid_results),
                            "processing_time_ms": processing_time,
                            "correlation_id": correlation_id,
                        },
                    )

                    return hybrid_results

                except Exception as fallback_error:
                    logger.error(
                        "Both primary and fallback services failed",
                        extra={
                            "primary_service": primary_name,
                            "primary_error": str(e),
                            "fallback_service": fallback_name,
                            "fallback_error": str(fallback_error),
                            "correlation_id": correlation_id,
                        },
                    )

            # All services failed
            processing_time = (time.time() - start_time) * 1000

            raise VectorServiceError(
                message="All vector services failed",
                error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                operation="search_by_text",
                details={
                    "primary_service": primary_name,
                    "primary_error": str(e),
                    "processing_time_ms": processing_time,
                },
                cause=e,
                correlation_id=correlation_id,
            )

    async def add_documents(
        self, documents: list[dict[str, Any]], batch_size: int = 100
    ) -> dict[str, bool]:
        """
        Add documents to all available vector services
        """
        if not self._initialized:
            await self.initialize()

        results = {}

        # Add to Chromadb if available
        if self._chromadb_available and self.chromadb_service:
            try:
                chromadb_success = await self.chromadb_service.add_documents(
                    documents=documents, batch_size=batch_size
                )
                results["chromadb"] = chromadb_success
            except Exception as e:
                logger.error(f"Failed to add documents to Chromadb: {str(e)}")
                results["chromadb"] = False

        # Add to Qdrant if available
        if self._qdrant_available and self.qdrant_service:
            try:
                qdrant_success = await self.qdrant_service.add_documents(
                    documents=documents, batch_size=batch_size
                )
                results["qdrant"] = qdrant_success
            except Exception as e:
                logger.error(f"Failed to add documents to Qdrant: {str(e)}")
                results["qdrant"] = False

        return results

    def _convert_filters_for_chromadb(
        self, filters: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        """Convert generic filters to Chromadb format"""
        if not filters:
            return None

        # Simple conversion for now - Chromadb uses where clause format
        chromadb_filters = {}

        # Direct mappings for string fields
        for field in ["content_type", "property_type", "transaction_type", "sido", "sigungu"]:
            if field in filters:
                chromadb_filters[field] = filters[field]

        # Range filters need special handling in Chromadb
        # For now, we'll skip complex range filters and implement them as needed

        return chromadb_filters if chromadb_filters else None

    async def health_check(self) -> dict[str, Any]:
        """Comprehensive health check for hybrid vector service"""
        health_status = {
            "service_name": "Hybrid Vector Service",
            "status": "unhealthy",
            "services": {},
            "primary_service": self.primary_service,
            "fallback_service": self.fallback_service,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Check Chromadb service
        if self.chromadb_service:
            try:
                chromadb_health = await self.chromadb_service.health_check()
                health_status["services"]["chromadb"] = chromadb_health
                self._chromadb_available = chromadb_health["status"] == "healthy"
            except Exception as e:
                health_status["services"]["chromadb"] = {"status": "unhealthy", "error": str(e)}
                self._chromadb_available = False

        # Check Qdrant service
        if self.qdrant_service:
            try:
                qdrant_health = await self.qdrant_service.health_check()
                health_status["services"]["qdrant"] = qdrant_health
                self._qdrant_available = qdrant_health["status"] == "healthy"
            except Exception as e:
                health_status["services"]["qdrant"] = {"status": "unhealthy", "error": str(e)}
                self._qdrant_available = False

        # Determine overall health
        available_services = sum(
            [1 for available in [self._chromadb_available, self._qdrant_available] if available]
        )

        if available_services >= 1:
            health_status["status"] = "healthy"
        elif available_services > 0:
            health_status["status"] = "degraded"
        else:
            health_status["status"] = "unhealthy"

        health_status["availability"] = {
            "chromadb": self._chromadb_available,
            "qdrant": self._qdrant_available,
            "total_available": available_services,
        }

        return health_status

    async def get_collection_info(self) -> dict[str, Any]:
        """Get information from all available vector databases"""
        info = {"hybrid_service": True, "primary_service": self.primary_service, "collections": {}}

        # Get Chromadb info
        if self._chromadb_available and self.chromadb_service:
            try:
                chromadb_info = await self.chromadb_service.get_collection_info()
                info["collections"]["chromadb"] = chromadb_info
            except Exception as e:
                info["collections"]["chromadb"] = {"error": str(e)}

        # Get Qdrant info
        if self._qdrant_available and self.qdrant_service:
            try:
                qdrant_info = await self.qdrant_service.get_collection_info()
                info["collections"]["qdrant"] = qdrant_info
            except Exception as e:
                info["collections"]["qdrant"] = {"error": str(e)}

        return info
