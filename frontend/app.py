"""
BODA - Korean Real Estate AI Chatbot
Streamlit frontend following demo-ai-assistant design pattern
"""

import logging
import uuid

import streamlit as st
from htbuilder import div, styles
from htbuilder.units import rem

from api_client import BODAAPIClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Page config
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="BODA - 부동산 AI 어시스턴트",
    page_icon="🔎",
    layout="centered",
)

# -----------------------------------------------------------------------------
# Session initialization
# -----------------------------------------------------------------------------


def get_api_client():
    """API 클라이언트 반환 (캐싱)"""
    if "api_client" not in st.session_state:
        st.session_state.api_client = BODAAPIClient()
    return st.session_state.api_client


def get_user_id():
    """사용자 ID 반환 또는 생성"""
    if "user_id" not in st.session_state:
        st.session_state.user_id = f"user_{uuid.uuid4().hex[:8]}"
    return st.session_state.user_id


# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

# -----------------------------------------------------------------------------
# Suggestions - Korean real estate focused
# -----------------------------------------------------------------------------

SUGGESTIONS = {
    ":blue[:material/apartment:] 강남 아파트 추천": (
        "서울 강남구 아파트를 추천해주세요. 예산은 10억 정도입니다."
    ),
    ":green[:material/family_restroom:] 신혼부부 정책": (
        "신혼부부가 받을 수 있는 주거 지원 정책을 알려주세요."
    ),
    ":orange[:material/payments:] 전세 대출 조건": (
        "전세 대출 조건과 금리가 어떻게 되나요?"
    ),
    ":violet[:material/school:] 청년 주거 지원": (
        "청년이 받을 수 있는 주거 지원 정책은 무엇이 있나요?"
    ),
    ":red[:material/savings:] 저가 매물 검색": (
        "2억 이하로 살 수 있는 수도권 아파트가 있을까요?"
    ),
}


# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------


def get_response(prompt: str):
    """
    BODA RAG API로 응답 생성

    Args:
        prompt: 사용자 질문

    Returns:
        tuple: (response_text, metadata)
    """
    client = get_api_client()
    user_id = get_user_id()

    response = client.send_message(
        message=prompt,
        user_id=user_id,
        conversation_id=st.session_state.conversation_id,
    )

    # Update conversation ID if new
    if not st.session_state.conversation_id:
        st.session_state.conversation_id = response.conversation_id

    metadata = {
        "processing_time_ms": response.processing_time_ms,
        "knowledge_mode": response.knowledge_mode,
        "conversation_id": response.conversation_id,
    }

    return response.response, metadata


def show_feedback_controls(message_index: int):
    """피드백 컨트롤 표시"""
    st.write("")

    with st.popover("이 답변은 어땠나요?"):
        with st.form(key=f"feedback-{message_index}", border=False):
            with st.container():
                st.markdown(":small[평점]")
                rating = st.feedback(options="stars")

            details = st.text_area("추가 의견 (선택사항)")

            ""  # spacing

            if st.form_submit_button("피드백 보내기"):
                st.success("피드백 감사합니다!")


@st.dialog("서비스 안내")
def show_disclaimer_dialog():
    st.caption("""
        BODA는 한국 부동산 정보를 분석하여 매물 추천 및 정부 정책 매칭을
        제공하는 AI 어시스턴트입니다.

        **주의사항:**
        - AI가 제공하는 정보는 참고용이며, 실제 거래 전 전문가 상담을 권장합니다
        - 부동산 가격 및 정책 정보는 실시간으로 변동될 수 있습니다
        - 개인정보를 입력하지 마세요

        **데이터 출처:**
        - 국토교통부 공공데이터
        - 서울시 열린데이터

        이 서비스를 사용함으로써 위 내용에 동의하는 것으로 간주됩니다.
    """)


# -----------------------------------------------------------------------------
# Draw the UI
# -----------------------------------------------------------------------------

# Big icon at the top (reduced size)
st.html(div(style=styles(font_size=rem(2.5), line_height=1))["🔎"])

# Title row with horizontal layout
title_row = st.container()

with title_row:
    cols = st.columns([4, 1])
    with cols[0]:
        st.html(
            div(style=styles(font_size=rem(1.8), font_weight=600, margin_bottom=rem(1)))[
                "BODA 부동산 AI 어시스턴트"
            ]
        )

# Check user interaction states
user_just_asked_initial_question = (
    "initial_question" in st.session_state and st.session_state.initial_question
)

user_just_clicked_suggestion = (
    "selected_suggestion" in st.session_state and st.session_state.selected_suggestion
)

user_first_interaction = (
    user_just_asked_initial_question or user_just_clicked_suggestion
)

has_message_history = (
    "messages" in st.session_state and len(st.session_state.messages) > 0
)

# -----------------------------------------------------------------------------
# Welcome screen (no messages yet)
# -----------------------------------------------------------------------------

if not user_first_interaction and not has_message_history:
    st.session_state.messages = []

    with st.container():
        st.chat_input("무엇이든 물어보세요...", key="initial_question")

        selected_suggestion = st.pills(
            label="추천 질문",
            label_visibility="collapsed",
            options=SUGGESTIONS.keys(),
            key="selected_suggestion",
        )

    st.button(
        "&nbsp;:small[:gray[:material/info: 서비스 안내]]",
        type="tertiary",
        on_click=show_disclaimer_dialog,
    )

    st.stop()

# -----------------------------------------------------------------------------
# Chat interface (after first message)
# -----------------------------------------------------------------------------

# Chat input at the bottom
user_message = st.chat_input("추가 질문을 입력하세요...")

# Get message from initial question or suggestion
if not user_message:
    if user_just_asked_initial_question:
        user_message = st.session_state.initial_question
    if user_just_clicked_suggestion:
        user_message = SUGGESTIONS[st.session_state.selected_suggestion]

# Add restart button to title row
with title_row:
    with cols[1]:
        def clear_conversation():
            st.session_state.messages = []
            st.session_state.conversation_id = None
            st.session_state.initial_question = None
            st.session_state.selected_suggestion = None

        st.button(
            "다시 시작",
            icon=":material/refresh:",
            on_click=clear_conversation,
        )

# Display chat history
for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            st.container()  # Fix ghost message bug

        st.markdown(message["content"])

        if message["role"] == "assistant":
            # Show metadata if available
            if "metadata" in message:
                metadata = message["metadata"]
                mode = metadata.get("knowledge_mode")
                time_ms = metadata.get("processing_time_ms", 0)

                mode_labels = {
                    "naive": "기본 검색",
                    "local": "로컬 검색",
                    "global": "글로벌 검색",
                    "hybrid": "하이브리드",
                }
                mode_label = mode_labels.get(mode, mode) if mode else None

                info_parts = []
                if time_ms:
                    info_parts.append(f"처리시간: {time_ms:.0f}ms")
                if mode_label:
                    info_parts.append(f"모드: {mode_label}")

                if info_parts:
                    st.caption(" · ".join(info_parts))

            show_feedback_controls(i)

# Handle new user message
if user_message:
    # Escape $ for LaTeX issues
    user_message = user_message.replace("$", r"\$")

    # Display user message
    with st.chat_message("user"):
        st.text(user_message)

    # Display assistant response
    with st.chat_message("assistant"):
        try:
            with st.spinner("정보를 검색하고 있습니다..."):
                response_text, metadata = get_response(user_message)

            # Container to fix ghost message bug
            with st.container():
                st.markdown(response_text)

                # Show metadata
                mode = metadata.get("knowledge_mode")
                time_ms = metadata.get("processing_time_ms", 0)

                mode_labels = {
                    "naive": "기본 검색",
                    "local": "로컬 검색",
                    "global": "글로벌 검색",
                    "hybrid": "하이브리드",
                }
                mode_label = mode_labels.get(mode, mode) if mode else None

                info_parts = []
                if time_ms:
                    info_parts.append(f"처리시간: {time_ms:.0f}ms")
                if mode_label:
                    info_parts.append(f"모드: {mode_label}")

                if info_parts:
                    st.caption(" · ".join(info_parts))

                # Add to history
                st.session_state.messages.append({
                    "role": "user",
                    "content": user_message
                })
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response_text,
                    "metadata": metadata,
                })

                show_feedback_controls(len(st.session_state.messages) - 1)

        except Exception as e:
            error_msg = f"죄송합니다. 오류가 발생했습니다: {str(e)}"
            st.error(error_msg)
            logger.error(f"Chat error: {e}")

            # Add error to history
            st.session_state.messages.append({
                "role": "user",
                "content": user_message
            })
            st.session_state.messages.append({
                "role": "assistant",
                "content": error_msg,
                "is_error": True,
            })
