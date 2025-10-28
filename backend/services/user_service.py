"""
사용자 서비스 - 사용자 프로필 및 대화 이력 관리
Neo4j 그래프 데이터베이스 기반
"""

import logging
import uuid
from datetime import datetime
from typing import Any

from neo4j import AsyncDriver

from core.database import db_manager

logger = logging.getLogger(__name__)


class UserService:
    """Neo4j 기반 사용자 관련 서비스"""

    def __init__(self):
        logger.info("UserService 초기화 완료")

    async def _get_driver(self) -> AsyncDriver:
        """Neo4j 드라이버 가져오기"""
        return db_manager.get_neo4j()

    # ==================== 사용자 프로필 관리 ====================

    async def get_primary_profile(self, user_id: str) -> dict[str, Any] | None:
        """사용자 기본 프로필 조회"""
        try:
            logger.info(f"사용자 프로필 조회: {user_id}")

            driver = await self._get_driver()
            async with driver.session() as session:
                result = await session.run(
                    """
                    MATCH (u:User {user_id: $user_id})
                    RETURN u
                    """,
                    user_id=user_id
                )
                record = await result.single()

                if record:
                    user_node = record["u"]
                    return dict(user_node)
                return None

        except Exception as e:
            logger.error(f"사용자 프로필 조회 실패: {str(e)}")
            return None

    async def create_or_update_user_profile(
        self,
        user_id: str,
        profile_data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """사용자 프로필 생성 또는 업데이트"""
        try:
            logger.info(f"사용자 프로필 생성/업데이트: {user_id}")

            driver = await self._get_driver()
            async with driver.session() as session:
                result = await session.run(
                    """
                    MERGE (u:User {user_id: $user_id})
                    SET u.age = $age,
                        u.income = $income,
                        u.region = $region,
                        u.property_type = $property_type,
                        u.transaction_type = $transaction_type,
                        u.budget_min = $budget_min,
                        u.budget_max = $budget_max,
                        u.room_count = $room_count,
                        u.area = $area,
                        u.additional_preferences = $additional_preferences,
                        u.updated_at = $updated_at
                    RETURN u
                    """,
                    user_id=user_id,
                    age=profile_data.get("age"),
                    income=profile_data.get("income"),
                    region=profile_data.get("region"),
                    property_type=profile_data.get("property_type"),
                    transaction_type=profile_data.get("transaction_type"),
                    budget_min=profile_data.get("budget_min"),
                    budget_max=profile_data.get("budget_max"),
                    room_count=profile_data.get("room_count"),
                    area=profile_data.get("area"),
                    additional_preferences=str(profile_data.get("additional_preferences", {})),
                    updated_at=datetime.utcnow().isoformat()
                )
                record = await result.single()

                if record:
                    user_node = record["u"]
                    logger.info(f"✅ 사용자 프로필 저장 성공: {user_id}")
                    return dict(user_node)
                return None

        except Exception as e:
            logger.error(f"❌ 사용자 프로필 저장 실패: {str(e)}")
            return None

    # ==================== 대화 이력 관리 ====================

    async def get_conversation_history(
        self,
        user_id: str,
        conversation_id: str,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """대화 이력 조회"""
        try:
            logger.info(f"대화 이력 조회: user={user_id}, conv={conversation_id}")

            driver = await self._get_driver()
            async with driver.session() as session:
                result = await session.run(
                    """
                    MATCH (u:User {user_id: $user_id})-[:HAS_CONVERSATION]->(c:Conversation {conversation_id: $conversation_id})
                    MATCH (c)-[:HAS_MESSAGE]->(m:Message)
                    RETURN m
                    ORDER BY m.created_at DESC
                    LIMIT $limit
                    """,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    limit=limit
                )

                messages = []
                async for record in result:
                    message_node = record["m"]
                    messages.append(dict(message_node))

                logger.info(f"대화 이력 조회 완료: {len(messages)}개 메시지")
                return messages

        except Exception as e:
            logger.error(f"대화 이력 조회 실패: {str(e)}")
            return []

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
        try:
            logger.info(f"대화 메시지 저장: user={user_id}, conv={conversation_id}")

            message_id = str(uuid.uuid4())
            created_at = datetime.utcnow().isoformat()

            driver = await self._get_driver()
            async with driver.session() as session:
                await session.run(
                    """
                    MERGE (u:User {user_id: $user_id})
                    MERGE (c:Conversation {conversation_id: $conversation_id})
                    MERGE (u)-[:HAS_CONVERSATION]->(c)
                    CREATE (m:Message {
                        message_id: $message_id,
                        role: $role,
                        content: $content,
                        intent: $intent,
                        entities: $entities,
                        search_results: $search_results,
                        recommended_policies: $recommended_policies,
                        confidence_score: $confidence_score,
                        model_used: $model_used,
                        created_at: $created_at
                    })
                    MERGE (c)-[:HAS_MESSAGE]->(m)
                    """,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    role=role,
                    content=content,
                    intent=intent,
                    entities=str(entities or {}),
                    search_results=str(search_results or []),
                    recommended_policies=str(recommended_policies or []),
                    confidence_score=confidence_score,
                    model_used=model_used,
                    created_at=created_at
                )

            logger.info(f"✅ 대화 메시지 저장 성공: {message_id}")
            return True

        except Exception as e:
            logger.error(f"❌ 대화 메시지 저장 실패: {str(e)}")
            return False

    # ==================== 사용자 분석 ====================

    async def get_user_statistics(self, user_id: str) -> dict[str, Any]:
        """사용자 활동 통계"""
        try:
            logger.info(f"사용자 통계 조회: {user_id}")

            driver = await self._get_driver()
            async with driver.session() as session:
                result = await session.run(
                    """
                    MATCH (u:User {user_id: $user_id})
                    OPTIONAL MATCH (u)-[:HAS_CONVERSATION]->(c:Conversation)-[:HAS_MESSAGE]->(m:Message)
                    RETURN
                        COUNT(DISTINCT c) as conversation_count,
                        COUNT(m) as message_count
                    """,
                    user_id=user_id
                )
                record = await result.single()

                if record:
                    return {
                        "user_id": user_id,
                        "conversation_count": record["conversation_count"],
                        "message_count": record["message_count"],
                    }
                return {
                    "user_id": user_id,
                    "conversation_count": 0,
                    "message_count": 0,
                }

        except Exception as e:
            logger.error(f"사용자 통계 조회 실패: {str(e)}")
            return {
                "user_id": user_id,
                "conversation_count": 0,
                "message_count": 0,
            }

    async def get_user_preferences(self, user_id: str) -> dict[str, Any]:
        """사용자 선호도 분석"""
        try:
            logger.info(f"사용자 선호도 분석: {user_id}")

            # 기본 프로필 조회
            profile = await self.get_primary_profile(user_id)
            if not profile:
                return {}

            # 선호도 데이터 추출
            preferences = {
                "age": profile.get("age"),
                "income": profile.get("income"),
                "region": profile.get("region"),
                "property_type": profile.get("property_type"),
                "transaction_type": profile.get("transaction_type"),
                "budget_range": {
                    "min": profile.get("budget_min"),
                    "max": profile.get("budget_max")
                },
                "room_count": profile.get("room_count"),
                "area": profile.get("area"),
            }

            return preferences

        except Exception as e:
            logger.error(f"사용자 선호도 분석 실패: {str(e)}")
            return {}

    # ==================== 대화 세션 관리 ====================

    async def create_conversation_session(
        self,
        user_id: str,
        conversation_id: str | None = None
    ) -> str:
        """새 대화 세션 생성"""
        try:
            if not conversation_id:
                conversation_id = str(uuid.uuid4())

            logger.info(f"대화 세션 생성: user={user_id}, conv={conversation_id}")

            driver = await self._get_driver()
            async with driver.session() as session:
                await session.run(
                    """
                    MERGE (u:User {user_id: $user_id})
                    MERGE (c:Conversation {conversation_id: $conversation_id, created_at: $created_at})
                    MERGE (u)-[:HAS_CONVERSATION]->(c)
                    """,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    created_at=datetime.utcnow().isoformat()
                )

            logger.info(f"✅ 대화 세션 생성 완료: {conversation_id}")
            return conversation_id

        except Exception as e:
            logger.error(f"❌ 대화 세션 생성 실패: {str(e)}")
            return str(uuid.uuid4())  # fallback

    async def get_user_conversations(
        self,
        user_id: str,
        limit: int = 20
    ) -> list[dict[str, Any]]:
        """사용자의 모든 대화 조회"""
        try:
            logger.info(f"사용자 대화 목록 조회: {user_id}")

            driver = await self._get_driver()
            async with driver.session() as session:
                result = await session.run(
                    """
                    MATCH (u:User {user_id: $user_id})-[:HAS_CONVERSATION]->(c:Conversation)
                    RETURN c
                    ORDER BY c.created_at DESC
                    LIMIT $limit
                    """,
                    user_id=user_id,
                    limit=limit
                )

                conversations = []
                async for record in result:
                    conv_node = record["c"]
                    conversations.append(dict(conv_node))

                logger.info(f"대화 목록 조회 완료: {len(conversations)}개")
                return conversations

        except Exception as e:
            logger.error(f"대화 목록 조회 실패: {str(e)}")
            return []
