"""
AWS OpenSearch vector service for Korean Real Estate RAG chatbot.

Provides resilient indexing and similarity search using the OpenSearch k-NN
engine. Embeddings are generated through AWS Bedrock Titan to keep parity with
the LightRAG pipeline.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from core.config import settings
from core.exceptions import ErrorCode, VectorServiceError

logger = logging.getLogger(__name__)


@dataclass
class OpenSearchVectorResult:
    """Container for OpenSearch vector search results."""

    id: str
    score: float
    metadata: dict[str, Any]
    document: str | None = None


class OpenSearchVectorService:
    """High-availability vector service backed by AWS OpenSearch k-NN."""

    def __init__(self) -> None:
        self._client = None
        self._bulk_helper = None
        self._opensearch_exceptions = None
        self._index_name = settings.OPENSEARCH_INDEX_NAME
        self._text_field = settings.OPENSEARCH_TEXT_FIELD
        self._vector_field = settings.OPENSEARCH_VECTOR_FIELD
        self._metadata_field = settings.OPENSEARCH_METADATA_FIELD
        self._vector_dim = settings.VECTOR_SIZE

        self._initialized = False
        self._initializing_lock = asyncio.Lock()

        # Circuit breaker metadata
        self._circuit_breaker_failures = 0
        self._circuit_breaker_last_failure = 0.0
        self._circuit_breaker_open = False
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_timeout = 60

        # Bedrock embedding client (lazy)
        self._bedrock_client = None
        self._embedding_model_id = settings.BEDROCK_EMBEDDING_MODEL_ID

        logger.info(
            "OpenSearchVectorService configured",
            extra={"index": self._index_name, "host": settings.OPENSEARCH_HOST},
        )

    async def initialize(self) -> None:
        """Initialise OpenSearch client and ensure k-NN index exists."""
        if self._initialized:
            return

        async with self._initializing_lock:
            if self._initialized:
                return

            try:
                from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection
                from opensearchpy import exceptions as opensearch_exceptions
                from opensearchpy.helpers import bulk
            except ImportError as exc:  # pragma: no cover - handled at runtime
                raise VectorServiceError(
                    message=(
                        "opensearch-py is not installed. "
                        "Install with `uv add opensearch-py` or `pip install opensearch-py`."
                    ),
                    error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                    operation="initialize",
                    cause=exc,
                ) from exc

            # Store helpers for later usage
            self._bulk_helper = bulk
            self._opensearch_exceptions = opensearch_exceptions

            # Build authentication
            http_auth = None
            connection_class = RequestsHttpConnection

            if settings.OPENSEARCH_AUTH_MODE == "sigv4":
                try:
                    import boto3
                except ImportError as exc:  # pragma: no cover - boto3 should be available
                    raise VectorServiceError(
                        message="boto3 is required for SigV4 authentication with OpenSearch",
                        error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                        operation="initialize",
                        cause=exc,
                    ) from exc

                session = boto3.Session(
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.get_secret_value("AWS_SECRET_ACCESS_KEY"),
                    region_name=settings.AWS_REGION,
                )
                credentials = session.get_credentials()
                if credentials is None:
                    raise VectorServiceError(
                        message="Failed to obtain AWS credentials for OpenSearch SigV4 auth",
                        error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                        operation="initialize",
                    )

                http_auth = AWSV4SignerAuth(credentials, settings.AWS_REGION, service="es")
            elif settings.OPENSEARCH_AUTH_MODE == "basic":
                username = settings.OPENSEARCH_USERNAME
                password = settings.OPENSEARCH_PASSWORD
                if not username or password is None:
                    raise VectorServiceError(
                        message="Basic auth requires OPENSEARCH_USERNAME and OPENSEARCH_PASSWORD",
                        error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                        operation="initialize",
                    )
                http_auth = (
                    username,
                    password.get_secret_value() if hasattr(password, "get_secret_value") else str(password),
                )

            # Create OpenSearch client
            hosts = [{"host": settings.OPENSEARCH_HOST, "port": settings.OPENSEARCH_PORT}]
            try:
                self._client = OpenSearch(
                    hosts=hosts,
                    http_auth=http_auth,
                    use_ssl=settings.OPENSEARCH_USE_SSL,
                    verify_certs=settings.OPENSEARCH_VERIFY_CERTS,
                    connection_class=connection_class,
                    timeout=30,
                    max_retries=3,
                    retry_on_timeout=True,
                )
            except Exception as exc:  # pragma: no cover - depends on runtime environment
                raise VectorServiceError(
                    message=f"Failed to create OpenSearch client: {exc}",
                    error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                    operation="initialize",
                    cause=exc,
                ) from exc

            # Ensure index exists
            await asyncio.get_running_loop().run_in_executor(None, self._ensure_index)

            # Initialise Bedrock client for embeddings (lazy until needed)
            self._bedrock_client = None

            self._initialized = True
            logger.info("OpenSearch vector service initialised successfully", extra={"index": self._index_name})

    async def index_documents(
        self,
        documents: list[dict[str, Any]],
        *,
        batch_size: int = 100,
        refresh: bool = False,
    ) -> int:
        """Index or update documents in OpenSearch."""
        if not documents:
            return 0

        await self.initialize()

        actions: list[dict[str, Any]] = []
        count = 0

        for doc in documents:
            text = doc.get("text")
            metadata = doc.get("metadata", {})
            embedding = doc.get("embedding")
            document_id = doc.get("id", str(uuid.uuid4()))

            if not text:
                logger.debug("Skipping document without text payload", extra={"doc_id": document_id})
                continue

            if embedding is None:
                embeddings = await self._embed_texts([text])
                embedding = embeddings[0]

            action = {
                "_op_type": "index",
                "_index": self._index_name,
                "_id": document_id,
                "_source": {
                    self._text_field: text,
                    self._vector_field: embedding,
                    self._metadata_field: metadata,
                    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
            }
            actions.append(action)
            count += 1

        if not actions:
            return 0

        try:
            loop = asyncio.get_running_loop()

            def _bulk_index_sync(payload: list[dict[str, Any]]) -> None:
                for i in range(0, len(payload), batch_size):
                    batch = payload[i : i + batch_size]
                    self._bulk_helper(self._client, batch, refresh=refresh)

            await loop.run_in_executor(None, _bulk_index_sync, actions)
        except Exception as exc:
            raise VectorServiceError(
                message=f"Failed to index documents in OpenSearch: {exc}",
                error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                operation="index",
                cause=exc,
            ) from exc

        logger.info("Indexed documents into OpenSearch", extra={"count": count, "index": self._index_name})
        return count

    async def delete_documents(self, document_ids: list[str]) -> int:
        """Delete documents from OpenSearch by ID."""
        if not document_ids:
            return 0

        await self.initialize()

        deleted = 0

        for doc_id in document_ids:
            try:
                await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: self._client.delete(index=self._index_name, id=doc_id, ignore=[404]),
                )
                deleted += 1
            except Exception as exc:
                logger.warning("Failed to delete OpenSearch document", extra={"id": doc_id, "error": str(exc)})

        return deleted

    async def search(
        self,
        query_texts: list[str],
        *,
        limit: int = 10,
        correlation_id: str | None = None,
    ) -> list[OpenSearchVectorResult]:
        """Perform k-NN similarity search in OpenSearch."""
        if not query_texts:
            return []

        await self.initialize()

        correlation_id = correlation_id or f"opensearch_search_{int(time.time() * 1000)}"
        start_time = time.time()

        # Circuit breaker guard
        if self._circuit_breaker_open:
            elapsed = time.time() - self._circuit_breaker_last_failure
            if elapsed < self.circuit_breaker_timeout:
                raise VectorServiceError(
                    message="OpenSearch search circuit breaker is open",
                    error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                    operation="search",
                    correlation_id=correlation_id,
                )
            self._circuit_breaker_open = False
            self._circuit_breaker_failures = 0

        try:
            embeddings = await self._embed_texts(query_texts)

            results: list[OpenSearchVectorResult] = []
            for embedding in embeddings:
                search_body = {
                    "size": limit,
                    "query": {
                        "knn": {
                            self._vector_field: {
                                "vector": embedding,
                                "k": limit,
                            }
                        }
                    },
                }

                response = await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: self._client.search(index=self._index_name, body=search_body),
                )

                for hit in response.get("hits", {}).get("hits", []):
                    results.append(
                        OpenSearchVectorResult(
                            id=hit.get("_id", ""),
                            score=float(hit.get("_score") or 0.0),
                            metadata=hit.get("_source", {}).get(self._metadata_field, {}),
                            document=hit.get("_source", {}).get(self._text_field),
                        )
                    )

            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(
                "OpenSearch search completed successfully",
                extra={
                    "query_count": len(query_texts),
                    "results_count": len(results),
                    "limit": limit,
                    "processing_time_ms": elapsed_ms,
                    "correlation_id": correlation_id,
                },
            )

            self._circuit_breaker_failures = 0
            return results

        except Exception as exc:
            elapsed_ms = (time.time() - start_time) * 1000
            self._circuit_breaker_failures += 1
            self._circuit_breaker_last_failure = time.time()

            if self._circuit_breaker_failures >= self.circuit_breaker_threshold:
                self._circuit_breaker_open = True
                logger.warning(
                    "Circuit breaker opened for OpenSearch search",
                    extra={"failures": self._circuit_breaker_failures, "correlation_id": correlation_id},
                )

            logger.error(
                "OpenSearch search failed",
                extra={
                    "query_count": len(query_texts),
                    "limit": limit,
                    "processing_time_ms": elapsed_ms,
                    "error": str(exc),
                    "correlation_id": correlation_id,
                },
            )

            raise VectorServiceError(
                message="OpenSearch search failed",
                error_code=ErrorCode.VECTOR_SERVICE_ERROR,
                operation="search",
                cause=exc,
                correlation_id=correlation_id,
            ) from exc

    async def health_check(self) -> dict[str, Any]:
        """Perform a lightweight health check on the OpenSearch cluster."""
        await self.initialize()

        health_status = {
            "service_name": "OpenSearch Vector Service",
            "index": self._index_name,
            "status": "unknown",
        }

        try:
            response = await asyncio.get_running_loop().run_in_executor(
                None, lambda: self._client.cluster.health(index=self._index_name, request_timeout=5)
            )
            health_status["status"] = response.get("status", "unknown")
            health_status["cluster_status"] = response
        except Exception as exc:
            health_status["status"] = "unavailable"
            health_status["error"] = str(exc)

        return health_status

    def _ensure_index(self) -> None:
        """Create OpenSearch index with k-NN mapping if it does not exist."""
        assert self._client is not None, "OpenSearch client must be initialised first"

        if self._client.indices.exists(index=self._index_name):
            return

        index_body = {
            "settings": {
                "index": {
                    "knn": True,
                    "number_of_shards": settings.OPENSEARCH_SHARDS,
                    "number_of_replicas": settings.OPENSEARCH_REPLICAS,
                }
            },
            "mappings": {
                "properties": {
                    self._text_field: {"type": "text"},
                    self._metadata_field: {"type": "object", "dynamic": True},
                    self._vector_field: {
                        "type": "knn_vector",
                        "dimension": self._vector_dim,
                        "method": {
                            "name": "hnsw",
                            "engine": settings.OPENSEARCH_KNN_ENGINE,
                            "space_type": settings.OPENSEARCH_KNN_SPACE_TYPE,
                            "parameters": {"ef_construction": 512, "m": 16},
                        },
                    },
                }
            },
        }

        self._client.indices.create(index=self._index_name, body=index_body)
        logger.info("Created OpenSearch index for vector storage", extra={"index": self._index_name})

    async def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using AWS Bedrock Titan model."""
        if not texts:
            return []

        if self._bedrock_client is None:
            import boto3

            self._bedrock_client = boto3.client(
                "bedrock-runtime",
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.get_secret_value("AWS_SECRET_ACCESS_KEY"),
            )

        embeddings: list[list[float]] = []

        for text in texts:
            try:
                response = await asyncio.to_thread(
                    self._bedrock_client.invoke_model,
                    modelId=self._embedding_model_id,
                    body=json.dumps({"inputText": text}),
                )
                payload = json.loads(response["body"].read())
                embedding = payload.get("embedding")
                if not embedding:
                    raise ValueError("Missing embedding vector in Bedrock response")
                embeddings.append(embedding)
            except Exception as exc:
                raise VectorServiceError(
                    message=f"Failed to generate embedding via Bedrock: {exc}",
                    error_code=ErrorCode.AI_SERVICE_UNAVAILABLE,
                    operation="embed",
                    cause=exc,
                ) from exc

        return embeddings
