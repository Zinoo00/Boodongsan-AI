"""
채팅 UI 컴포넌트
"""

import streamlit as st
import logging
from ..models import RealEstateAssistant
from ..config import BEDROCK_MODEL_ID, BEDROCK_INFERENCE_PROFILE_ID
from ..utils.aws_knowledge_base import format_retrieval_results

logger = logging.getLogger(__name__)


def render_chat_interface(aws_region: str, knowledge_base_id: str, max_results: int):
    """채팅 인터페이스 렌더링"""
    st.header("💬 부동산 AI 어시스턴트와 대화하기")
    
    # 채팅 인터페이스
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # 채팅 기록 표시
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # 채팅 입력창을 화면 아래쪽에 고정 (사이드바 고려)
    st.markdown("""
    <style>
    .stChatInput {
        position: fixed !important;
        bottom: 0 !important;
        left: 21rem !important;  /* 사이드바 너비만큼 오른쪽으로 이동 */
        right: 0 !important;
        z-index: 999 !important;
        background: var(--background-color) !important;
        border-top: 1px solid var(--border-color) !important;
        padding: 1rem !important;
        box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.1) !important;
    }
    .main .block-container {
        padding-bottom: 100px !important;
    }
    @media (max-width: 768px) {
        .stChatInput {
            left: 0 !important;  /* 모바일에서는 전체 너비 사용 */
        }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 사용자 입력 (화면 아래쪽 고정)
    if prompt := st.chat_input("부동산에 대해 무엇이든 물어보세요!", key="chat_input"):
        # 사용자 메시지 추가
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # AI 응답 생성
        with st.chat_message("assistant"):
            with st.spinner("AI가 답변을 생성하고 있습니다..."):
                # Knowledge Base 검색
                assistant = RealEstateAssistant(aws_region)
                
                if knowledge_base_id:
                    logger.info(f"AI 채팅 시작 - Knowledge Base ID: {knowledge_base_id}")
                    knowledge_response = assistant.query_knowledge_base(prompt, knowledge_base_id, max_results)
                    
                    # 에러 체크
                    if 'error' in knowledge_response:
                        logger.error(f"Knowledge Base 검색 오류: {knowledge_response['error']}")
                        response = f"❌ Knowledge Base 검색 오류: {knowledge_response['error']}"
                    else:
                        # 컨텍스트 생성
                        context = format_retrieval_results(knowledge_response)
                        logger.info(f"생성된 컨텍스트 길이: {len(context)}자")
                        
                        # AI 응답 생성
                        logger.info("Claude 모델로 응답 생성 중...")
                        # Inference Profile 우선 사용
                        model_or_profile_id = BEDROCK_INFERENCE_PROFILE_ID or BEDROCK_MODEL_ID
                        response = assistant.generate_response(prompt, context, model_or_profile_id)
                        
                        # 응답이 에러 메시지인지 확인
                        if response.startswith("AWS Bedrock에 접근할 권한이 없습니다") or \
                           response.startswith("모델 ID가 올바르지 않습니다") or \
                           response.startswith("Bedrock 응답 생성 오류") or \
                           response.startswith("❌ BEDROCK_MODEL_ID"):
                            logger.error(f"Claude 모델 오류: {response}")
                            # 에러 메시지에 에러 코드 정보 추가
                            if "ValidationException" in response:
                                response = f"❌ **ValidationException**: {response}"
                            elif "AccessDeniedException" in response:
                                response = f"❌ **AccessDeniedException**: {response}"
                            elif "ResourceNotFoundException" in response:
                                response = f"❌ **ResourceNotFoundException**: {response}"
                            elif "ThrottlingException" in response:
                                response = f"❌ **ThrottlingException**: {response}"
                            else:
                                response = f"❌ {response}"
                        else:
                            logger.info(f"AI 응답 생성 완료 - 최종 응답 길이: {len(response)}자")
                else:
                    logger.warning("Knowledge Base ID가 설정되지 않음")
                    # Knowledge Base가 설정되지 않은 경우 기본 응답
                    response = "⚠️ Knowledge Base ID가 설정되지 않았습니다. 사이드바에서 Knowledge Base ID를 입력해주세요."
                
                st.markdown(response)
                
                # AI 메시지 추가
                st.session_state.messages.append({"role": "assistant", "content": response})
