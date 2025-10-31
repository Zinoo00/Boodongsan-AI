"""
BODA - Korean Real Estate AI Chatbot
Streamlit frontend for the BODA chatbot
"""

import logging
import uuid

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


# Title
st.title("🏠 BODA 챗봇")
st.caption("한국 부동산 AI 어시스턴트 - 매물 추천 및 정책 매칭")


# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# Chat input
if prompt := st.chat_input("메시지를 입력하세요..."):
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)

    # Add to history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Generate response
    with st.chat_message("assistant"):
        with st.spinner("답변 생성 중..."):
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

                # Show metadata
                col1, col2 = st.columns(2)
                with col1:
                    st.caption(f"⏱️ {response.processing_time_ms:.0f}ms")
                with col2:
                    if response.knowledge_mode:
                        mode_emoji = {
                            "naive": "🔍",
                            "local": "📍",
                            "global": "🌐",
                            "hybrid": "🔀",
                        }.get(response.knowledge_mode, "💡")
                        st.caption(f"{mode_emoji} {response.knowledge_mode.upper()}")

                # Add to history
                st.session_state.messages.append({"role": "assistant", "content": response.response})

            except Exception as e:
                error_msg = f"❌ 오류가 발생했습니다: {str(e)}"
                st.error(error_msg)
                logger.error(f"Chat error: {e}")

                # Add error to history
                st.session_state.messages.append({"role": "assistant", "content": error_msg})


# Sidebar
with st.sidebar:
    st.header("⚙️ 설정")

    # New chat button
    if st.button("🔄 새 대화", use_container_width=True):
        st.session_state.messages = []
        st.session_state.conversation_id = None
        st.rerun()

    st.divider()

    # User info
    st.subheader("👤 사용자 정보")
    st.text(f"ID: {st.session_state.user_id}")
    if st.session_state.conversation_id:
        st.text(f"대화: {st.session_state.conversation_id[:8]}...")

    st.divider()

    # Backend status
    st.subheader("🔧 시스템 상태")
    if st.button("상태 확인", use_container_width=True):
        try:
            health = st.session_state.api_client.health_check()
            if health.get("status") == "healthy":
                st.success("✅ 백엔드 정상")
            else:
                st.warning("⚠️ 백엔드 문제")
        except Exception as e:
            st.error(f"❌ 연결 실패: {str(e)}")
