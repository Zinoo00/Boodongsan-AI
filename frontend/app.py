"""
부동산 데이터 대화형 인터페이스
AWS Knowledge Base와 연결된 Streamlit 애플리케이션
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import json
from typing import List, Dict, Any
import sys
import os
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.aws_knowledge_base import AWSKnowledgeBase, format_retrieval_results
from utils.data_loader import S3DataLoader, create_sample_data

# 환경변수 로드
load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="부동산 데이터 AI 어시스턴트",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# AWS 설정
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
KNOWLEDGE_BASE_ID = os.getenv("KNOWLEDGE_BASE_ID", "")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID")
BEDROCK_INFERENCE_PROFILE_ID = os.getenv("BEDROCK_INFERENCE_PROFILE_ID")

# 환경변수 확인
if not KNOWLEDGE_BASE_ID:
    st.error("❌ KNOWLEDGE_BASE_ID 환경변수가 설정되지 않았습니다. .env 파일을 확인해주세요.")
    st.stop()

if not BEDROCK_MODEL_ID and not BEDROCK_INFERENCE_PROFILE_ID:
    st.error("❌ BEDROCK_MODEL_ID 또는 BEDROCK_INFERENCE_PROFILE_ID 환경변수가 설정되지 않았습니다. .env 파일을 확인해주세요.")
    st.stop()

class RealEstateAssistant:
    """부동산 데이터 AI 어시스턴트 클래스"""
    
    def __init__(self, region_name: str = "ap-northeast-2"):
        self.kb_client = AWSKnowledgeBase(region_name)
        self.data_loader = S3DataLoader(region_name=region_name)
        
    def query_knowledge_base(self, query: str, knowledge_base_id: str, max_results: int = 5) -> Dict[str, Any]:
        """AWS Knowledge Base에서 데이터 검색"""
        return self.kb_client.retrieve_documents(knowledge_base_id, query, max_results)
    
    def generate_response(self, query: str, context: str, model_id: str = None) -> str:
        """Claude 모델을 사용하여 응답 생성"""
        return self.kb_client.generate_response(query, context, model_id)
    
    def get_data_summary(self, data_type: str, lawd_cd: str) -> Dict[str, Any]:
        """데이터 요약 정보 조회"""
        return self.data_loader.get_data_summary(data_type, lawd_cd)

def load_sample_data() -> pd.DataFrame:
    """샘플 부동산 데이터 로드"""
    return create_sample_data()

def create_price_trend_chart(df: pd.DataFrame):
    """가격 추이 차트 생성"""
    fig = px.line(
        df, 
        x='거래일', 
        y='보증금', 
        color='지역',
        title='지역별 보증금 추이',
        labels={'보증금': '보증금 (만원)', '거래일': '거래일'}
    )
    fig.update_layout(
        xaxis_title="거래일",
        yaxis_title="보증금 (만원)",
        hovermode='x unified'
    )
    return fig

def create_area_distribution_chart(df: pd.DataFrame):
    """면적 분포 차트 생성"""
    fig = px.histogram(
        df, 
        x='전용면적', 
        nbins=20,
        title='전용면적 분포',
        labels={'전용면적': '전용면적 (㎡)', 'count': '건수'}
    )
    return fig

def main():
    # 제목 및 설명
    st.title("🏠 부동산 데이터 AI 어시스턴트")
    st.markdown("---")
    
    # 사이드바
    with st.sidebar:
        st.header("🔧 설정")
        
        # AWS 설정
        st.subheader("AWS 설정")
        # AWS 리전은 환경변수에서 가져옴
        aws_region = AWS_REGION
        
        # Knowledge Base ID는 환경변수에서 가져옴
        knowledge_base_id = KNOWLEDGE_BASE_ID
        
        # 검색 설정
        st.subheader("검색 설정")
        max_results = st.slider(
            "최대 검색 결과 수",
            min_value=1,
            max_value=10,
            value=5
        )
        
        # 데이터 필터
        st.subheader("데이터 필터")
        selected_regions = st.multiselect(
            "지역 선택",
            ["분당구", "강남구", "서초구", "송파구", "마포구"],
            default=["분당구", "강남구"]
        )
        
        date_range = st.date_input(
            "거래일 범위",
            value=(datetime.now() - timedelta(days=30), datetime.now()),
            max_value=datetime.now()
        )
    
    # 메인 컨텐츠
    tab1, tab2, tab3 = st.tabs(["💬 AI 채팅", "📊 데이터 분석", "🔍 데이터 검색"])
    
    with tab1:
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
    
    with tab2:
        st.header("📊 부동산 데이터 분석")
        
        # S3에서 실제 데이터 로드
        with st.spinner("S3에서 데이터를 로드하고 있습니다..."):
            try:
                data_loader = S3DataLoader(region_name=aws_region)
                
                # 데이터 타입 선택
                data_type_options = {
                    "아파트 매매": "apt_trade",
                    "아파트 전월세": "apt_rent", 
                    "오피스텔 매매": "offi_trade",
                    "오피스텔 전월세": "offi_rent",
                    "연립다세대 매매": "rh_trade",
                    "연립다세대 전월세": "rh_rent"
                }
                
                selected_type_name = st.selectbox(
                    "데이터 타입 선택",
                    list(data_type_options.keys()),
                    help="분석할 부동산 데이터 타입을 선택하세요"
                )
                
                data_type = data_type_options[selected_type_name]
                
                # 최근 데이터 로드
                df = data_loader.load_latest_data(data_type, "41480")  # 파주시 코드
                
                if df is not None and not df.empty:
                    st.success(f"✅ {data_type} 데이터 로드 완료 ({len(df)}건)")
                    
                    # 데이터 전처리
                    if data_type in ["apt_trade", "apt_rent", "offi_trade", "offi_rent", "rh_trade", "rh_rent"]:
                        # 모든 부동산 데이터 타입 처리
                        if 'deal_amount' in df.columns:
                            # 쉼표 제거 후 숫자 변환
                            df['deal_amount'] = df['deal_amount'].astype(str).str.replace(',', '').str.replace(' ', '')
                            df['deal_amount'] = pd.to_numeric(df['deal_amount'], errors='coerce')
                        if 'area' in df.columns:
                            df['area'] = pd.to_numeric(df['area'], errors='coerce')
                        if 'floor' in df.columns:
                            df['floor'] = pd.to_numeric(df['floor'], errors='coerce')
                        if 'deposit' in df.columns:
                            # 전월세 데이터의 보증금 처리
                            df['deposit'] = df['deposit'].astype(str).str.replace(',', '').str.replace(' ', '')
                            df['deposit'] = pd.to_numeric(df['deposit'], errors='coerce')
                        if 'monthly_rent' in df.columns:
                            # 전월세 데이터의 월세 처리
                            df['monthly_rent'] = df['monthly_rent'].astype(str).str.replace(',', '').str.replace(' ', '')
                            df['monthly_rent'] = pd.to_numeric(df['monthly_rent'], errors='coerce')
                    
                    # 모든 데이터 타입에 대해 공통 전처리
                    for col in df.columns:
                        if df[col].dtype == 'object':
                            # 문자열 컬럼에서 쉼표와 공백 제거 후 숫자 변환 시도
                            try:
                                df[col] = df[col].astype(str).str.replace(',', '').str.replace(' ', '')
                                numeric_col = pd.to_numeric(df[col], errors='coerce')
                                # 숫자로 변환된 값이 50% 이상이면 숫자형으로 변환
                                if not numeric_col.isna().sum() / len(numeric_col) > 0.5:
                                    df[col] = numeric_col
                            except:
                                pass
                    
                    # 메트릭 표시
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric(
                            "총 데이터 건수",
                            len(df),
                            delta=f"{len(df)}건"
                        )
                    
                    with col2:
                        if 'deal_amount' in df.columns:
                            # 매매 데이터
                            avg_amount = df['deal_amount'].mean()
                            st.metric(
                                "평균 거래금액",
                                f"{avg_amount:,.0f}만원" if not pd.isna(avg_amount) else "N/A",
                                delta=f"{avg_amount/1000:.1f}억원" if not pd.isna(avg_amount) else ""
                            )
                        elif 'deposit' in df.columns:
                            # 전월세 데이터 - 보증금
                            avg_deposit = df['deposit'].mean()
                            st.metric(
                                "평균 보증금",
                                f"{avg_deposit:,.0f}만원" if not pd.isna(avg_deposit) else "N/A",
                                delta=f"{avg_deposit/1000:.1f}억원" if not pd.isna(avg_deposit) else ""
                            )
                        else:
                            st.metric("평균 거래금액", "N/A")
                    
                    with col3:
                        if 'area' in df.columns:
                            avg_area = df['area'].mean()
                            st.metric(
                                "평균 면적",
                                f"{avg_area:.1f}㎡" if not pd.isna(avg_area) else "N/A",
                                delta=f"{avg_area/3.3:.1f}평" if not pd.isna(avg_area) else ""
                            )
                        else:
                            st.metric("평균 면적", "N/A")
                    
                    with col4:
                        if 'floor' in df.columns:
                            # 층수 데이터
                            avg_floor = df['floor'].mean()
                            st.metric(
                                "평균 층수",
                                f"{avg_floor:.1f}층" if not pd.isna(avg_floor) else "N/A"
                            )
                        elif 'monthly_rent' in df.columns:
                            # 전월세 데이터 - 월세
                            avg_rent = df['monthly_rent'].mean()
                            st.metric(
                                "평균 월세",
                                f"{avg_rent:,.0f}만원" if not pd.isna(avg_rent) else "N/A"
                            )
                        else:
                            st.metric("평균 층수", "N/A")
                    
                    # 차트 표시
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if 'deal_amount' in df.columns and not df['deal_amount'].isna().all():
                            st.subheader("거래금액 분포")
                            # 숫자형 데이터만 필터링
                            numeric_amounts = pd.to_numeric(df['deal_amount'], errors='coerce').dropna()
                            if not numeric_amounts.empty:
                                st.bar_chart(numeric_amounts.value_counts().head(20))
                            else:
                                st.info("유효한 거래금액 데이터가 없습니다.")
                        elif 'deposit' in df.columns and not df['deposit'].isna().all():
                            st.subheader("보증금 분포")
                            # 숫자형 데이터만 필터링
                            numeric_deposits = pd.to_numeric(df['deposit'], errors='coerce').dropna()
                            if not numeric_deposits.empty:
                                st.bar_chart(numeric_deposits.value_counts().head(20))
                            else:
                                st.info("유효한 보증금 데이터가 없습니다.")
                        else:
                            st.info("거래금액/보증금 데이터가 없습니다.")
                    
                    with col2:
                        if 'area' in df.columns and not df['area'].isna().all():
                            st.subheader("면적 분포")
                            # 숫자형 데이터만 필터링
                            numeric_areas = pd.to_numeric(df['area'], errors='coerce').dropna()
                            if not numeric_areas.empty:
                                st.bar_chart(numeric_areas.value_counts().head(20))
                            else:
                                st.info("유효한 면적 데이터가 없습니다.")
                        elif 'monthly_rent' in df.columns and not df['monthly_rent'].isna().all():
                            st.subheader("월세 분포")
                            # 숫자형 데이터만 필터링
                            numeric_rents = pd.to_numeric(df['monthly_rent'], errors='coerce').dropna()
                            if not numeric_rents.empty:
                                st.bar_chart(numeric_rents.value_counts().head(20))
                            else:
                                st.info("유효한 월세 데이터가 없습니다.")
                        else:
                            st.info("면적/월세 데이터가 없습니다.")
                    
                    # 데이터 테이블
                    st.subheader("📋 상세 데이터")
                    st.dataframe(
                        df.head(100),  # 처음 100건만 표시
                        use_container_width=True,
                        hide_index=True
                    )
                    
                else:
                    st.warning("⚠️ 데이터를 찾을 수 없습니다. S3 버킷과 데이터 경로를 확인해주세요.")
                    
            except Exception as e:
                st.error(f"❌ 데이터 로드 중 오류가 발생했습니다: {str(e)}")
                logger.error(f"데이터 분석 탭 오류: {str(e)}")
    
    with tab3:
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
                        logger.info(f"데이터 검색 시작 - 쿼리: {search_query[:50]}...")
                        results = assistant.query_knowledge_base(search_query, knowledge_base_id, max_results)
                        
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

if __name__ == "__main__":
    main()
