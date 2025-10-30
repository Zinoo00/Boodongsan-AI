"""
채팅 UI 컴포넌트
"""

import streamlit as st
import logging
from ..models import RealEstateAssistant
from ..config import BEDROCK_MODEL_ID, BEDROCK_INFERENCE_PROFILE_ID
from ..utils.aws_knowledge_base import format_retrieval_results

logger = logging.getLogger(__name__)


def render_chat_interface(aws_region: str, knowledge_base_id: str, max_results: int, search_type: str = "hybrid", model_or_profile_id: str | None = None):
    """채팅 인터페이스 렌더링"""
    st.header("💬 부동산 AI 어시스턴트와 대화하기")
    
    # 채팅 인터페이스
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # 채팅 기록 표시
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # 사용자 입력 
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
                    logger.info(f"AI 채팅 시작 - Knowledge Base ID: {knowledge_base_id}, 검색 타입: {search_type}")
                    knowledge_response = assistant.query_knowledge_base(prompt, knowledge_base_id, max_results, search_type)
                    
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
                        # 사이드바 선택 > 환경변수 우선순위 적용
                        chosen_model = model_or_profile_id or BEDROCK_INFERENCE_PROFILE_ID or BEDROCK_MODEL_ID
                        response = assistant.generate_response(prompt, context, chosen_model)
                        
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
