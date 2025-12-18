"""
In-memory data service for properties and policies.

NOTE: 이 서비스는 인메모리 스텁입니다.
- 데이터는 서버 재시작 시 사라짐
- 실제 부동산/정책 데이터는 LightRAG를 통해 관리됨
- properties.py, policies.py 라우터는 현재 비활성 상태

향후 계획:
- LightRAG 기반 검색으로 통합 예정
- 또는 PostgreSQL 기반으로 마이그레이션 예정
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


class DataService:
    """
    In-memory stub for properties and policies.

    WARNING: 이 서비스는 현재 비활성 상태입니다.
    실제 데이터는 LightRAG를 통해 관리됩니다.
    """

    def __init__(self) -> None:
        self._properties: dict[str, dict[str, Any]] = {}
        self._policies: dict[str, dict[str, Any]] = {}
        logger.warning(
            "DataService initialized (in-memory stub). "
            "Data will not persist across restarts. "
            "Use LightRAG for actual data."
        )

    async def create_property(self, property_data: dict[str, Any]) -> dict[str, Any]:
        property_id = property_data.get("id") or str(uuid.uuid4())
        record = {**property_data, "id": property_id}
        self._properties[property_id] = record
        return record

    async def get_property(self, property_id: str) -> dict[str, Any] | None:
        return self._properties.get(property_id)

    async def search_properties(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        items = list(self._properties.values())
        filters = filters or {}
        for key, value in filters.items():
            if value is None:
                continue
            items = [item for item in items if item.get(key) == value]
        return items[offset : offset + limit]

    async def update_property(
        self, property_id: str, updates: dict[str, Any]
    ) -> dict[str, Any] | None:
        if property_id not in self._properties:
            return None
        self._properties[property_id].update(updates)
        return self._properties[property_id]

    async def delete_property(self, property_id: str) -> bool:
        return self._properties.pop(property_id, None) is not None

    async def create_policy(self, policy_data: dict[str, Any]) -> dict[str, Any]:
        policy_id = policy_data.get("id") or str(uuid.uuid4())
        record = {**policy_data, "id": policy_id, "active": policy_data.get("active", True)}
        self._policies[policy_id] = record
        return record

    async def get_policy(self, policy_id: str) -> dict[str, Any] | None:
        return self._policies.get(policy_id)

    async def search_policies(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        items = list(self._policies.values())
        filters = filters or {}
        for key, value in filters.items():
            if value is None:
                continue
            items = [item for item in items if item.get(key) == value]
        return items

    async def get_all_policies(self, active_only: bool = True) -> list[dict[str, Any]]:
        if not active_only:
            return list(self._policies.values())
        return [policy for policy in self._policies.values() if policy.get("active", True)]

    async def match_policies_for_user(self, user_profile: dict[str, Any]) -> list[dict[str, Any]]:
        region = user_profile.get("region")
        if not region:
            return list(self._policies.values())
        return [policy for policy in self._policies.values() if policy.get("region") == region]
