"""
Chromadb Service for Korean Real Estate RAG AI Chatbot
Handles Chromadb vector database operations with enterprise-grade reliability
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
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from core.config import settings
from core.database import cache_manager
from core.exceptions import ErrorCode, VectorServiceError

logger = logging.getLogger(__name__)

# Chromadb service configuration
CHROMADB_RETRY_ATTEMPTS = 3
CHROMADB_RETRY_WAIT_MIN = 1
CHROMADB_RETRY_WAIT_MAX = 8
CHROMADB_OPERATION_TIMEOUT = 30  # 30 seconds


@dataclass
class ChromaSearchResult:
    """Chromadb search result"""

    id: str
    score: float
    metadata: dict[str, Any]
    document: str | None = None


class ChromadbService:
    """Chromadb vector service with enterprise-grade reliability"""

    def __init__(self):
        self.client = None
        self.collection = None
        self.collection_name = settings.CHROMADB_COLLECTION_NAME
        self._initialized = False
        self._connection_healthy = False
        self._circuit_breaker_failures = 0
        self._circuit_breaker_open = False
        self._circuit_breaker_last_failure = 0

        # Circuit breaker configuration
        self.circuit_breaker_threshold = 5  # failures
        self.circuit_breaker_timeout = 60  # seconds

        logger.info(
            "ChromadbService initialized",
            extra={
                "collection_name": self.collection_name,
                "host": settings.CHROMADB_HOST,
                "port": settings.CHROMADB_PORT,
            },
        )

    @retry(
        stop=stop_after_attempt(CHROMADB_RETRY_ATTEMPTS),
        wait=wait_exponential(
            multiplier=1, min=CHROMADB_RETRY_WAIT_MIN, max=CHROMADB_RETRY_WAIT_MAX
        ),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    )
    async def initialize(self):
        """Initialize Chromadb client and collection with retry logic"""
        if self._initialized:
            return

        correlation_id = f"chroma_init_{int(time.time() * 1000)}"

        try:
            logger.info(
                "Initializing Chromadb vector service", extra={"correlation_id": correlation_id}
            )

            # Import chromadb (lazy import for better error handling)
            try:
                import chromadb
                from chromadb.config import Settings as ChromaSettings
            except ImportError as e:
                logger.error(
                    "Chromadb not installed. Install with: pip install chromadb",
                    extra={"correlation_id": correlation_id},
                )
                raise VectorServiceError(
                    message="Chromadb not available - please install chromadb package",
                    error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                    operation="initialize",
                    cause=e,
                    correlation_id=correlation_id,
                )

            # Initialize Chromadb client
            if settings.CHROMADB_HOST == "localhost":
                # Local persistent client
                self.client = chromadb.PersistentClient(path="./chromadb_data")
            else:
                # Remote client
                self.client = chromadb.HttpClient(
                    host=settings.CHROMADB_HOST,
                    port=settings.CHROMADB_PORT,
                    settings=ChromaSettings(
                        chroma_client_auth_provider="chromadb.auth.basic.BasicAuthClientProvider",
                        chroma_client_auth_credentials_provider="chromadb.auth.basic.BasicAuthCredentialsProvider",
                    ),
                )

            # Get or create collection
            try:
                self.collection = self.client.get_collection(name=self.collection_name)
                logger.info(
                    "Using existing Chromadb collection",
                    extra={
                        "collection_name": self.collection_name,
                        "count": self.collection.count(),
                        "correlation_id": correlation_id,
                    },
                )
            except Exception:
                # Collection doesn't exist, create it
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={
                        "description": "Korean Real Estate RAG AI Chatbot vectors",
                        "created_at": datetime.utcnow().isoformat(),
                    },
                )
                logger.info(
                    "Created new Chromadb collection",
                    extra={
                        "collection_name": self.collection_name,
                        "correlation_id": correlation_id,
                    },
                )

            self._initialized = True
            self._connection_healthy = True
            self._circuit_breaker_failures = 0
            self._circuit_breaker_open = False

            logger.info(
                "Chromadb vector service initialized successfully",
                extra={
                    "collection_name": self.collection_name,
                    "documents_count": self.collection.count(),
                    "correlation_id": correlation_id,
                },
            )

        except Exception as e:
            logger.error(
                "Failed to initialize Chromadb client",
                extra={"error": str(e), "correlation_id": correlation_id},
            )

            raise VectorServiceError(
                message="Chromadb service initialization failed",
                error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                operation="initialize",
                cause=e,
                correlation_id=correlation_id,
            )

    async def add_documents(self, documents: list[dict[str, Any]], batch_size: int = 100) -> bool:
        """
        Add documents to Chromadb

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

                ids = []
                documents_text = []
                metadatas = []

                for doc in batch:
                    text = doc.get("text", "")
                    if not text:
                        logger.warning(
                            f"Skipping document without text: {doc.get('id', 'unknown')}"
                        )
                        continue

                    doc_id = doc.get("id", str(uuid.uuid4()))
                    metadata = {
                        "content_type": doc.get("content_type", "unknown"),
                        "created_at": doc.get("created_at", datetime.utcnow().isoformat()),
                        **doc.get("metadata", {}),
                    }

                    ids.append(doc_id)
                    documents_text.append(text)
                    metadatas.append(metadata)

                if ids and documents_text:
                    # Add batch to Chromadb
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.collection.add(
                            ids=ids, documents=documents_text, metadatas=metadatas
                        ),
                    )

                    logger.info(
                        f"Uploaded batch {i//batch_size + 1}/{(total_docs + batch_size - 1)//batch_size} "
                        f"({len(ids)} documents)"
                    )

            logger.info(f"Successfully added {total_docs} documents to Chromadb")
            return True

        except Exception as e:
            logger.error(f"Failed to add documents to Chromadb: {str(e)}")
            return False

    async def search(
        self,
        query_texts: list[str],
        limit: int = 10,
        where: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> list[ChromaSearchResult]:
        """
        Perform text-based similarity search in Chromadb

        Args:
            query_texts: List of query texts
            limit: Maximum number of results per query
            where: Filter conditions
            correlation_id: Request correlation ID for tracking
        """
        start_time = time.time()
        correlation_id = correlation_id or f"chroma_search_{int(time.time() * 1000)}"

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
                        message="Chromadb search circuit breaker is open",
                        error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                        operation="search",
                        correlation_id=correlation_id,
                    )

            # Perform search
            results = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.collection.query(
                    query_texts=query_texts, n_results=limit, where=where
                ),
            )

            # Convert results to ChromaSearchResult objects
            search_results = []

            if results and "ids" in results:
                for i in range(len(query_texts)):
                    if i < len(results["ids"]):
                        ids = results["ids"][i]
                        distances = (
                            results["distances"][i] if "distances" in results else [0.0] * len(ids)
                        )
                        metadatas = (
                            results["metadatas"][i] if "metadatas" in results else [{}] * len(ids)
                        )
                        documents = (
                            results["documents"][i] if "documents" in results else [None] * len(ids)
                        )

                        for j, doc_id in enumerate(ids):
                            # Convert distance to similarity score (1 - normalized_distance)
                            score = max(0.0, 1.0 - distances[j]) if j < len(distances) else 0.0
                            metadata = metadatas[j] if j < len(metadatas) else {}
                            document = documents[j] if j < len(documents) else None

                            search_results.append(
                                ChromaSearchResult(
                                    id=doc_id, score=score, metadata=metadata, document=document
                                )
                            )

            processing_time = (time.time() - start_time) * 1000

            logger.info(
                "Chromadb search completed successfully",
                extra={
                    "query_count": len(query_texts),
                    "results_count": len(search_results),
                    "limit": limit,
                    "processing_time_ms": processing_time,
                    "correlation_id": correlation_id,
                },
            )

            # Reset circuit breaker on success
            self._circuit_breaker_failures = min(self._circuit_breaker_failures, 0)

            return search_results

        except Exception as e:
            processing_time = (time.time() - start_time) * 1000

            # Update circuit breaker
            self._circuit_breaker_failures += 1
            self._circuit_breaker_last_failure = time.time()

            if self._circuit_breaker_failures >= self.circuit_breaker_threshold:
                self._circuit_breaker_open = True
                logger.warning(
                    "Circuit breaker opened for Chromadb search",
                    extra={
                        "failures": self._circuit_breaker_failures,
                        "correlation_id": correlation_id,
                    },
                )

            logger.error(
                "Chromadb search failed",
                extra={
                    "query_count": len(query_texts),
                    "limit": limit,
                    "processing_time_ms": processing_time,
                    "error": str(e),
                    "correlation_id": correlation_id,
                },
            )

            raise VectorServiceError(
                message="Chromadb search failed",
                error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                operation="search",
                details={"query_count": len(query_texts), "limit": limit},
                cause=e,
                correlation_id=correlation_id,
            )

    async def delete_documents(self, document_ids: list[str]) -> bool:
        """Delete documents by IDs"""
        if not self._initialized:
            await self.initialize()

        try:
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.collection.delete(ids=document_ids)
            )

            logger.info(f"Deleted {len(document_ids)} documents from Chromadb")
            return True

        except Exception as e:
            logger.error(f"Failed to delete documents from Chromadb: {str(e)}")
            return False

    async def get_collection_info(self) -> dict[str, Any]:
        """Get collection information and statistics"""
        if not self._initialized:
            await self.initialize()

        try:
            count = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.collection.count()
            )

            return {
                "name": self.collection_name,
                "documents_count": count,
                "type": "chromadb",
                "host": settings.CHROMADB_HOST,
                "port": settings.CHROMADB_PORT,
            }

        except Exception as e:
            logger.error(f"Failed to get Chromadb collection info: {str(e)}")
            return {}

    async def health_check(self) -> dict[str, Any]:
        """Comprehensive Chromadb service health check"""
        health_status = {
            "service_name": "Chromadb Service",
            "status": "unhealthy",
            "checks": {
                "initialization": {"status": False, "latency_ms": None},
                "connection": {"status": False, "latency_ms": None},
                "collection": {"status": False, "info": None},
                "search": {"status": False, "latency_ms": None},
            },
            "circuit_breaker": {
                "open": self._circuit_breaker_open,
                "failures": self._circuit_breaker_failures,
                "last_failure": self._circuit_breaker_last_failure,
            },
            "config": {
                "collection_name": self.collection_name,
                "host": settings.CHROMADB_HOST,
                "port": settings.CHROMADB_PORT,
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

            # Check collection status
            start_time = time.time()
            collection_info = await self.get_collection_info()
            collection_latency = (time.time() - start_time) * 1000

            health_status["checks"]["collection"].update(
                {
                    "status": True,
                    "latency_ms": round(collection_latency, 2),
                    "info": collection_info,
                }
            )

            # Test search functionality
            start_time = time.time()
            test_results = await self.search(
                query_texts=["health check test"], limit=1, correlation_id="health_check"
            )
            search_latency = (time.time() - start_time) * 1000

            health_status["checks"]["search"].update(
                {
                    "status": True,
                    "latency_ms": round(search_latency, 2),
                    "results_count": len(test_results),
                }
            )

            # Update overall status
            all_checks_passed = all(check["status"] for check in health_status["checks"].values())

            if all_checks_passed:
                health_status["status"] = "healthy"
                self._connection_healthy = True
            else:
                health_status["status"] = "degraded"
                self._connection_healthy = False

            logger.debug(
                "Chromadb service health check completed", extra={"status": health_status["status"]}
            )

        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
            self._connection_healthy = False

            logger.error("Chromadb service health check failed", extra={"error": str(e)})

        return health_status

    async def add_simple_document(self, text: str, metadata: dict[str, Any] = None) -> str:
        """
        간단한 문서 하나를 ChromaDB에 추가
        
        Args:
            text: 문서 내용 (문자열)
            metadata: 메타데이터 (선택사항)
            
        Returns:
            str: 생성된 문서 ID
        """
        if not self._initialized:
            await self.initialize()
            
        try:
            doc_id = str(uuid.uuid4())
            doc_metadata = {
                'content_type': 'text',
                'created_at': datetime.utcnow().isoformat(),
                **(metadata or {})
            }
            
            # ChromaDB에 문서 추가
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.collection.add(
                    ids=[doc_id],
                    documents=[text],
                    metadatas=[doc_metadata]
                )
            )
            
            logger.info(f'문서 추가 성공: {doc_id}')
            return doc_id
            
        except Exception as e:
            logger.error(f'문서 추가 실패: {str(e)}')
            raise VectorServiceError(
                error_code=ErrorCode.VECTOR_OPERATION_FAILED,
                message=f'Failed to add document: {str(e)}',
                correlation_id=str(uuid.uuid4())
            )
    
    async def add_multiple_documents(self, documents: list[dict[str, Any]]) -> list[str]:
        """
        여러 문서를 ChromaDB에 추가
        
        Args:
            documents: 문서 리스트 [{'text': '내용', 'metadata': {...}}, ...]
            
        Returns:
            list[str]: 생성된 문서 ID 리스트
        """
        if not self._initialized:
            await self.initialize()
            
        try:
            ids = []
            documents_text = []
            metadatas = []
            
            for doc in documents:
                doc_id = str(uuid.uuid4())
                text = doc.get('text', '')
                metadata = {
                    'content_type': doc.get('content_type', 'text'),
                    'created_at': datetime.utcnow().isoformat(),
                    **doc.get('metadata', {})
                }
                
                if not text:
                    logger.warning(f'텍스트가 없는 문서 건너뜀: {doc_id}')
                    continue
                    
                ids.append(doc_id)
                documents_text.append(text)
                metadatas.append(metadata)
            
            if ids:
                # ChromaDB에 배치로 추가
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.collection.add(
                        ids=ids,
                        documents=documents_text,
                        metadatas=metadatas
                    )
                )
                
                logger.info(f'{len(ids)}개 문서 추가 성공')
                return ids
            else:
                logger.warning('추가할 유효한 문서가 없음')
                return []
                
        except Exception as e:
            logger.error(f'여러 문서 추가 실패: {str(e)}')
            raise VectorServiceError(
                error_code=ErrorCode.VECTOR_OPERATION_FAILED,
                message=f'Failed to add multiple documents: {str(e)}',
                correlation_id=str(uuid.uuid4())
            )
    
    async def search_documents(self, query: str, limit: int = 5) -> list[ChromaSearchResult]:
        """
        문서 검색
        
        Args:
            query: 검색 쿼리
            limit: 결과 개수
            
        Returns:
            list[ChromaSearchResult]: 검색 결과
        """
        if not self._initialized:
            await self.initialize()
            
        try:
            # ChromaDB에서 검색
            results = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.collection.query(
                    query_texts=[query],
                    n_results=limit
                )
            )
            
            search_results = []
            if results['ids'] and results['ids'][0]:
                for i, doc_id in enumerate(results['ids'][0]):
                    search_results.append(ChromaSearchResult(
                        id=doc_id,
                        score=results['distances'][0][i] if results['distances'] else 0.0,
                        metadata=results['metadatas'][0][i] if results['metadatas'] else {},
                        document=results['documents'][0][i] if results['documents'] else None
                    ))
            
            logger.info(f'검색 완료: {len(search_results)}개 결과')
            return search_results
            
        except Exception as e:
            logger.error(f'문서 검색 실패: {str(e)}')
            raise VectorServiceError(
                error_code=ErrorCode.VECTOR_OPERATION_FAILED,
                message=f'Failed to search documents: {str(e)}',
                correlation_id=str(uuid.uuid4())
            )
    
    async def get_document_count(self) -> int:
        """
        저장된 문서 개수 조회
        
        Returns:
            int: 문서 개수
        """
        if not self._initialized:
            await self.initialize()
            
        try:
            count = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.collection.count()
            )
            return count
            
        except Exception as e:
            logger.error(f'문서 개수 조회 실패: {str(e)}')
            return 0
