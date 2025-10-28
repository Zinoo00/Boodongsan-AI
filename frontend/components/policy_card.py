"""
Policy card component for displaying government housing policies.
정부 주택 정책 정보를 카드 형태로 표시하는 컴포넌트
"""

from typing import Any

import streamlit as st


def render_eligibility_badge(is_eligible: bool, match_score: float | None = None) -> None:
    """
    자격 여부 배지 렌더링

    Args:
        is_eligible: 자격 여부
        match_score: 매칭 점수 (0-100)
    """
    if is_eligible:
        if match_score and match_score >= 80:
            st.success("✅ 높은 적합도")
        else:
            st.success("✅ 지원 가능")
    else:
        st.warning("⚠️ 일부 조건 불충족")


def format_amount(amount: int | float | None) -> str:
    """
    금액을 한국 단위로 포맷팅

    Args:
        amount: 금액 (원)

    Returns:
        포맷된 금액 문자열
    """
    if not amount or amount == 0:
        return "미정"

    eok = int(amount // 100_000_000)
    man = int((amount % 100_000_000) // 10_000)

    result = []
    if eok > 0:
        result.append(f"{eok}억")
    if man > 0:
        result.append(f"{man:,}만원")

    if not result:
        result.append(f"{amount:,}원")

    return " ".join(result)


def render_policy_card(policy_data: dict[str, Any], match_info: dict[str, Any] | None = None) -> None:
    """
    정부 주택 정책 카드 렌더링

    Args:
        policy_data: 정책 정보 딕셔너리
            - policy_name: 정책명
            - policy_type: 정책 유형
            - category: 카테고리
            - summary: 요약
            - benefits: 혜택 내용
            - target_demographic: 대상
            - age_min, age_max: 연령 제한
            - income_max: 소득 제한
            - support_amount_min, support_amount_max: 지원 금액
            - interest_rate: 금리
            - application_url: 신청 URL

        match_info: 매칭 정보 (선택)
            - is_eligible: 자격 여부
            - match_score: 매칭 점수
            - unmet_conditions: 불충족 조건 목록
    """
    # 기본 정보 추출
    policy_name = policy_data.get("policy_name", "정책명 없음")
    policy_type = policy_data.get("policy_type", "")
    category = policy_data.get("category", "")
    summary = policy_data.get("summary", "")
    benefits = policy_data.get("benefits", "")
    target_demographic = policy_data.get("target_demographic", "")

    # 자격 조건
    age_min = policy_data.get("age_min")
    age_max = policy_data.get("age_max")
    income_max = policy_data.get("income_max")

    # 지원 내용
    support_amount_min = policy_data.get("support_amount_min")
    support_amount_max = policy_data.get("support_amount_max")
    interest_rate = policy_data.get("interest_rate")

    # 신청 정보
    application_url = policy_data.get("application_url")
    administering_organization = policy_data.get("administering_organization", "")

    # 카드 렌더링
    with st.container():
        st.markdown("---")

        # 헤더: 정책명 + 유형
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"### 📋 {policy_name}")
            if policy_type or category:
                st.caption(f"{policy_type} · {category}")
        with col2:
            # 매칭 정보가 있으면 자격 배지 표시
            if match_info:
                is_eligible = match_info.get("is_eligible", False)
                match_score = match_info.get("match_score")
                render_eligibility_badge(is_eligible, match_score)

        # 요약
        if summary:
            st.markdown(f"**{summary}**")

        # 대상
        if target_demographic:
            st.markdown(f"👥 **대상**: {target_demographic}")

        # 자격 조건
        conditions = []
        if age_min is not None or age_max is not None:
            age_str = ""
            if age_min and age_max:
                age_str = f"{age_min}세 ~ {age_max}세"
            elif age_min:
                age_str = f"{age_min}세 이상"
            elif age_max:
                age_str = f"{age_max}세 이하"
            conditions.append(f"연령: {age_str}")

        if income_max:
            conditions.append(f"소득: 연 {format_amount(income_max)} 이하")

        if conditions:
            st.markdown("**📌 자격 조건**")
            for condition in conditions:
                st.caption(f"  • {condition}")

        # 지원 내용
        col1, col2 = st.columns(2)

        with col1:
            if support_amount_min or support_amount_max:
                if support_amount_min and support_amount_max:
                    amount_str = f"{format_amount(support_amount_min)} ~ {format_amount(support_amount_max)}"
                elif support_amount_max:
                    amount_str = f"최대 {format_amount(support_amount_max)}"
                elif support_amount_min:
                    amount_str = f"최소 {format_amount(support_amount_min)}"
                else:
                    amount_str = "금액 미정"

                st.metric("지원 금액", amount_str)

        with col2:
            if interest_rate is not None:
                st.metric("금리", f"{interest_rate}%")

        # 혜택 내용
        if benefits:
            with st.expander("💰 혜택 상세"):
                st.markdown(benefits)

        # 불충족 조건 (매칭 정보가 있고 자격이 없는 경우)
        if match_info and not match_info.get("is_eligible"):
            unmet_conditions = match_info.get("unmet_conditions", [])
            if unmet_conditions:
                with st.expander("⚠️ 불충족 조건", expanded=False):
                    for condition in unmet_conditions:
                        st.caption(f"  • {condition}")

        # 신청 정보
        if application_url:
            st.markdown(f"🔗 [온라인 신청하기]({application_url})")

        if administering_organization:
            st.caption(f"주관: {administering_organization}")


def render_policy_list(
    policies: list[dict[str, Any]],
    match_info_list: list[dict[str, Any]] | None = None,
) -> None:
    """
    여러 정책을 리스트 형태로 렌더링

    Args:
        policies: 정책 정보 리스트
        match_info_list: 각 정책에 대한 매칭 정보 리스트 (선택)
    """
    if not policies:
        st.info("조건에 맞는 정책이 없습니다.")
        return

    st.markdown(f"### 🏛️ 지원 가능한 정책 ({len(policies)}건)")

    for idx, policy_data in enumerate(policies):
        match_info = match_info_list[idx] if match_info_list and idx < len(match_info_list) else None

        # 정책명 + 적합도로 expander 제목 생성
        policy_name = policy_data.get("policy_name", f"정책 {idx+1}")
        eligibility_icon = "✅" if (match_info and match_info.get("is_eligible")) else "⚠️"

        with st.expander(
            f"{eligibility_icon} {policy_name}",
            expanded=(idx == 0),  # 첫 번째 정책만 펼침
        ):
            render_policy_card(policy_data, match_info)
