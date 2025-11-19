"""
BODA - Korean Real Estate AI Chatbot
Streamlit frontend with demo-ai-assistant inspired design
"""

import logging
import uuid
from datetime import datetime

import streamlit as st

from api_client import BODAAPIClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Page config
st.set_page_config(
    page_title="BODA - 부동산 AI 챗봇",
    page_icon="🏠",
    layout="centered",
)


# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "user_id" not in st.session_state:
    st.session_state.user_id = f"user_{uuid.uuid4().hex[:8]}"

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

if "api_client" not in st.session_state:
    st.session_state.api_client = BODAAPIClient()

if "selected_suggestion" not in st.session_state:
    st.session_state.selected_suggestion = None


# Helper functions
def reset_conversation():
    """새 대화 시작"""
    st.session_state.messages = []
    st.session_state.conversation_id = None
    st.session_state.selected_suggestion = None


def send_message(prompt: str):
    """메시지 전송 및 응답 받기"""
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)

    # Add to history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Generate response
    with st.chat_message("assistant"):
        try:
            response = st.session_state.api_client.send_message(
                message=prompt,
                user_id=st.session_state.user_id,
                conversation_id=st.session_state.conversation_id,
            )

            # Update conversation ID
            if not st.session_state.conversation_id:
                st.session_state.conversation_id = response.conversation_id

            # Display response
            st.markdown(response.response)

            # Show metadata in expandable section
            with st.expander("📊 응답 정보", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.caption(f"⏱️ 처리 시간: {response.processing_time_ms:.0f}ms")
                with col2:
                    if response.knowledge_mode:
                        mode_emoji = {
                            "naive": "🔍",
                            "local": "📍",
                            "global": "🌐",
                            "hybrid": "🔀",
                        }.get(response.knowledge_mode, "💡")
                        st.caption(f"{mode_emoji} 모드: {response.knowledge_mode.upper()}")

            # Feedback section
            with st.popover("💬 피드백"):
                st.write("이 답변이 도움이 되셨나요?")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("👍 도움됨", key=f"thumbs_up_{len(st.session_state.messages)}"):
                        st.success("피드백 감사합니다!")
                with col2:
                    if st.button("👎 개선 필요", key=f"thumbs_down_{len(st.session_state.messages)}"):
                        st.info("피드백이 기록되었습니다.")

            # Add to history
            st.session_state.messages.append({
                "role": "assistant",
                "content": response.response,
                "metadata": {
                    "processing_time_ms": response.processing_time_ms,
                    "knowledge_mode": response.knowledge_mode,
                }
            })

        except Exception as e:
            error_msg = f"죄송합니다. 오류가 발생했습니다: {str(e)}"
            st.error(error_msg)
            logger.error(f"Chat error: {e}")

            # Add error to history
            st.session_state.messages.append({
                "role": "assistant",
                "content": error_msg,
                "is_error": True
            })


# Main UI
st.title("🏠 BODA 챗봇")
st.caption("한국 부동산 AI 어시스턴트 - 매물 추천 및 정책 매칭")

# Welcome screen with suggestions (shown when no messages)
if not st.session_state.messages:
    st.markdown("---")

    st.markdown("""
    ### 안녕하세요! 👋

    BODA는 한국 부동산 정보를 분석하여 최적의 매물과 정부 지원 정책을 추천해드립니다.

    아래 질문 예시를 선택하거나 직접 질문을 입력해주세요:
    """)

    # Suggestion pills with colors
    st.markdown("#### 💡 질문 예시")

    suggestions = [
        {
            "text": "서울 강남구 아파트 추천해주세요",
            "color": "blue",
            "icon": "🏢",
            "category": "매물 검색"
        },
        {
            "text": "신혼부부 정책 지원 알려주세요",
            "color": "green",
            "icon": "👶",
            "category": "정책 정보"
        },
        {
            "text": "전세 대출 조건이 궁금해요",
            "color": "orange",
            "icon": "💰",
            "category": "대출 정보"
        },
        {
            "text": "2억 이하 아파트 찾아주세요",
            "color": "red",
            "icon": "🔍",
            "category": "가격대별"
        },
        {
            "text": "청년 주거 지원 정책 있나요?",
            "color": "violet",
            "icon": "🎓",
            "category": "청년 지원"
        },
        {
            "text": "재개발 지역 정보 알려주세요",
            "color": "rainbow",
            "icon": "🏗️",
            "category": "개발 정보"
        },
    ]

    # Display suggestions in grid (2 columns)
    cols = st.columns(2)
    for idx, suggestion in enumerate(suggestions):
        col_idx = idx % 2
        with cols[col_idx]:
            color = suggestion["color"]
            if st.button(
                f"{suggestion['icon']} {suggestion['text']}",
                key=f"suggestion_{idx}",
                use_container_width=True,
                type="secondary"
            ):
                st.session_state.selected_suggestion = suggestion["text"]
                send_message(suggestion["text"])
                st.rerun()

    st.markdown("---")

    # Additional info
    with st.expander("ℹ️ BODA 사용 가이드"):
        st.markdown("""
        **BODA가 도와드릴 수 있는 것들:**

        - 🏘️ **매물 추천**: 지역, 가격대, 평수 등 조건에 맞는 부동산 검색
        - 📋 **정책 매칭**: 나이, 소득, 혼인 여부 등에 따른 정부 지원 정책 안내
        - 💡 **시장 분석**: 특정 지역의 시장 동향 및 가격 추세 정보
        - 🤔 **상담**: 부동산 관련 궁금한 점에 대한 상담

        **사용 팁:**
        - 구체적인 조건을 말씀해주시면 더 정확한 추천이 가능합니다
        - "30대, 연소득 5천만원, 강남 선호" 처럼 상세히 알려주세요
        - 여러 조건을 조합해서 질문하실 수 있습니다
        """)

else:
    # Display chat history
    for idx, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            # Check if this is an error message
            is_error = message.get("is_error", False)

            if is_error:
                st.error(message["content"])
            else:
                st.markdown(message["content"])

            # Show metadata for assistant messages
            if message["role"] == "assistant" and not is_error and "metadata" in message:
                metadata = message["metadata"]
                with st.expander("📊 응답 정보", expanded=False):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.caption(f"⏱️ {metadata.get('processing_time_ms', 0):.0f}ms")
                    with col2:
                        mode = metadata.get('knowledge_mode')
                        if mode:
                            mode_emoji = {
                                "naive": "🔍",
                                "local": "📍",
                                "global": "🌐",
                                "hybrid": "🔀",
                            }.get(mode, "💡")
                            st.caption(f"{mode_emoji} {mode.upper()}")

# Chat input (always shown at bottom)
if prompt := st.chat_input("메시지를 입력하세요..."):
    send_message(prompt)
    st.rerun()


# Sidebar
with st.sidebar:
    st.markdown("### ⚙️ 대화 관리")

    # New chat button with icon
    if st.button(
        ":material/refresh: 새 대화 시작",
        use_container_width=True,
        type="primary"
    ):
        reset_conversation()
        st.rerun()

    # Message count
    if st.session_state.messages:
        st.caption(f"💬 메시지: {len(st.session_state.messages)}개")

    st.divider()

    # User info section
    st.markdown("### 👤 사용자 정보")
    st.text(f"ID: {st.session_state.user_id}")
    if st.session_state.conversation_id:
        st.text(f"대화: {st.session_state.conversation_id[:8]}...")

    st.divider()

    # System status
    st.markdown("### 🔧 시스템 상태")
    if st.button("상태 확인", use_container_width=True):
        with st.spinner("확인 중..."):
            try:
                health = st.session_state.api_client.health_check()
                if health.get("status") == "healthy":
                    st.success("✅ 백엔드 정상 작동 중")
                else:
                    st.warning("⚠️ 백엔드 문제 발생")
                    st.json(health)
            except Exception as e:
                st.error(f"❌ 연결 실패: {str(e)}")

    st.divider()

    # About section
    with st.expander("ℹ️ BODA 정보"):
        st.markdown("""
        **BODA** (부동산 AI 챗봇)

        - 🏗️ LightRAG + Claude Sonnet 4.5
        - 🗄️ PostgreSQL + pgvector
        - 🚀 FastAPI + Streamlit

        © 2025 BODA Team
        """)
