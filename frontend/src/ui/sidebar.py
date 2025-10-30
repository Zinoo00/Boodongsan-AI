"""
사이드바 UI 컴포넌트
"""

import streamlit as st
from datetime import datetime, timedelta
from ..config import AWS_REGION, KNOWLEDGE_BASE_ID, REGION_OPTIONS, DATA_LOADING_MODES


def render_sidebar():
    """사이드바 렌더링"""
    with st.sidebar:
        st.header("🔧 설정")
        
        # AWS 리전은 환경변수에서 가져옴
        aws_region = AWS_REGION
        
        # Knowledge Base ID는 환경변수에서 가져옴
        knowledge_base_id = KNOWLEDGE_BASE_ID
        
        # 💬 AI 채팅 설정
        st.subheader("💬 AI 채팅 설정")
        
        # 검색 타입 선택
        search_type = st.selectbox(
            "검색 타입",
            options=["hybrid", "vector", "keyword"],
            format_func=lambda x: {
                "hybrid": "🔀 하이브리드 (벡터 + 키워드)",
                "vector": "🧠 벡터 검색 (의미적 유사성)",
                "keyword": "🔍 키워드 검색 (정확한 매칭)"
            }[x],
            help="하이브리드: 가장 정확한 결과, 벡터: 의미적 유사성, 키워드: 정확한 키워드 매칭"
        )
        
        # 데이터 필터
        st.subheader("데이터 필터")
        selected_regions = st.multiselect(
            "지역 선택",
            REGION_OPTIONS,
            default=["분당구", "강남구"]
        )
        
        # 데이터 로딩 방식 선택
        data_loading_mode = st.radio(
            "데이터 로딩 방식",
            DATA_LOADING_MODES,
            help="년월 선택: 특정 년월의 데이터를 로드하고 일자로 필터링"
        )
        
        if data_loading_mode == "📅 년월 선택":
            # 년월 선택 모드
            st.info("💡 년월을 선택하면 해당 월의 모든 데이터를 로드하고 일자로 필터링할 수 있습니다.")
            selected_year = None
            selected_month = None
            date_range = None
        elif data_loading_mode == "🔄 최신 데이터":
            # 기존 최신 데이터 모드
            use_date_filter = st.checkbox(
                "날짜 필터 사용",
                value=True,
                help="체크 해제하면 모든 날짜의 데이터를 표시합니다"
            )
            
            if use_date_filter:
                date_range = st.date_input(
                    "거래일 범위",
                    value=(datetime.now() - timedelta(days=30), datetime.now()),
                    max_value=datetime.now()
                )
            else:
                date_range = None
            selected_year = None
            selected_month = None
        else:
            # 전체 데이터 모드
            date_range = None
            selected_year = None
            selected_month = None
            
        # 🔍 데이터 검색 설정
        st.subheader("🔍 데이터 검색 설정")
        
        max_results = st.slider(
            "최대 검색 결과 수",
            min_value=1,
            max_value=10,
            value=5
        )
    
    return {
        'aws_region': aws_region,
        'knowledge_base_id': knowledge_base_id,
        'search_type': search_type,
        'max_results': max_results,
        'selected_regions': selected_regions,
        'data_loading_mode': data_loading_mode,
        'date_range': date_range,
        'selected_year': selected_year,
        'selected_month': selected_month
    }
