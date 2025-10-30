"""
데이터 분석 UI 컴포넌트
"""

import streamlit as st
import pandas as pd
import logging
from datetime import datetime, timedelta
from ..models import RealEstateAssistant
from ..config import DATA_TYPE_OPTIONS
from ..charts import create_price_heatmap
from ..utils.data_loader import S3DataLoader

logger = logging.getLogger(__name__)


def render_data_analysis(aws_region: str, data_type: str, data_loading_mode: str, date_range=None, selected_year=None, selected_month=None, selected_regions=None, selected_region_labels=None, start_year_month=None, end_year_month=None):
    """데이터 분석 UI 렌더링"""
    st.header("📊 부동산 데이터 분석")
    
    # 지역 선택 여부 확인
    selected_regions = selected_regions or []
    selected_region_labels = selected_region_labels or []
    if not selected_regions:
        st.info("왼쪽에서 지역을 선택하면 해당 지역 데이터만 조회합니다.")
        return

    # S3에서 실제 데이터 로드
    with st.spinner("S3에서 데이터를 로드하고 있습니다..."):
        try:
            data_loader = S3DataLoader(region_name=aws_region)
            
            # 데이터 타입은 사이드바에서 선택된 값 사용
            
            # 데이터 로딩 방식에 따라 데이터 로드
            if data_loading_mode == "날짜 필터 사용":
                # 날짜 범위의 년월에 해당하는 파일만 로드 후, 일자 필터는 아래에서 적용
                if not (date_range and len(date_range) == 2 and date_range[0] and date_range[1]):
                    st.warning("⚠️ 날짜 범위를 선택해주세요.")
                    return
                start_date = pd.to_datetime(date_range[0])
                end_date = pd.to_datetime(date_range[1])
                # 년월 리스트 생성
                months = []
                cursor = pd.Timestamp(start_date.year, start_date.month, 1)
                end_cursor = pd.Timestamp(end_date.year, end_date.month, 1)
                while cursor <= end_cursor:
                    months.append((str(cursor.year), str(cursor.month).zfill(2)))
                    cursor = (cursor + pd.offsets.MonthBegin(1))

                frames = []
                for lawd_cd in selected_regions:
                    for (yy, mm) in months:
                        part = data_loader.load_data_by_year_month(data_type, lawd_cd, yy, mm)
                        if part is not None and not part.empty:
                            frames.append(part)
                df = pd.concat(frames, ignore_index=True) if frames else None
            elif data_loading_mode == "전체 조회":
                # 전체 데이터 로드 (여러 파일) - 각 지역별로 병합
                frames = []
                for lawd_cd in selected_regions:
                    part = data_loader.load_latest_data(data_type, lawd_cd, max_files=50)
                    if part is not None and not part.empty:
                        frames.append(part)
                df = pd.concat(frames, ignore_index=True) if frames else None
            
            if df is not None and not df.empty:
                # 데이터 전처리
                df = _preprocess_data(df, data_type)
                
                # 거래일 범위 필터 적용 (사이드바에서만 선택)
                if date_range is not None and len(date_range) == 2 and date_range[0] is not None and date_range[1] is not None:
                    df = _apply_date_filter(df, date_range)
                
                # 메트릭 및 차트 표시
                if df is not None and not df.empty:
                    _render_metrics(df)
                    _render_charts(df)
                    _render_data_table(df)
                else:
                    st.warning("⚠️ 필터링 후 데이터가 없습니다.")
            else:
                st.warning("⚠️ 데이터를 찾을 수 없습니다. S3 버킷과 데이터 경로를 확인해주세요.")
                
        except Exception as e:
            st.error(f"❌ 데이터 로드 중 오류가 발생했습니다: {str(e)}")
            logger.error(f"데이터 분석 탭 오류: {str(e)}")


def _load_data_by_year_month(data_loader, data_type, selected_regions, start_year_month, end_year_month):
    """년월별 데이터 로드 (사이드바에서 받은 기간으로만 로드)"""
    if not start_year_month or not end_year_month:
        st.warning("⚠️ 사이드바에서 시작/종료 년월을 선택해주세요.")
        return None

    # 년월을 년도와 월로 분리
    start_year, start_month = start_year_month.split('.')
    end_year, end_month = end_year_month.split('.')
    
    # 선택된 기간의 모든 년월 데이터 로드 (선택된 모든 지역에 대해 병합)
    all_dataframes = []
    current_year = int(start_year)
    current_month = int(start_month)
    end_year_int = int(end_year)
    end_month_int = int(end_month)
    
    while (current_year < end_year_int) or (current_year == end_year_int and current_month <= end_month_int):
        year_str = str(current_year)
        month_str = str(current_month).zfill(2)
        
        # 각 지역의 해당 년월 데이터 로드 후 병합
        monthly_frames = []
        for lawd_cd in selected_regions:
            monthly_df = data_loader.load_data_by_year_month(data_type, lawd_cd, year_str, month_str)
            if monthly_df is not None and not monthly_df.empty:
                monthly_frames.append(monthly_df)
        if monthly_frames:
            merged = pd.concat(monthly_frames, ignore_index=True)
            all_dataframes.append(merged)
            st.info(f"📅 {year_str}년 {month_str}월 데이터 로드: {len(merged)}건")
        
        # 다음 월로 이동
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1
    
    if all_dataframes:
        # 모든 데이터 통합
        df = pd.concat(all_dataframes, ignore_index=True)
        return df
    else:
        st.warning("⚠️ 선택된 기간에 데이터가 없습니다.")
        return None


def _setup_day_filtering(df):
    """일자 필터링 설정"""
    # 데이터의 날짜 범위 확인 (히트맵 생성 로직과 동일)
    date_col = _find_date_column(df)
    
    if date_col:
        # 유효한 날짜 범위 확인
        valid_dates = df[date_col].dropna()
        if not valid_dates.empty:
            min_date = valid_dates.min().date()
            max_date = valid_dates.max().date()
            
            st.info(f"📅 데이터 날짜 범위: {min_date} ~ {max_date}")
            
            # 일자 범위 선택
            use_day_filter = st.checkbox("일자 필터 사용", value=False)
            if use_day_filter:
                date_range = st.date_input(
                    "일자 범위",
                    value=(min_date, max_date),
                    min_value=min_date,
                    max_value=max_date
                )
                if len(date_range) == 2 and date_range[0] is not None and date_range[1] is not None:
                    df = _apply_date_filter(df, date_range)
        else:
            st.warning("⚠️ 유효한 날짜 데이터가 없습니다.")
    else:
        st.warning("⚠️ 날짜 컬럼을 찾을 수 없습니다.")
    
    return df


def _find_date_column(df):
    """날짜 컬럼 찾기"""
    # 1순위: deal_year, deal_month, deal_day 조합으로 날짜 생성
    if all(col in df.columns for col in ['deal_year', 'deal_month', 'deal_day']):
        try:
            df['deal_date'] = pd.to_datetime(
                df['deal_year'].astype(str) + '-' + 
                df['deal_month'].astype(str).str.zfill(2) + '-' + 
                df['deal_day'].astype(str).str.zfill(2),
                errors='coerce'
            )
            date_col = 'deal_date'
            if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
                df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            return date_col
        except Exception as e:
            st.error(f"일자 필터링 날짜 생성 오류: {e}")
            return None
    
    # 2순위: 기존 deal_date 컬럼 사용
    elif 'deal_date' in df.columns:
        date_col = 'deal_date'
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        return date_col
    
    # 3순위: year, month, day 조합으로 날짜 생성 (전월세 데이터용)
    elif all(col in df.columns for col in ['year', 'month', 'day']):
        df['deal_date'] = pd.to_datetime(
            df[['year', 'month', 'day']], 
            errors='coerce'
        )
        return 'deal_date'
    
    # 4순위: 기타 날짜 관련 컬럼 (거래일 우선)
    else:
        date_columns = [col for col in df.columns if 'deal_date' in col.lower() or '거래일' in col or 'date' in col.lower()]
        # rgst_date 같은 등록일보다는 거래일을 우선시
        deal_date_cols = [col for col in date_columns if 'deal' in col.lower() or '거래' in col]
        if deal_date_cols:
            date_col = deal_date_cols[0]
        elif date_columns:
            date_col = date_columns[0]
        else:
            st.warning("⚠️ 날짜 컬럼을 찾을 수 없습니다.")
            return None
        
        if date_col:
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            return date_col
    
    return None


def _preprocess_data(df, data_type):
    """데이터 전처리"""
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
    
    return df


def _apply_date_filter(df, date_range):
    """날짜 필터 적용"""
    # 날짜 컬럼 찾기
    date_col = None
    if all(col in df.columns for col in ['deal_year', 'deal_month', 'deal_day']):
        # deal_year, deal_month, deal_day 조합으로 날짜 생성
        try:
            df['deal_date'] = pd.to_datetime(
                df['deal_year'].astype(str) + '-' + 
                df['deal_month'].astype(str).str.zfill(2) + '-' + 
                df['deal_day'].astype(str).str.zfill(2),
                errors='coerce'
            )
            date_col = 'deal_date'
        except:
            pass
    elif any('deal_date' in col.lower() or '거래일' in col or 'date' in col.lower() for col in df.columns):
        # 기존 날짜 컬럼 사용
        date_columns = [col for col in df.columns if 'deal_date' in col.lower() or '거래일' in col or 'date' in col.lower()]
        if date_columns:
            date_col = date_columns[0]
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    
    # 날짜 필터링 적용
    if date_col is not None:
        start_date = pd.to_datetime(date_range[0])
        end_date = pd.to_datetime(date_range[1])
        # 날짜 범위 내 데이터만 필터링
        df = df[(df[date_col] >= start_date) & (df[date_col] <= end_date)]
        if df.empty:
            st.warning("⚠️ 선택한 거래일 범위에 해당하는 데이터가 없습니다.")
            df = None
    else:
        st.warning("⚠️ 날짜 컬럼을 찾을 수 없습니다. 날짜 필터링을 건너뜁니다.")
    
    return df


def _render_metrics(df):
    """메트릭 표시"""
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


def _render_charts(df):
    """차트 표시"""
    col1, col2 = st.columns(2)
    
    with col1:
        # 거래금액 또는 보증금 히트맵
        if 'deal_amount' in df.columns and not df['deal_amount'].isna().all():
            st.subheader("매매 거래 분포")
            create_price_heatmap(df, 'deal_amount', 'Blues', '가격대')
        elif 'deposit' in df.columns and not df['deposit'].isna().all():
            st.subheader("전월세 거래 분포")
            create_price_heatmap(df, 'deposit', 'Greens', '보증금대')
        else:
            st.info("거래금액/보증금 데이터가 없습니다.")
    
    with col2:
        # 면적 또는 월세 분포 차트
        if 'area' in df.columns and not df['area'].isna().all():
            st.subheader("면적 분포")
            numeric_areas = pd.to_numeric(df['area'], errors='coerce').dropna()
            if not numeric_areas.empty:
                st.bar_chart(numeric_areas.value_counts().head(20))
            else:
                st.info("유효한 면적 데이터가 없습니다.")
        elif 'monthly_rent' in df.columns and not df['monthly_rent'].isna().all():
            st.subheader("월세 분포")
            numeric_rents = pd.to_numeric(df['monthly_rent'], errors='coerce').dropna()
            if not numeric_rents.empty:
                st.bar_chart(numeric_rents.value_counts().head(20))
            else:
                st.info("유효한 월세 데이터가 없습니다.")
        else:
            st.info("면적/월세 데이터가 없습니다.")


def _render_data_table(df):
    """데이터 테이블 표시"""
    st.subheader("📋 상세 데이터")
    # 표시에서 제외할 컬럼 제거
    display_df = df.drop(columns=["수집년월", "파일경로", "deal_date"], errors='ignore')
    st.dataframe(
        display_df.head(100),  # 처음 100건만 표시
        width='stretch',
        hide_index=True
    )
