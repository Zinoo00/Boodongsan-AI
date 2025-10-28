"""
애플리케이션 설정 관리
"""

import os
import streamlit as st
from dotenv import load_dotenv
import logging

# 환경변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# AWS 설정
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
KNOWLEDGE_BASE_ID = os.getenv("KNOWLEDGE_BASE_ID", "")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID")
BEDROCK_INFERENCE_PROFILE_ID = os.getenv("BEDROCK_INFERENCE_PROFILE_ID")

# Streamlit 페이지 설정
def setup_page_config():
    """Streamlit 페이지 설정"""
    st.set_page_config(
        page_title="부동산 데이터 AI 어시스턴트",
        page_icon="🏠",
        layout="wide",
        initial_sidebar_state="expanded"
    )

def validate_environment():
    """환경변수 검증"""
    if not KNOWLEDGE_BASE_ID:
        st.error("❌ KNOWLEDGE_BASE_ID 환경변수가 설정되지 않았습니다. .env 파일을 확인해주세요.")
        st.stop()

    if not BEDROCK_MODEL_ID and not BEDROCK_INFERENCE_PROFILE_ID:
        st.error("❌ BEDROCK_MODEL_ID 또는 BEDROCK_INFERENCE_PROFILE_ID 환경변수가 설정되지 않았습니다. .env 파일을 확인해주세요.")
        st.stop()

# 데이터 타입 옵션
DATA_TYPE_OPTIONS = {
    "아파트 매매": "apt_trade",
    "아파트 전월세": "apt_rent", 
    "오피스텔 매매": "offi_trade",
    "오피스텔 전월세": "offi_rent",
    "연립다세대 매매": "rh_trade",
    "연립다세대 전월세": "rh_rent"
}

# 지역 옵션
REGION_OPTIONS = ["분당구", "강남구", "서초구", "송파구", "마포구"]

# 데이터 로딩 모드
DATA_LOADING_MODES = ["📅 년월 선택", "🔄 최신 데이터", "📊 전체 데이터"]
