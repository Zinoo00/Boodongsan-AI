"""
Property card component for displaying real estate listings.
부동산 매물 정보를 카드 형태로 표시하는 컴포넌트
"""

from typing import Any

import streamlit as st


def format_price(price: int | float, transaction_type: str) -> str:
    """
    가격을 한국 단위로 포맷팅

    Args:
        price: 가격 (원)
        transaction_type: 거래 유형 (매매/전세/월세)

    Returns:
        포맷된 가격 문자열 (예: "5억 2천만원")
    """
    if not price or price == 0:
        return "가격 미정"

    eok = int(price // 100_000_000)  # 억
    man = int((price % 100_000_000) // 10_000)  # 만

    result = []
    if eok > 0:
        result.append(f"{eok}억")
    if man > 0:
        result.append(f"{man:,}만원")

    if not result:
        result.append(f"{price:,}원")

    return " ".join(result)


def format_area(area_pyeong: float | None, area_exclusive: float | None) -> str:
    """
    면적 정보 포맷팅 (평/제곱미터)

    Args:
        area_pyeong: 평수
        area_exclusive: 전용면적 (㎡)

    Returns:
        포맷된 면적 문자열
    """
    if area_pyeong and area_exclusive:
        return f"{area_pyeong:.1f}평 ({area_exclusive:.2f}㎡)"
    elif area_pyeong:
        return f"{area_pyeong:.1f}평"
    elif area_exclusive:
        return f"{area_exclusive:.2f}㎡"
    else:
        return "면적 정보 없음"


def render_property_card(property_data: dict[str, Any]) -> None:
    """
    부동산 매물 카드 렌더링

    Args:
        property_data: 매물 정보 딕셔너리
            - address: 주소
            - district: 구
            - dong: 동
            - property_type: 매물 유형 (아파트/빌라/오피스텔 등)
            - transaction_type: 거래 유형 (매매/전세/월세)
            - price: 가격
            - deposit: 보증금 (월세인 경우)
            - monthly_rent: 월세 (월세인 경우)
            - area_pyeong: 평수
            - area_exclusive: 전용면적
            - room_count: 방 개수
            - bathroom_count: 욕실 개수
            - floor: 층수
            - building_year: 건축년도
    """
    # 기본 정보 추출
    address = property_data.get("address", "주소 정보 없음")
    district = property_data.get("district", "")
    dong = property_data.get("dong", "")
    property_type = property_data.get("property_type", "매물")
    transaction_type = property_data.get("transaction_type", "")

    # 가격 정보
    price = property_data.get("price", 0)
    deposit = property_data.get("deposit", 0)
    monthly_rent = property_data.get("monthly_rent", 0)

    # 면적 정보
    area_pyeong = property_data.get("area_pyeong")
    area_exclusive = property_data.get("area_exclusive")

    # 상세 정보
    room_count = property_data.get("room_count", 0)
    bathroom_count = property_data.get("bathroom_count", 0)
    floor = property_data.get("floor")
    building_year = property_data.get("building_year")

    # 카드 렌더링
    with st.container():
        st.markdown("---")

        # 헤더: 매물 유형 + 거래 유형
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"### 🏠 {property_type} - {transaction_type}")
        with col2:
            # 가격 표시
            if transaction_type == "월세" and deposit and monthly_rent:
                price_str = f"{format_price(deposit, transaction_type)} / {format_price(monthly_rent, transaction_type)}"
            else:
                price_str = format_price(price, transaction_type)
            st.markdown(f"**{price_str}**")

        # 주소
        st.markdown(f"📍 **{address}**")
        if district or dong:
            location = f"{district} {dong}".strip()
            st.caption(location)

        # 상세 정보 그리드
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("면적", format_area(area_pyeong, area_exclusive))

        with col2:
            if room_count and bathroom_count:
                st.metric("구조", f"방{room_count}/욕{bathroom_count}")
            elif room_count:
                st.metric("방 개수", f"{room_count}개")

        with col3:
            if floor is not None:
                st.metric("층수", f"{floor}층")
            elif building_year:
                st.metric("건축년도", f"{building_year}년")

        # 추가 정보 (있는 경우)
        amenities = property_data.get("amenities", [])
        if amenities:
            st.caption(f"🔸 편의시설: {', '.join(amenities[:5])}")

        nearby_facilities = property_data.get("nearby_facilities", {})
        if nearby_facilities:
            facilities_str = ", ".join(
                f"{k}: {v}" for k, v in list(nearby_facilities.items())[:3]
            )
            st.caption(f"🔸 주변시설: {facilities_str}")


def render_property_list(properties: list[dict[str, Any]]) -> None:
    """
    여러 매물을 리스트 형태로 렌더링

    Args:
        properties: 매물 정보 리스트
    """
    if not properties:
        st.info("조건에 맞는 매물이 없습니다.")
        return

    st.markdown(f"### 🏘️ 추천 매물 ({len(properties)}건)")

    for idx, property_data in enumerate(properties, 1):
        with st.expander(
            f"매물 {idx}: {property_data.get('property_type', '매물')} - "
            f"{property_data.get('district', '')} {property_data.get('dong', '')}",
            expanded=(idx == 1),  # 첫 번째 매물만 펼침
        ):
            render_property_card(property_data)
