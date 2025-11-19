"""
사용자 서비스 - 경량 JSON 기반 사용자 및 대화 이력 저장소
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from core.config import settings

logger = logging.getLogger(__name__)


class UserService:
    """Lightweight JSON-backed user service replacing the previous Neo4j implementation."""

    def __init__(self) -> None:
        storage_root = Path(settings.LIGHTRAG_WORKING_DIR).resolve()
        storage_root.mkdir(parents=True, exist_ok=True)

        self._storage_path = storage_root / "user_store.json"
        self._lock = asyncio.Lock()
        logger.info("UserService initialised with JSON storage at %s", self._storage_path)

    # ==================== 내부 헬퍼 ====================

    async def _load_store(self) -> dict[str, Any]:
        def _read() -> dict[str, Any]:
            if not self._storage_path.exists():
                return {"profiles": {}, "conversations": {}}
            try:
                with self._storage_path.open("r", encoding="utf-8") as fp:
                    return json.load(fp)
            except json.JSONDecodeError:
                logger.warning("User storage corrupted, resetting %s", self._storage_path)
                return {"profiles": {}, "conversations": {}}

        return await asyncio.to_thread(_read)

    async def _write_store(self, store: dict[str, Any]) -> None:
        def _write() -> None:
            with self._storage_path.open("w", encoding="utf-8") as fp:
                json.dump(store, fp, ensure_ascii=False, indent=2)

        await asyncio.to_thread(_write)

    def _now(self) -> str:
        return datetime.utcnow().isoformat()

    # ==================== 사용자 프로필 관리 ====================

    async def get_primary_profile(self, user_id: str) -> dict[str, Any] | None:
        """사용자 기본 프로필 조회"""
        async with self._lock:
            store = await self._load_store()
            return store["profiles"].get(user_id)

    async def create_or_update_user_profile(
        self,
        user_id: str,
        profile_data: dict[str, Any],
    ) -> dict[str, Any] | None:
        """사용자 프로필 생성 또는 업데이트"""
        async with self._lock:
            store = await self._load_store()
            profile = {
                "user_id": user_id,
                "age": profile_data.get("age"),
                "income": profile_data.get("income"),
                "region": profile_data.get("region"),
                "property_type": profile_data.get("property_type"),
                "transaction_type": profile_data.get("transaction_type"),
                "budget_min": profile_data.get("budget_min"),
                "budget_max": profile_data.get("budget_max"),
                "room_count": profile_data.get("room_count"),
                "area": profile_data.get("area"),
                "additional_preferences": profile_data.get("additional_preferences", {}),
                "updated_at": self._now(),
            }

            store.setdefault("profiles", {})[user_id] = profile
            await self._write_store(store)
            logger.info("✅ 사용자 프로필 저장 성공: %s", user_id)
            return profile

    # ==================== 대화 이력 관리 ====================

    async def get_conversation_history(
        self,
        user_id: str,
        conversation_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """대화 이력 조회"""
        async with self._lock:
            store = await self._load_store()
            user_convs = store.get("conversations", {}).get(user_id, {})
            convo = user_convs.get(conversation_id, {"messages": []})
            messages = list(convo.get("messages", []))
            return list(reversed(messages[-limit:]))

    async def save_conversation_message(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        intent: str | None = None,
        entities: dict[str, Any] | None = None,
        search_results: list[str] | None = None,
        recommended_policies: list[str] | None = None,
        confidence_score: float | None = None,
        model_used: str | None = None,
    ) -> bool:
        """대화 메시지 저장"""
        message = {
            "message_id": str(uuid.uuid4()),
            "role": role,
            "content": content,
            "intent": intent,
            "entities": entities or {},
            "search_results": search_results or [],
            "recommended_policies": recommended_policies or [],
            "confidence_score": confidence_score,
            "model_used": model_used,
            "created_at": self._now(),
        }

        async with self._lock:
            store = await self._load_store()
            convs = store.setdefault("conversations", {}).setdefault(user_id, {})
            convo = convs.setdefault(
                conversation_id,
                {"conversation_id": conversation_id, "created_at": self._now(), "messages": []},
            )
            convo.setdefault("messages", []).append(message)
            await self._write_store(store)

        logger.info("✅ 대화 메시지 저장 성공: %s", message["message_id"])
        return True

    # ==================== 사용자 분석 ====================

    async def get_user_statistics(self, user_id: str) -> dict[str, Any]:
        """사용자 활동 통계"""
        async with self._lock:
            store = await self._load_store()
            convs = store.get("conversations", {}).get(user_id, {})
            conversation_count = len(convs)
            message_count = sum(len(conv.get("messages", [])) for conv in convs.values())

        return {
            "user_id": user_id,
            "conversation_count": conversation_count,
            "message_count": message_count,
        }

    async def get_user_preferences(self, user_id: str) -> dict[str, Any]:
        """사용자 선호도 분석"""
        profile = await self.get_primary_profile(user_id)
        if not profile:
            return {}

        return {
            "age": profile.get("age"),
            "income": profile.get("income"),
            "region": profile.get("region"),
            "property_type": profile.get("property_type"),
            "transaction_type": profile.get("transaction_type"),
            "budget_range": {
                "min": profile.get("budget_min"),
                "max": profile.get("budget_max"),
            },
            "room_count": profile.get("room_count"),
            "area": profile.get("area"),
        }

    # ==================== 대화 세션 관리 ====================

    async def create_conversation_session(
        self,
        user_id: str,
        conversation_id: str | None = None,
    ) -> str:
        """새 대화 세션 생성"""
        conversation_id = conversation_id or str(uuid.uuid4())
        async with self._lock:
            store = await self._load_store()
            user_convs = store.setdefault("conversations", {}).setdefault(user_id, {})
            user_convs.setdefault(
                conversation_id,
                {"conversation_id": conversation_id, "created_at": self._now(), "messages": []},
            )
            await self._write_store(store)

        logger.info("✅ 대화 세션 생성 완료: %s", conversation_id)
        return conversation_id

    async def get_user_conversations(
        self,
        user_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """사용자의 모든 대화 조회"""
        async with self._lock:
            store = await self._load_store()
            user_convs = store.get("conversations", {}).get(user_id, {})
            conversations = sorted(
                user_convs.values(),
                key=lambda item: item.get("created_at", ""),
                reverse=True,
            )
        return conversations[:limit]
