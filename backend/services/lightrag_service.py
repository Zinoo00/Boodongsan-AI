"""
Lightweight LightRAG stub used for development.
"""

from __future__ import annotations

from typing import Any


class LightRAGService:
    """Simple placeholder that keeps the interface compatible."""

    def __init__(self) -> None:
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True

    async def finalize(self) -> None:
        self._initialized = False

    async def query(self, query: str) -> dict[str, Any] | None:
        if not self._initialized:
            await self.initialize()
        return {"answer": None, "mode": "stub", "query": query}
