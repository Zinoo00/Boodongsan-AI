"""
Storage backend abstraction layer.

Supports multiple storage backends:
- PostgreSQL (default): AWS RDS PostgreSQL + pgvector
- Local: NanoVectorDB + NetworkX + JSON
"""

from services.storage.base import StorageBackend
from services.storage.factory import create_storage_backend

__all__ = ["StorageBackend", "create_storage_backend"]
