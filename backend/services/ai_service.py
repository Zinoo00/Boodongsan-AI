"""
Lightweight AI service for local embeddings and Anthropic Claude text generation.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any

import numpy as np
from anthropic import Anthropic

from core.config import settings

logger = logging.getLogger(__name__)


class AIService:
    """Straightforward AI service using Anthropic Claude and local embeddings."""

    def __init__(self) -> None:
        self._initialized = False
        self._anthropic_client: Anthropic | None = None
        self._anthropic_model_id = settings.ANTHROPIC_MODEL_ID
        self._embedding_dim = settings.LIGHTRAG_EMBEDDING_DIM

    async def initialize(self) -> None:
        if self._initialized:
            return

        self._initialized = True
        logger.info("AIService initialised")

    async def close(self) -> None:
        self._initialized = False
        self._anthropic_client = None

    def is_ready(self) -> bool:
        return self._initialized

    @property
    def embedding_dim(self) -> int:
        return self._embedding_dim

    async def generate_embeddings(self, texts: list[str], **_: Any) -> list[list[float]]:
        """Generate lightweight deterministic embeddings (no external dependency)."""

        if not texts:
            return []

        return [self._text_to_embedding(text) for text in texts]

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 2000,
    ) -> dict[str, Any]:
        """
        Generate text using Anthropic Claude (direct API).

        Args:
            prompt: User prompt
            system_prompt: System prompt (optional)
            max_tokens: Maximum tokens to generate

        Returns:
            Response dict with "text" key
        """
        system = system_prompt if system_prompt else None

        anthropic_messages = [
            {"role": "user", "content": prompt},
        ]

        text = await self._invoke_claude(
            messages=anthropic_messages,
            system_prompt=system,
            max_tokens=max_tokens,
        )
        return {
            "text": text,
            "model_used": self._anthropic_model_id,
        }

    async def generate_rag_response(self, context: dict[str, Any]) -> dict[str, Any]:
        system_prompt = self._system_prompt()
        messages = [
            {"role": "user", "content": self._user_prompt(context)},
        ]

        text = await self._invoke_claude(
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=settings.RESPONSE_MAX_TOKENS,
        )
        return {
            "text": text,
            "model_used": self._anthropic_model_id,
        }

    def _system_prompt(self) -> str:
        return (
            "당신은 한국 부동산 상담을 돕는 AI 어시스턴트입니다. "
            "매물 정보, 정부 정책, 시장 데이터를 조합하여 간결하고 명확하게 답변하세요."
        )

    def _user_prompt(self, context: dict[str, Any]) -> str:
        parts: list[str] = [f"사용자 질문: {context.get('user_query', '').strip()}"]

        profile = context.get("user_profile") or {}
        if profile:
            summary = []
            if profile.get("age"):
                summary.append(f"나이 {profile['age']}세")
            if profile.get("annual_income"):
                summary.append(f"연소득 {profile['annual_income']:,}원")
            if profile.get("max_budget"):
                summary.append(f"예산 {profile['max_budget']:,}원")
            if profile.get("preferred_locations"):
                summary.append(f"선호 지역 {', '.join(profile['preferred_locations'])}")
            if summary:
                parts.append("사용자 정보: " + ", ".join(summary))

        properties = context.get("properties") or []
        if properties:
            lines = ["추천 매물:"]
            for item in properties[:3]:
                address = item.get("address") or item.get("title") or "미확인 매물"
                price = item.get("price")
                price_str = f"{price:,}원" if isinstance(price, int | float) else str(price or "")
                prop_type = item.get("property_type") or ""
                lines.append(f"- {address} / {prop_type} / {price_str}")
            parts.extend(lines)

        policies = context.get("policies") or []
        if policies:
            lines = ["추천 정책:"]
            for policy in policies[:2]:
                name = policy.get("policy_name") or policy.get("name") or "미확인 정책"
                org = policy.get("organizing_institution") or policy.get("institution") or ""
                lines.append(f"- {name} ({org})" if org else f"- {name}")
            parts.extend(lines)

        market = context.get("market_context") or {}
        if market:
            info = []
            if market.get("average_price"):
                info.append(f"평균 매매가 {market['average_price']:,}원")
            if market.get("price_trend"):
                info.append(f"가격 추세 {market['price_trend']}")
            if info:
                parts.append("시장 정보: " + ", ".join(info))

        return "\n".join(part for part in parts if part)

    def _ensure_anthropic_client(self) -> Anthropic:
        if settings.ANTHROPIC_API_KEY == "":
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")
        if self._anthropic_client is None:
            self._anthropic_client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._anthropic_client

    async def _invoke_claude(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None,
        max_tokens: int,
    ) -> str:
        client = self._ensure_anthropic_client()

        request_kwargs: dict[str, Any] = {
            "model": self._anthropic_model_id,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system_prompt:
            request_kwargs["system"] = system_prompt

        try:
            response = await asyncio.to_thread(
                client.messages.create,
                **request_kwargs,
            )
        except Exception as exc:  # Anthropic client raises generic exceptions
            logger.error("Anthropic invocation failed: %s", exc)
            raise

        text_parts: list[str] = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                text_parts.append(block.text)
        return "".join(text_parts)

    def _text_to_embedding(self, text: str) -> list[float]:
        """Generate a deterministic pseudo-embedding for development use."""
        if not text:
            return [0.0] * self._embedding_dim

        digest = hashlib.sha256(text.encode("utf-8")).digest()
        seed = int.from_bytes(digest[:8], "little", signed=False)
        rng = np.random.default_rng(seed)
        vector = rng.standard_normal(self._embedding_dim)
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        return vector.astype(np.float32).tolist()
