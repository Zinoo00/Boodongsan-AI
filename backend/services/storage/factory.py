"""
Storage backend factory.
"""

from __future__ import annotations

import logging
from pathlib import Path

from core.config import settings
from services.storage.base import StorageBackend
from services.storage.local_backend import LocalBackend
from services.storage.postgresql_backend import PostgreSQLBackend

logger = logging.getLogger(__name__)


def create_storage_backend(backend_type: str | None = None) -> StorageBackend:
    """
    Storage backend 생성 팩토리.

    Args:
        backend_type: Storage backend 타입
            - "postgresql": AWS RDS PostgreSQL + pgvector (default)
            - "local": NanoVectorDB + NetworkX + JSON
            - None: Use settings.STORAGE_BACKEND

    Returns:
        StorageBackend instance

    Raises:
        ValueError: Unknown backend type
    """
    backend = backend_type or settings.STORAGE_BACKEND

    if backend == "postgresql":
        logger.info("Creating PostgreSQL storage backend")
        return PostgreSQLBackend()

    elif backend == "local":
        logger.info("Creating local storage backend")
        working_dir = Path(settings.LIGHTRAG_WORKING_DIR) / settings.LIGHTRAG_WORKSPACE
        return LocalBackend(working_dir)

    else:
        raise ValueError(
            f"Unknown storage backend: {backend}. "
            f"Supported backends: postgresql, local"
        )
