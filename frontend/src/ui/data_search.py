"""
데이터 검색 UI 컴포넌트
"""

import streamlit as st
import logging
from ..models import RealEstateAssistant

logger = logging.getLogger(__name__)


def render_data_search(aws_region: str, knowledge_base_id: str, max_results: int, search_type: str = "hybrid"):
    """데이터 검색 UI 렌더링"""
    st.header("🔍 데이터 검색")
    
    # 검색 인터페이스
    search_query = st.text_input(
        "검색어를 입력하세요",
        placeholder="예: 분당구 아파트 전세, 강남구 오피스텔 월세"
    )
    
    if st.button("검색", type="primary"):
        if search_query:
            with st.spinner("데이터를 검색하고 있습니다..."):
                assistant = RealEstateAssistant(aws_region)
                
                if knowledge_base_id:
                    logger.info(f"데이터 검색 시작 - 쿼리: {search_query[:50]}..., 검색 타입: {search_type}")
                    results = assistant.query_knowledge_base(search_query, knowledge_base_id, max_results, search_type)
                    
                    if 'error' in results:
                        logger.error(f"검색 오류: {results['error']}")
                        st.error(f"❌ 검색 오류: {results['error']}")
                    elif 'retrievalResults' in results:
                        logger.info(f"검색 성공 - {len(results['retrievalResults'])}개 결과")
                        
                        # 각 검색 결과 상세 로그
                        for i, result in enumerate(results['retrievalResults'], 1):
                            score = result.get('score', 0)
                            content = result.get('content', {})
                            text_preview = content.get('text', '')[:100] + '...' if len(content.get('text', '')) > 100 else content.get('text', '')
                            logger.info(f"  검색결과 {i}: 신뢰도={score:.3f}, 내용='{text_preview}'")
                        
                        st.success(f"✅ {len(results['retrievalResults'])}개의 결과를 찾았습니다.")
                        
                        for i, result in enumerate(results['retrievalResults'], 1):
                            with st.expander(f"결과 {i} - 신뢰도: {result.get('score', 0):.2f}"):
                                content = result.get('content', {})
                                st.write("**내용:**")
                                st.write(content.get('text', ''))
                                
                                if 'location' in result:
                                    st.write("**출처:**")
                                    st.write(result['location'])
                    else:
                        logger.warning("검색 결과 없음")
                        st.warning("⚠️ 검색 결과가 없습니다.")
                else:
                    logger.warning("Knowledge Base ID가 설정되지 않음")
                    st.warning("⚠️ Knowledge Base ID가 설정되지 않았습니다.")
        else:
            st.warning("검색어를 입력해주세요.")
