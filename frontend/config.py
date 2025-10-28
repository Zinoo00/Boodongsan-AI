"""
Frontend configuration for BODA Streamlit chatbot.
환경 변수 및 애플리케이션 설정 관리
"""

import os
from typing import Any

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class FrontendSettings(BaseSettings):
    """Streamlit 프론트엔드 설정"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = Field(
        default="BODA - 부동산 AI 챗봇",
        description="애플리케이션 이름",
    )
    APP_DESCRIPTION: str = Field(
        default="한국 부동산 매물 추천 및 정부 정책 매칭 AI 챗봇",
        description="애플리케이션 설명",
    )
    APP_VERSION: str = Field(default="1.0.0", description="버전")

    # Backend API
    BACKEND_URL: HttpUrl = Field(
        default="http://localhost:8000",
        description="FastAPI 백엔드 URL",
    )
    API_V1_STR: str = Field(default="/api/v1", description="API 버전 prefix")
    API_TIMEOUT: int = Field(default=30, ge=5, le=300, description="API 타임아웃 (초)")

    # Chat Settings
    MAX_MESSAGE_LENGTH: int = Field(default=2000, ge=1, le=10000, description="최대 메시지 길이")
    DEFAULT_MESSAGE_LIMIT: int = Field(default=20, ge=1, le=200, description="기본 메시지 로드 개수")
    ENABLE_STREAMING: bool = Field(default=True, description="스트리밍 응답 활성화")

    # UI Settings
    THEME: str = Field(default="light", description="테마 (light/dark)")
    PRIMARY_COLOR: str = Field(default="#FF4B4B", description="Primary color")
    BACKGROUND_COLOR: str = Field(default="#FFFFFF", description="배경색")
    SECONDARY_BACKGROUND_COLOR: str = Field(default="#F0F2F6", description="보조 배경색")
    TEXT_COLOR: str = Field(default="#262730", description="텍스트 색상")

    # Session
    SESSION_TIMEOUT_MINUTES: int = Field(default=30, ge=5, le=1440, description="세션 타임아웃 (분)")

    # Feature Flags
    ENABLE_CONVERSATION_HISTORY: bool = Field(default=True, description="대화 이력 기능 활성화")
    ENABLE_USER_PROFILE: bool = Field(default=True, description="사용자 프로필 기능 활성화")
    ENABLE_PROPERTY_CARDS: bool = Field(default=True, description="매물 카드 표시 활성화")
    ENABLE_POLICY_CARDS: bool = Field(default=True, description="정책 카드 표시 활성화")

    # Debug
    DEBUG: bool = Field(default=False, description="디버그 모드")

    @property
    def api_base_url(self) -> str:
        """API base URL 반환"""
        return f"{self.BACKEND_URL}{self.API_V1_STR}"

    @property
    def chat_endpoint(self) -> str:
        """Chat 엔드포인트 URL"""
        return f"{self.api_base_url}/chat/send"

    @property
    def history_endpoint(self) -> str:
        """History 엔드포인트 URL (conversation_id placeholder)"""
        return f"{self.api_base_url}/chat/history/{{conversation_id}}"

    @property
    def user_context_endpoint(self) -> str:
        """User context 엔드포인트 URL (user_id placeholder)"""
        return f"{self.api_base_url}/chat/context/{{user_id}}"


# Global settings instance
settings = FrontendSettings()
