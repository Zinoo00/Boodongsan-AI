"""
Lightweight AI service for local embeddings and Anthropic Claude text generation.
Supports both Anthropic Direct API and AWS Bedrock.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any, Literal

import numpy as np
from anthropic import Anthropic

from core.config import settings

logger = logging.getLogger(__name__)


class AIService:
    """
    AI service supporting both Anthropic Direct API and AWS Bedrock.
    
    Automatically selects provider based on configuration:
    - If ANTHROPIC_API_KEY is set: uses Anthropic Direct API
    - If AWS credentials are set: uses AWS Bedrock
    - Priority: Anthropic Direct API > AWS Bedrock
    """

    def __init__(self) -> None:
        self._initialized = False
        self._anthropic_client: Anthropic | None = None
        self._bedrock_client: Any = None  # boto3 client
        self._provider: Literal["anthropic", "bedrock", "none"] = "none"
        self._anthropic_model_id = settings.ANTHROPIC_MODEL_ID
        self._bedrock_model_id = settings.BEDROCK_MODEL_ID
        self._embedding_dim = settings.LIGHTRAG_EMBEDDING_DIM

    async def initialize(self) -> None:
        if self._initialized:
            return

        # Detect which provider is configured
        self._provider = self._detect_provider()
        
        if self._provider == "anthropic":
            logger.info("✓ Using Anthropic Direct API")
        elif self._provider == "bedrock":
            logger.info("✓ Using AWS Bedrock")
            await self._initialize_bedrock()
        else:
            logger.warning("⚠️  No AI provider configured (neither ANTHROPIC_API_KEY nor AWS credentials)")

        self._initialized = True
        logger.info("AIService initialized")

    async def close(self) -> None:
        self._initialized = False
        self._anthropic_client = None
        self._bedrock_client = None

    def is_ready(self) -> bool:
        return self._initialized and self._provider != "none"
    
    @property
    def provider(self) -> str:
        """Current AI provider: 'anthropic', 'bedrock', or 'none'"""
        return self._provider

    @property
    def embedding_dim(self) -> int:
        return self._embedding_dim

    def _detect_provider(self) -> Literal["anthropic", "bedrock", "none"]:
        """Detect which AI provider is configured."""
        # Priority: Anthropic Direct API > AWS Bedrock
        if settings.ANTHROPIC_API_KEY and settings.ANTHROPIC_API_KEY.strip():
            return "anthropic"
        
        if (
            settings.AWS_ACCESS_KEY_ID
            and settings.AWS_ACCESS_KEY_ID.strip()
            and settings.AWS_SECRET_ACCESS_KEY
            and settings.AWS_SECRET_ACCESS_KEY.strip()
        ):
            return "bedrock"
        
        return "none"

    async def _initialize_bedrock(self) -> None:
        """Initialize AWS Bedrock client."""
        try:
            import boto3
            
            self._bedrock_client = boto3.client(
                service_name="bedrock-runtime",
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )
            logger.info(f"AWS Bedrock client initialized (region: {settings.AWS_REGION})")
        except ImportError:
            logger.error("boto3 not installed. Install with: pip install boto3")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize AWS Bedrock: {e}")
            raise

    async def generate_embeddings(self, texts: list[str], **_: Any) -> list[list[float]]:
        """
        Generate embeddings using AWS Bedrock Titan v2 or fallback to deterministic hash.

        AWS Bedrock Titan Embeddings v2: configurable dimensions (256, 512, 1024)
        Default: 1024 dimensions (set via LIGHTRAG_EMBEDDING_DIM)
        """
        if not texts:
            return []

        # Use real Titan embeddings if Bedrock is available and enabled
        if (
            self._provider == "bedrock"
            and self._bedrock_client
            and settings.LIGHTRAG_USE_REAL_EMBEDDINGS
        ):
            return await self._generate_titan_embeddings(texts)

        # Fallback to hash-based embeddings for development
        logger.warning("Using hash-based embeddings (not semantic). Set LIGHTRAG_USE_REAL_EMBEDDINGS=true for production.")
        return [self._text_to_embedding(text) for text in texts]

    async def _generate_titan_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Generate real embeddings using AWS Bedrock Titan Embeddings v2.

        Model: amazon.titan-embed-text-v2:0
        Dimensions: 1024 (configurable: 256, 512, 1024)
        Max input: 8192 tokens
        """
        embeddings = []

        for text in texts:
            try:
                # Titan v2 embedding request body with configurable dimensions
                request_body = {
                    "inputText": text[:8000],  # Truncate to avoid token limit
                    "dimensions": self._embedding_dim,  # Titan v2: 256, 512, or 1024
                    "normalize": True,  # Return normalized embeddings
                }

                response = await asyncio.to_thread(
                    self._bedrock_client.invoke_model,
                    modelId=settings.BEDROCK_EMBEDDING_MODEL_ID,
                    body=json.dumps(request_body),
                )

                response_body = json.loads(response["body"].read())
                embedding = response_body.get("embedding", [])

                if embedding:
                    embeddings.append(embedding)
                else:
                    logger.warning(f"Empty embedding returned for text: {text[:50]}...")
                    embeddings.append(self._text_to_embedding(text))

            except Exception as e:
                logger.error(f"Titan embedding failed: {e}")
                # Fallback to hash-based embedding
                embeddings.append(self._text_to_embedding(text))

        return embeddings

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 2000,
    ) -> dict[str, Any]:
        """
        Generate text using configured AI provider (Anthropic or Bedrock).

        Args:
            prompt: User prompt
            system_prompt: System prompt (optional)
            max_tokens: Maximum tokens to generate

        Returns:
            Response dict with "text" and "model_used" keys
        """
        if self._provider == "anthropic":
            text = await self._invoke_anthropic(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=system_prompt,
                max_tokens=max_tokens,
            )
            return {
                "text": text,
                "model_used": self._anthropic_model_id,
                "provider": "anthropic",
            }
        
        elif self._provider == "bedrock":
            text = await self._invoke_bedrock(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=system_prompt,
                max_tokens=max_tokens,
            )
            return {
                "text": text,
                "model_used": self._bedrock_model_id,
                "provider": "bedrock",
            }
        
        else:
            raise RuntimeError("No AI provider configured")

    async def generate_rag_response(self, context: dict[str, Any]) -> dict[str, Any]:
        system_prompt = self._system_prompt()
        messages = [
            {"role": "user", "content": self._user_prompt(context)},
        ]

        if self._provider == "anthropic":
            text = await self._invoke_anthropic(
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=settings.RESPONSE_MAX_TOKENS,
            )
            return {
                "text": text,
                "model_used": self._anthropic_model_id,
                "provider": "anthropic",
            }
        
        elif self._provider == "bedrock":
            text = await self._invoke_bedrock(
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=settings.RESPONSE_MAX_TOKENS,
            )
            return {
                "text": text,
                "model_used": self._bedrock_model_id,
                "provider": "bedrock",
            }
        
        else:
            raise RuntimeError("No AI provider configured")

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
        """Ensure Anthropic client is initialized."""
        if not settings.ANTHROPIC_API_KEY or not settings.ANTHROPIC_API_KEY.strip():
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")
        if self._anthropic_client is None:
            self._anthropic_client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._anthropic_client

    async def _invoke_anthropic(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None,
        max_tokens: int,
    ) -> str:
        """Invoke Anthropic Direct API."""
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
        except Exception as exc:
            logger.error(f"Anthropic API call failed: {exc}")
            raise

        text_parts: list[str] = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                text_parts.append(block.text)
        return "".join(text_parts)

    async def _invoke_bedrock(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None,
        max_tokens: int,
    ) -> str:
        """Invoke AWS Bedrock Claude model."""
        if not self._bedrock_client:
            raise RuntimeError("AWS Bedrock client not initialized")

        # Bedrock uses the same message format as Anthropic
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": messages,
        }
        
        if system_prompt:
            request_body["system"] = system_prompt

        try:
            response = await asyncio.to_thread(
                self._bedrock_client.invoke_model,
                modelId=self._bedrock_model_id,
                body=json.dumps(request_body),
            )
            
            response_body = json.loads(response["body"].read())
            
            # Extract text from response
            text_parts: list[str] = []
            for content_block in response_body.get("content", []):
                if content_block.get("type") == "text":
                    text_parts.append(content_block.get("text", ""))
            
            return "".join(text_parts)
            
        except Exception as exc:
            logger.error(f"AWS Bedrock invocation failed: {exc}")
            raise

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
