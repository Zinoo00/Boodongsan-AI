"""
부동산 데이터 대화형 인터페이스 메인 앱
"""

import streamlit as st
from .config import setup_page_config, validate_environment
from .ui import render_sidebar, render_chat_interface, render_data_analysis, render_data_search


def main():
    """메인 애플리케이션 함수"""
    # 페이지 설정
    setup_page_config()
    
    # 환경변수 검증
    validate_environment()
    
    # 제목 및 설명
    st.title("🏠 부동산 데이터 AI 어시스턴트")
    st.markdown("---")
    
    # 사이드바 렌더링 및 설정값 가져오기
    sidebar_config = render_sidebar()
    
    # 메인 컨텐츠
    tab1, tab2, tab3 = st.tabs(["💬 AI 채팅", "📊 데이터 분석", "🔍 데이터 검색"])
    
    with tab1:
        render_chat_interface(
            sidebar_config['aws_region'],
            sidebar_config['knowledge_base_id'],
            sidebar_config['max_results']
        )
    
    with tab2:
        render_data_analysis(
            sidebar_config['aws_region'],
            sidebar_config['data_loading_mode'],
            sidebar_config['date_range'],
            sidebar_config['selected_year'],
            sidebar_config['selected_month']
        )
    
    with tab3:
        render_data_search(
            sidebar_config['aws_region'],
            sidebar_config['knowledge_base_id'],
            sidebar_config['max_results']
        )


if __name__ == "__main__":
    main()
