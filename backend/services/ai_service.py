"""
Lightweight AI service for generating responses via AWS Bedrock Claude.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from core.config import settings

logger = logging.getLogger(__name__)


class AIService:
    """Straightforward Bedrock runtime wrapper with embeddings."""

    def __init__(self) -> None:
        self._runtime = None
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return

        self._runtime = boto3.client(
            "bedrock-runtime",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        )
        self._initialized = True
        logger.info("AIService initialised")

    async def close(self) -> None:
        self._runtime = None
        self._initialized = False

    def is_ready(self) -> bool:
        return self._runtime is not None

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using Bedrock"""
        await self.initialize()

        if not texts:
            return []

        try:
            embeddings = []
            for text in texts:
                body = json.dumps({"inputText": text})

                response = await asyncio.to_thread(
                    self._runtime.invoke_model,
                    modelId=settings.BEDROCK_EMBEDDING_MODEL_ID,
                    body=body,
                    contentType="application/json",
                    accept="application/json",
                )

                result = json.loads(response["body"].read())
                embeddings.append(result["embedding"])

            logger.info(f"Generated {len(embeddings)} embeddings")
            return embeddings

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 2000,
    ) -> dict[str, Any]:
        """
        Generate text using AWS Bedrock Claude (for LightRAG).

        Args:
            prompt: User prompt
            system_prompt: System prompt (optional)
            max_tokens: Maximum tokens to generate

        Returns:
            Response dict with "text" key
        """
        await self.initialize()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        text = await self._invoke_claude(messages, max_tokens=max_tokens)
        return {
            "text": text,
            "model_used": settings.BEDROCK_MODEL_ID,
        }

    async def generate_rag_response(self, context: dict[str, Any]) -> dict[str, Any]:
        await self.initialize()

        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": self._user_prompt(context)},
        ]

        text = await self._invoke_claude(messages, max_tokens=settings.RESPONSE_MAX_TOKENS)
        return {
            "text": text,
            "model_used": settings.BEDROCK_MODEL_ID,
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
                price_str = f"{price:,}원" if isinstance(price, (int, float)) else str(price or "")
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

    async def _invoke_claude(self, messages: list[dict[str, str]], max_tokens: int) -> str:
        if self._runtime is None:
            raise RuntimeError("AIService is not initialised")

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
            "top_p": 0.9,
        }

        try:
            response = await asyncio.to_thread(
                self._runtime.invoke_model,
                modelId=settings.BEDROCK_MODEL_ID,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
            payload = json.loads(response["body"].read())
            return payload["content"][0]["text"]
        except (ClientError, BotoCoreError) as exc:
            logger.error("Bedrock invocation failed: %s", exc)
            raise
