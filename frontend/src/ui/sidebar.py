"""
사이드바 UI 컴포넌트
"""

import streamlit as st
from datetime import datetime, timedelta
from ..config import AWS_REGION, KNOWLEDGE_BASE_ID, DATA_LOADING_MODES, DATA_TYPE_OPTIONS
from ..services.opensearch_service import get_level2_regions
from ..utils.data_loader import S3DataLoader


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
        
        # 📊 데이터 분석 설정 - 데이터 타입을 사이드바로 이동
        st.subheader("📊 데이터 분석 설정")
        selected_type_name = st.selectbox(
            "데이터 타입",
            list(DATA_TYPE_OPTIONS.keys()),
            help="분석/조회에 사용할 데이터 타입을 선택하세요"
        )
        selected_data_type = DATA_TYPE_OPTIONS[selected_type_name]
        
        try:
            dynamic_regions = get_level2_regions()
        except Exception:
            dynamic_regions = []

        region_options = dynamic_regions
        if not region_options:
            st.warning("OpenSearch에서 지역 목록을 불러오지 못했습니다. 환경변수나 인덱스를 확인해주세요.")

        selected_regions = st.multiselect(
            "지역 선택",
            region_options,
            format_func=lambda x: x[1],
            default=[]
        )
        
        # 데이터 로딩 방식 선택 (두 가지 옵션만 제공)
        data_loading_mode = st.radio(
            "데이터 로딩 방식",
            ["날짜 필터 사용", "전체 조회"],
            help="날짜 필터를 사용하거나 전체 데이터를 조회합니다."
        )

        if data_loading_mode == "날짜 필터 사용":
            date_range = st.date_input(
                "거래일 범위",
                value=(datetime.now() - timedelta(days=30), datetime.now()),
                max_value=datetime.now()
            )
        else:
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
        'selected_regions': [code for code, _ in selected_regions],
        'selected_region_labels': [label for _, label in selected_regions],
        'data_loading_mode': data_loading_mode,
        'date_range': date_range,
        'selected_year': selected_year,
        'selected_month': selected_month,
        'data_type': selected_data_type
    }
