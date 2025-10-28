"""
데이터 시각화 차트 생성 함수들
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


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


def create_price_heatmap(df: pd.DataFrame, price_column: str, colorscale: str, price_label: str):
    """가격 히트맵 생성"""
    df_chart = df.copy()
    
    if price_column not in df_chart.columns:
        st.warning(f"⚠️ 가격 컬럼 '{price_column}'을 찾을 수 없습니다.")
        return
    
    df_chart[price_column] = pd.to_numeric(df_chart[price_column], errors='coerce')
    
    # 거래일 컬럼 찾기 및 처리 (우선순위: deal_year/month/day > deal_date > 기타 date 컬럼)
    date_col = None
    
    # 1순위: deal_year, deal_month, deal_day 조합으로 날짜 생성
    if all(col in df_chart.columns for col in ['deal_year', 'deal_month', 'deal_day']):
        try:
            df_chart['deal_date'] = pd.to_datetime(
                df_chart['deal_year'].astype(str) + '-' + 
                df_chart['deal_month'].astype(str).str.zfill(2) + '-' + 
                df_chart['deal_day'].astype(str).str.zfill(2),
                errors='coerce'
            )
            date_col = 'deal_date'
            if not pd.api.types.is_datetime64_any_dtype(df_chart[date_col]):
                df_chart[date_col] = pd.to_datetime(df_chart[date_col], errors='coerce')
        except Exception as e:
            st.error(f"날짜 생성 오류: {e}")
            date_col = None
    
    # 2순위: 기존 deal_date 컬럼 사용
    elif 'deal_date' in df_chart.columns:
        date_col = 'deal_date'
        df_chart[date_col] = pd.to_datetime(df_chart[date_col], errors='coerce')
    
    # 3순위: year, month, day 조합으로 날짜 생성 (전월세 데이터용)
    elif all(col in df_chart.columns for col in ['year', 'month', 'day']):
        df_chart['deal_date'] = pd.to_datetime(
            df_chart[['year', 'month', 'day']], 
            errors='coerce'
        )
        date_col = 'deal_date'
    
    # 4순위: 기타 날짜 관련 컬럼 (거래일 우선)
    else:
        date_columns = [col for col in df_chart.columns if 'deal_date' in col.lower() or '거래일' in col or 'date' in col.lower()]
        # rgst_date 같은 등록일보다는 거래일을 우선시
        deal_date_cols = [col for col in date_columns if 'deal' in col.lower() or '거래' in col]
        if deal_date_cols:
            date_col = deal_date_cols[0]
        elif date_columns:
            date_col = date_columns[0]
        else:
            st.warning("⚠️ 날짜 컬럼을 찾을 수 없습니다.")
            date_col = None
        
        if date_col:
            df_chart[date_col] = pd.to_datetime(df_chart[date_col], errors='coerce')
    
    if date_col is not None:
        # 유효한 데이터만 필터링
        valid_data = df_chart.dropna(subset=[price_column, date_col])
        
        if not valid_data.empty:
            # 가격대 구간 생성
            if price_column == 'deal_amount':
                # 매매 데이터 - 억원 단위
                valid_data['price_range'] = pd.cut(
                    valid_data[price_column] / 10000,
                    bins=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, float('inf')],
                    labels=['0-1억', '1-2억', '2-3억', '3-4억', '4-5억', '5-6억', '6-7억', '7-8억', '8-9억', '9-10억', '10억+']
                )
            else:
                # 전월세 데이터 - 천만원 단위
                valid_data['price_range'] = pd.cut(
                    valid_data[price_column] / 1000,
                    bins=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, float('inf')],
                    labels=['0-1천만', '1-2천만', '2-3천만', '3-4천만', '4-5천만', '5-6천만', '6-7천만', '7-8천만', '8-9천만', '9-10천만', '10천만+']
                )
            
            # 날짜별, 가격대별 거래 건수 집계
            heatmap_data = valid_data.groupby([valid_data[date_col].dt.date, 'price_range']).size().unstack(fill_value=0)
            
            if not heatmap_data.empty:
                # 날짜를 오름차순으로 정렬하고 yyyy.mm.dd 형식으로 변환
                heatmap_data = heatmap_data.sort_index()
                date_labels = [date.strftime('%Y.%m.%d') for date in heatmap_data.index]
                
                # Plotly 히트맵 생성
                fig = go.Figure(data=go.Heatmap(
                    z=heatmap_data.values.T,  # 전치하여 축 바꾸기
                    x=date_labels,           # 날짜 라벨을 x축으로
                    y=heatmap_data.columns,  # 가격대를 y축으로
                    colorscale=colorscale,
                    hoverongaps=False,
                    hovertemplate=f'거래일: %{{x}}<br>{price_label}: %{{y}}<br>거래건수: %{{z}}<extra></extra>'
                ))
                
                fig.update_layout(
                    title=f'날짜별 {price_label}별 거래 건수',
                    xaxis_title='거래일',
                    yaxis_title=price_label,
                    height=400
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("히트맵 데이터가 없습니다.")
        else:
            st.info(f"유효한 {price_label} 및 날짜 데이터가 없습니다.")
    else:
        st.info("거래일 컬럼을 찾을 수 없습니다.")
