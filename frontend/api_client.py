"""
API client for BODA FastAPI backend integration.
FastAPI 백엔드와의 통신을 담당하는 클라이언트
"""

import logging
from typing import Any

import httpx
from pydantic import BaseModel, Field

from config import settings

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    """Chat request payload matching backend schema"""

    message: str = Field(..., min_length=1, max_length=2000)
    user_id: str
    conversation_id: str | None = None
    session_context: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    """Chat response payload matching backend schema"""

    user_id: str
    conversation_id: str
    response: str
    knowledge_mode: str | None = None
    knowledge_cached: bool = False
    processing_time_ms: float
    vector_results: list[dict[str, Any]] = Field(default_factory=list)
    rag_context: dict[str, Any] = Field(default_factory=dict)


class ConversationHistoryResponse(BaseModel):
    """Conversation history response"""

    conversation_id: str
    messages: list[dict[str, Any]]
    total_count: int


class UserContextResponse(BaseModel):
    """User context response"""

    user_id: str
    profile: dict[str, Any] | None = None
    recent_conversations: list[dict[str, Any]] = Field(default_factory=list)


class BODAAPIClient:
    """
    BODA FastAPI 백엔드 클라이언트

    Features:
    - 비동기 HTTP 요청 with httpx
    - 자동 타임아웃 및 재시도 로직
    - Pydantic 모델 기반 요청/응답 검증
    """

    def __init__(self, base_url: str | None = None, timeout: int | None = None):
        """
        Args:
            base_url: 백엔드 API URL (기본값: settings.api_base_url)
            timeout: 요청 타임아웃 초 (기본값: settings.API_TIMEOUT)
        """
        self.base_url = base_url or settings.api_base_url
        self.timeout = timeout or settings.API_TIMEOUT
        self.client = httpx.Client(timeout=self.timeout)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """HTTP 클라이언트 종료"""
        if hasattr(self, "client"):
            self.client.close()

    def send_message(
        self,
        message: str,
        user_id: str,
        conversation_id: str | None = None,
        session_context: dict[str, Any] | None = None,
    ) -> ChatResponse:
        """
        채팅 메시지를 백엔드로 전송하고 응답 받기

        Args:
            message: 사용자 메시지
            user_id: 사용자 ID
            conversation_id: 대화 ID (None이면 새 대화 생성)
            session_context: 선택적 세션 컨텍스트

        Returns:
            ChatResponse: AI 응답 및 컨텍스트 정보

        Raises:
            httpx.HTTPError: API 요청 실패 시
        """
        request_payload = ChatRequest(
            message=message,
            user_id=user_id,
            conversation_id=conversation_id,
            session_context=session_context,
        )

        try:
            response = self.client.post(
                f"{self.base_url}/chat/send",
                json=request_payload.model_dump(exclude_none=True),
            )
            response.raise_for_status()

            data = response.json()
            return ChatResponse(**data)

        except httpx.HTTPStatusError as e:
            logger.error(f"API request failed: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def get_conversation_history(
        self,
        conversation_id: str,
        user_id: str,
        limit: int | None = None,
    ) -> ConversationHistoryResponse:
        """
        대화 이력 조회

        Args:
            conversation_id: 대화 ID
            user_id: 사용자 ID
            limit: 메시지 개수 제한 (기본값: settings.DEFAULT_MESSAGE_LIMIT)

        Returns:
            ConversationHistoryResponse: 대화 메시지 목록
        """
        limit = limit or settings.DEFAULT_MESSAGE_LIMIT

        try:
            response = self.client.get(
                f"{self.base_url}/chat/history/{conversation_id}",
                params={"user_id": user_id, "limit": limit},
            )
            response.raise_for_status()

            data = response.json()
            return ConversationHistoryResponse(**data)

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch conversation history: {e}")
            raise

    def get_user_context(self, user_id: str) -> UserContextResponse:
        """
        사용자 컨텍스트 조회 (프로필, 최근 대화 등)

        Args:
            user_id: 사용자 ID

        Returns:
            UserContextResponse: 사용자 프로필 및 컨텍스트
        """
        try:
            response = self.client.get(f"{self.base_url}/chat/context/{user_id}")
            response.raise_for_status()

            data = response.json()
            return UserContextResponse(**data)

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch user context: {e}")
            raise

    def health_check(self) -> dict[str, Any]:
        """
        백엔드 health check

        Returns:
            dict: Health status information
        """
        try:
            # Health endpoint는 /api/v1 prefix 없이 직접 접근
            backend_base = str(settings.BACKEND_URL)
            response = self.client.get(f"{backend_base}/api/v1/health")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}
