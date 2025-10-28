"""
Chat interface helper functions.
채팅 인터페이스 관련 헬퍼 함수
"""

from datetime import datetime

import streamlit as st


def format_timestamp(timestamp: str | datetime | None = None) -> str:
    """
    타임스탬프를 읽기 쉬운 형식으로 포맷팅

    Args:
        timestamp: ISO 형식 문자열 또는 datetime 객체

    Returns:
        포맷된 시간 문자열 (예: "2025-01-15 14:30")
    """
    if timestamp is None:
        timestamp = datetime.now()
    elif isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            return timestamp  # 파싱 실패 시 원본 반환

    return timestamp.strftime("%Y-%m-%d %H:%M")


def display_message(role: str, content: str, timestamp: str | datetime | None = None) -> None:
    """
    채팅 메시지 표시

    Args:
        role: "user" 또는 "assistant"
        content: 메시지 내용
        timestamp: 메시지 시간 (선택)
    """
    with st.chat_message(role):
        st.markdown(content)
        if timestamp:
            st.caption(f"⏰ {format_timestamp(timestamp)}")


def render_typing_indicator() -> None:
    """
    AI 응답 대기 중 typing indicator 표시
    """
    with st.chat_message("assistant"):
        with st.spinner("답변을 생성하고 있습니다..."):
            pass


def render_error_message(error: str) -> None:
    """
    에러 메시지 표시

    Args:
        error: 에러 메시지 내용
    """
    st.error(f"❌ 오류: {error}")


def render_welcome_message() -> None:
    """
    초기 환영 메시지 표시
    """
    welcome_text = """
    👋 안녕하세요! BODA 부동산 AI 챗봇입니다.

    **도움을 드릴 수 있는 내용:**
    - 🏠 부동산 매물 추천 (아파트, 빌라, 오피스텔 등)
    - 📋 정부 주택 지원 정책 매칭
    - 💰 전세/월세 시세 정보
    - 📍 지역별 매물 검색

    **예시 질문:**
    - "강남구 아파트 전세 5억 이하 추천해줘"
    - "청년 대상 주택 지원 정책 알려줘"
    - "역삼동 오피스텔 월세 매물 찾아줘"

    무엇을 도와드릴까요?
    """
    with st.chat_message("assistant"):
        st.markdown(welcome_text)


def render_system_info(info: dict) -> None:
    """
    시스템 정보 표시 (디버그용)

    Args:
        info: 시스템 정보 딕셔너리
    """
    with st.expander("🔧 시스템 정보 (디버그)", expanded=False):
        st.json(info)
