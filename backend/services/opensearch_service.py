"""
In-memory vector service stub used for development.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class OpenSearchVectorResult:
    id: str
    score: float
    metadata: dict[str, Any]
    document: str | None = None


class OpenSearchVectorService:
    """Stores documents locally and returns simple matches."""

    def __init__(self) -> None:
        self._documents: list[dict[str, Any]] = []

    async def initialize(self) -> None:
        self._documents = []

    async def index_documents(
        self,
        documents: list[dict[str, Any]],
        *,
        batch_size: int = 100,
        refresh: bool = False,
    ) -> int:
        self._documents.extend(documents)
        return len(documents)

    async def search(self, query_texts: list[str], limit: int = 10) -> list[OpenSearchVectorResult]:
        if not query_texts:
            return []

        results: list[OpenSearchVectorResult] = []
        for document in self._documents[:limit]:
            results.append(
                OpenSearchVectorResult(
                    id=document.get("id", ""),
                    score=1.0,
                    metadata=document.get("metadata") or {},
                    document=document.get("text"),
                )
            )
        return results
