"""
BODA - Korean Real Estate AI Chatbot
부동산 매물 추천 및 정부 정책 매칭 AI 챗봇 (Streamlit Frontend)

Features:
- LightRAG 기반 지식 그래프 검색
- 부동산 매물 추천
- 정부 주택 지원 정책 매칭
- 대화 이력 관리
"""

import logging
import uuid
from datetime import datetime
from typing import Any

import streamlit as st

from api_client import BODAAPIClient, ChatResponse
from components import (
    display_message,
    render_error_message,
    render_typing_indicator,
    render_welcome_message,
)
from components.policy_card import render_policy_list
from components.property_card import render_property_list
from config import settings

# 로깅 설정
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ==================== Page Configuration ====================

st.set_page_config(
    page_title=settings.APP_NAME,
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ==================== Session State Initialization ====================

def initialize_session_state():
    """세션 상태 초기화"""
    # 메시지 히스토리
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 사용자 정보
    if "user_id" not in st.session_state:
        st.session_state.user_id = f"user_{uuid.uuid4().hex[:8]}"

    # 대화 ID
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = None

    # API 클라이언트
    if "api_client" not in st.session_state:
        st.session_state.api_client = BODAAPIClient()

    # UI 상태
    if "show_debug_info" not in st.session_state:
        st.session_state.show_debug_info = settings.DEBUG

    # 백엔드 연결 상태
    if "backend_healthy" not in st.session_state:
        st.session_state.backend_healthy = None


initialize_session_state()


# ==================== Sidebar ====================

def render_sidebar():
    """사이드바 렌더링 (사용자 정보, 설정 등)"""
    with st.sidebar:
        st.title("🏠 BODA")
        st.caption(settings.APP_DESCRIPTION)
        st.divider()

        # 사용자 정보
        st.subheader("👤 사용자 정보")
        st.text_input(
            "사용자 ID",
            value=st.session_state.user_id,
            disabled=True,
            help="자동 생성된 사용자 ID입니다",
        )

        if st.session_state.conversation_id:
            st.text_input(
                "대화 ID",
                value=st.session_state.conversation_id,
                disabled=True,
                help="현재 대화의 고유 ID입니다",
            )

        st.divider()

        # 대화 관리
        st.subheader("💬 대화 관리")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("🔄 새 대화", use_container_width=True):
                st.session_state.messages = []
                st.session_state.conversation_id = None
                st.rerun()

        with col2:
            # TODO: 대화 이력 불러오기 기능
            st.button("📜 이력", use_container_width=True, disabled=True)

        st.divider()

        # 백엔드 상태 체크
        st.subheader("🔧 시스템 상태")

        if st.button("상태 확인", use_container_width=True):
            with st.spinner("백엔드 상태 확인 중..."):
                try:
                    health = st.session_state.api_client.health_check()
                    st.session_state.backend_healthy = health.get("status") == "healthy"

                    if st.session_state.backend_healthy:
                        st.success("✅ 백엔드 정상")
                    else:
                        st.error("❌ 백엔드 오류")

                    if settings.DEBUG:
                        with st.expander("상세 정보"):
                            st.json(health)

                except Exception as e:
                    st.session_state.backend_healthy = False
                    st.error(f"❌ 연결 실패: {str(e)}")
                    logger.error(f"Health check failed: {e}")

        # 현재 상태 표시
        if st.session_state.backend_healthy is True:
            st.success("✅ 백엔드 연결됨")
        elif st.session_state.backend_healthy is False:
            st.error("❌ 백엔드 연결 안됨")
        else:
            st.info("ℹ️ 상태 미확인")

        st.divider()

        # 설정
        st.subheader("⚙️ 설정")

        st.session_state.show_debug_info = st.checkbox(
            "디버그 정보 표시",
            value=st.session_state.show_debug_info,
        )

        # 앱 정보
        st.divider()
        st.caption(f"버전: {settings.APP_VERSION}")
        st.caption(f"백엔드: {settings.BACKEND_URL}")


# ==================== Main Chat Interface ====================

def _normalize_property_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Vector 검색 메타데이터를 카드 렌더링 형식으로 정규화"""
    normalized = dict(metadata)

    if "district" not in normalized and normalized.get("sigungu"):
        normalized["district"] = normalized.get("sigungu")

    if "dong" not in normalized and normalized.get("umd"):
        normalized["dong"] = normalized.get("umd")

    if "area_exclusive" not in normalized:
        if normalized.get("area"):
            normalized["area_exclusive"] = normalized["area"]
        elif normalized.get("area_m2"):
            normalized["area_exclusive"] = normalized["area_m2"]

    if "address" not in normalized:
        parts = [
            normalized.get("sido"),
            normalized.get("district") or normalized.get("sigungu"),
            normalized.get("dong"),
            normalized.get("jibun"),
        ]
        address_parts = [str(part).strip() for part in parts if part]
        if address_parts:
            normalized["address"] = " ".join(address_parts)

    return normalized


def _prepare_vector_cards(
    vector_results: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Vector 검색 결과를 매물/정책 카드 데이터로 분리"""
    property_cards: list[dict[str, Any]] = []
    policy_cards: list[dict[str, Any]] = []

    for item in vector_results:
        metadata = dict(item.get("metadata") or {})
        item_type_raw = item.get("type") or metadata.get("type") or metadata.get("document_type")
        item_type = str(item_type_raw).lower() if item_type_raw else ""

        # score와 원문 스니펫은 카드에서 참고용으로 사용 가능하도록 추가
        if "vector_score" not in metadata and item.get("score") is not None:
            metadata["vector_score"] = item["score"]
        if item.get("document") and "document_snippet" not in metadata:
            metadata["document_snippet"] = item["document"]

        if item_type.startswith("property"):
            property_cards.append(_normalize_property_metadata(metadata))
        elif item_type.startswith("policy"):
            policy_cards.append(metadata)

    return property_cards, policy_cards


def process_chat_response(response: ChatResponse) -> None:
    """
    채팅 응답 처리 및 UI 렌더링

    Args:
        response: ChatResponse 객체
    """
    # conversation_id 저장
    if not st.session_state.conversation_id:
        st.session_state.conversation_id = response.conversation_id

    # AI 응답 표시
    with st.chat_message("assistant"):
        st.markdown(response.response)

        # 처리 시간 표시
        processing_time = response.processing_time_ms
        st.caption(f"⏱️ 처리 시간: {processing_time:.0f}ms")

        # 지식 그래프 모드 표시
        if response.knowledge_mode:
            mode_emoji = {
                "naive": "🔍",
                "local": "📍",
                "global": "🌐",
                "hybrid": "🔀",
            }.get(response.knowledge_mode, "💡")

            cache_status = "캐시됨" if response.knowledge_cached else "신규 검색"
            st.caption(f"{mode_emoji} {response.knowledge_mode.upper()} 모드 · {cache_status}")

    vector_results = response.vector_results or []
    property_cards, policy_cards = _prepare_vector_cards(vector_results)

    if settings.ENABLE_PROPERTY_CARDS and property_cards:
        render_property_list(property_cards[:5])  # 최대 5개만 표시

    if settings.ENABLE_POLICY_CARDS and policy_cards:
        render_policy_list(policy_cards[:5])  # 최대 5개만 표시

    # 디버그 정보 표시
    if st.session_state.show_debug_info and response.rag_context:
        with st.expander("🔧 RAG Context (디버그)", expanded=False):
            st.json(response.rag_context)

    # 메시지를 세션에 추가
    st.session_state.messages.append({
        "role": "assistant",
        "content": response.response,
        "timestamp": datetime.now().isoformat(),
        "metadata": {
            "processing_time_ms": processing_time,
            "knowledge_mode": response.knowledge_mode,
            "knowledge_cached": response.knowledge_cached,
        },
    })


def main():
    """메인 애플리케이션 로직"""
    # 사이드바 렌더링
    render_sidebar()

    # 메인 컨텐츠
    st.title("💬 BODA 챗봇")

    # 환영 메시지 (첫 방문 시)
    if not st.session_state.messages:
        render_welcome_message()
    else:
        # 기존 대화 이력 표시
        for message in st.session_state.messages:
            role = message["role"]
            content = message["content"]
            timestamp = message.get("timestamp")

            display_message(role, content, timestamp)

    # 사용자 입력
    if user_input := st.chat_input(
        "메시지를 입력하세요...",
        max_chars=settings.MAX_MESSAGE_LENGTH,
    ):
        # 사용자 메시지 표시
        with st.chat_message("user"):
            st.markdown(user_input)

        # 세션에 추가
        st.session_state.messages.append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().isoformat(),
        })

        # AI 응답 생성
        try:
            # Typing indicator
            with st.spinner("답변 생성 중..."):
                response = st.session_state.api_client.send_message(
                    message=user_input,
                    user_id=st.session_state.user_id,
                    conversation_id=st.session_state.conversation_id,
                )

            # 응답 처리
            process_chat_response(response)

        except Exception as e:
            logger.error(f"Chat error: {e}")
            render_error_message(f"메시지 전송 중 오류가 발생했습니다: {str(e)}")

            # 에러 메시지도 세션에 추가
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"❌ 오류가 발생했습니다: {str(e)}",
                "timestamp": datetime.now().isoformat(),
                "metadata": {"error": True},
            })


# ==================== App Entry Point ====================

if __name__ == "__main__":
    main()
