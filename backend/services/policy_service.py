"""
정부 지원 정책 매칭 서비스
사용자 프로필과 정부 정책 조건을 매칭하여 적용 가능한 정책 찾기
"""

import logging
from typing import Any

from sqlalchemy import and_, or_

from ..database.connection import get_db_session
from ..database.models import GovernmentPolicy, PolicyCondition

logger = logging.getLogger(__name__)


class PolicyService:
    """정부 지원 정책 서비스"""

    def __init__(self):
        pass

    async def find_applicable_policies(
        self, user_profile: dict[str, Any]
    ) -> list[GovernmentPolicy]:
        """사용자 프로필에 적용 가능한 정책 찾기"""
        try:
            async with get_db_session() as db:
                # 활성 정책만 조회
                base_query = db.query(GovernmentPolicy).filter(GovernmentPolicy.is_active == True)

                # 기본 필터링 조건들
                filters = []

                # 나이 조건 필터링
                if user_profile.get("age"):
                    age = user_profile["age"]
                    age_filter = and_(
                        or_(GovernmentPolicy.age_min.is_(None), GovernmentPolicy.age_min <= age),
                        or_(GovernmentPolicy.age_max.is_(None), GovernmentPolicy.age_max >= age),
                    )
                    filters.append(age_filter)

                # 소득 조건 필터링
                if user_profile.get("annual_income"):
                    income = user_profile["annual_income"]
                    income_filter = and_(
                        or_(
                            GovernmentPolicy.income_min.is_(None),
                            GovernmentPolicy.income_min <= income,
                        ),
                        or_(
                            GovernmentPolicy.income_max.is_(None),
                            GovernmentPolicy.income_max >= income,
                        ),
                    )
                    filters.append(income_filter)

                # 지역 조건 필터링
                if user_profile.get("region_preference"):
                    region = user_profile["region_preference"]
                    region_filter = or_(
                        GovernmentPolicy.available_regions.is_(None),
                        GovernmentPolicy.available_regions.contains([region]),
                        # 부분 일치도 허용
                        GovernmentPolicy.available_regions.any(region),
                    )
                    filters.append(region_filter)

                # 필터 적용
                if filters:
                    policies = base_query.filter(and_(*filters)).all()
                else:
                    policies = base_query.all()

                # 추가 조건 검사
                applicable_policies = []
                for policy in policies:
                    if await self._check_detailed_conditions(policy, user_profile):
                        applicable_policies.append(policy)

                # 정책 유형별 우선순위로 정렬
                applicable_policies.sort(key=lambda p: self._get_policy_priority(p, user_profile))

                logger.info(f"적용 가능한 정책 {len(applicable_policies)}개 발견")
                return applicable_policies

        except Exception as e:
            logger.error(f"적용 가능한 정책 검색 실패: {str(e)}")
            return []

    async def _check_detailed_conditions(
        self, policy: GovernmentPolicy, user_profile: dict[str, Any]
    ) -> bool:
        """정책별 세부 조건 검사"""
        try:
            # 특별 조건 검사
            if policy.first_time_buyer_only and not user_profile.get("is_first_time_buyer", True):
                return False

            if policy.newlywed_priority and not user_profile.get("is_newlywed", False):
                # 신혼부부 우대 정책이지만 필수는 아닌 경우 통과
                pass

            if policy.multi_child_benefit and not user_profile.get("has_multiple_children", False):
                # 다자녀 혜택이지만 필수는 아닌 경우 통과
                pass

            # 자산 한도 검사 (향후 구현)
            if policy.asset_limit and user_profile.get("total_assets"):
                if user_profile["total_assets"] > policy.asset_limit:
                    return False

            return True

        except Exception as e:
            logger.error(f"세부 조건 검사 실패: {str(e)}")
            return False

    def _get_policy_priority(self, policy: GovernmentPolicy, user_profile: dict[str, Any]) -> int:
        """정책 우선순위 계산 (낮을수록 높은 우선순위)"""
        priority_score = 0

        # 정책 유형별 기본 우선순위
        type_priorities = {"전세자금": 1, "구입자금": 2, "임대주택": 3, "청약": 4, "보증보험": 5}
        priority_score += type_priorities.get(policy.policy_type, 10)

        # 사용자 특성과 매칭되는 정책 우선순위 상승
        if policy.newlywed_priority and user_profile.get("is_newlywed"):
            priority_score -= 5

        if policy.multi_child_benefit and user_profile.get("has_multiple_children"):
            priority_score -= 3

        if policy.first_time_buyer_only and user_profile.get("is_first_time_buyer"):
            priority_score -= 2

        # 대출 한도가 높은 정책 우선순위
        if policy.loan_limit:
            # 대출 한도를 억 단위로 변환해서 우선순위에 반영
            loan_priority = -(policy.loan_limit // 100000000)  # 음수로 해서 높은 한도가 우선
            priority_score += loan_priority

        # 낮은 금리 정책 우선순위
        if policy.interest_rate:
            priority_score += int(policy.interest_rate * 2)  # 금리가 낮을수록 우선순위 높음

        return priority_score

    async def get_policy_details(self, policy_id: str) -> dict[str, Any] | None:
        """정책 상세 정보 조회"""
        try:
            async with get_db_session() as db:
                policy = db.query(GovernmentPolicy).filter(GovernmentPolicy.id == policy_id).first()

                if not policy:
                    return None

                # 세부 조건 조회
                conditions = (
                    db.query(PolicyCondition).filter(PolicyCondition.policy_id == policy_id).all()
                )

                policy_dict = {
                    "id": str(policy.id),
                    "policy_name": policy.policy_name,
                    "policy_type": policy.policy_type,
                    "policy_category": policy.policy_category,
                    "description": policy.description,
                    # 자격 조건
                    "eligibility": {
                        "age_min": policy.age_min,
                        "age_max": policy.age_max,
                        "income_min": policy.income_min,
                        "income_max": policy.income_max,
                        "asset_limit": policy.asset_limit,
                        "first_time_buyer_only": policy.first_time_buyer_only,
                        "newlywed_priority": policy.newlywed_priority,
                        "multi_child_benefit": policy.multi_child_benefit,
                    },
                    # 혜택 내용
                    "benefits": {
                        "loan_limit": policy.loan_limit,
                        "interest_rate": float(policy.interest_rate)
                        if policy.interest_rate
                        else None,
                        "loan_period_max": policy.loan_period_max,
                    },
                    # 지역 제한
                    "regions": {
                        "available_regions": policy.available_regions or [],
                        "excluded_regions": policy.excluded_regions or [],
                    },
                    # 신청 정보
                    "application": {
                        "application_url": policy.application_url,
                        "required_documents": policy.required_documents or [],
                        "contact_info": policy.contact_info,
                    },
                    # 기간 정보
                    "period": {
                        "start_date": policy.start_date.isoformat() if policy.start_date else None,
                        "end_date": policy.end_date.isoformat() if policy.end_date else None,
                        "is_active": policy.is_active,
                    },
                    # 세부 조건
                    "detailed_conditions": [
                        {
                            "type": condition.condition_type,
                            "key": condition.condition_key,
                            "value": condition.condition_value,
                            "operator": condition.condition_operator,
                            "description": condition.description,
                            "is_required": condition.is_required,
                        }
                        for condition in conditions
                    ],
                }

                return policy_dict

        except Exception as e:
            logger.error(f"정책 상세 정보 조회 실패: {str(e)}")
            return None

    async def calculate_policy_benefit(
        self, policy_id: str, user_profile: dict[str, Any]
    ) -> dict[str, Any]:
        """사용자 기준 정책 혜택 계산"""
        try:
            policy_details = await self.get_policy_details(policy_id)
            if not policy_details:
                return {"error": "정책을 찾을 수 없습니다."}

            benefits = policy_details["benefits"]
            user_budget = user_profile.get("budget_max", 0)

            # 대출 가능 금액 계산
            loan_limit = benefits.get("loan_limit", 0)
            available_loan = min(loan_limit, user_budget) if user_budget > 0 else loan_limit

            # 월 상환액 계산 (원리금균등상환 방식)
            interest_rate = benefits.get("interest_rate", 0)
            loan_period = benefits.get("loan_period_max", 30)

            monthly_payment = 0
            if available_loan > 0 and interest_rate > 0:
                monthly_rate = (interest_rate / 100) / 12
                total_months = loan_period * 12

                # 원리금균등상환 공식
                monthly_payment = (
                    available_loan
                    * (monthly_rate * (1 + monthly_rate) ** total_months)
                    / ((1 + monthly_rate) ** total_months - 1)
                )

            # 시중 금리와 비교
            market_rate = 5.5  # 시중 평균 대출 금리 (예시)
            market_monthly_payment = 0

            if available_loan > 0:
                market_monthly_rate = (market_rate / 100) / 12
                total_months = loan_period * 12

                market_monthly_payment = (
                    available_loan
                    * (market_monthly_rate * (1 + market_monthly_rate) ** total_months)
                    / ((1 + market_monthly_rate) ** total_months - 1)
                )

            # 절약 금액 계산
            monthly_savings = market_monthly_payment - monthly_payment
            total_savings = monthly_savings * loan_period * 12

            calculation = {
                "policy_name": policy_details["policy_name"],
                "loan_amount": available_loan,
                "interest_rate": interest_rate,
                "loan_period_years": loan_period,
                "monthly_payment": round(monthly_payment),
                "market_comparison": {
                    "market_rate": market_rate,
                    "market_monthly_payment": round(market_monthly_payment),
                    "monthly_savings": round(monthly_savings),
                    "total_savings": round(total_savings),
                },
                "eligibility_check": await self._check_eligibility(policy_details, user_profile),
            }

            return calculation

        except Exception as e:
            logger.error(f"정책 혜택 계산 실패: {str(e)}")
            return {"error": "혜택 계산 중 오류가 발생했습니다."}

    async def _check_eligibility(
        self, policy_details: dict[str, Any], user_profile: dict[str, Any]
    ) -> dict[str, Any]:
        """자격 조건 체크"""
        try:
            eligibility = policy_details["eligibility"]
            results = {
                "is_eligible": True,
                "passed_conditions": [],
                "failed_conditions": [],
                "missing_info": [],
            }

            # 나이 조건 체크
            user_age = user_profile.get("age")
            if user_age:
                age_min = eligibility.get("age_min")
                age_max = eligibility.get("age_max")

                if age_min and user_age < age_min:
                    results["failed_conditions"].append(
                        f"최소 나이 {age_min}세 이상 필요 (현재: {user_age}세)"
                    )
                    results["is_eligible"] = False
                elif age_max and user_age > age_max:
                    results["failed_conditions"].append(
                        f"최대 나이 {age_max}세 이하 필요 (현재: {user_age}세)"
                    )
                    results["is_eligible"] = False
                else:
                    results["passed_conditions"].append("나이 조건 충족")
            else:
                results["missing_info"].append("나이 정보 필요")

            # 소득 조건 체크
            user_income = user_profile.get("annual_income")
            if user_income:
                income_min = eligibility.get("income_min")
                income_max = eligibility.get("income_max")

                if income_min and user_income < income_min:
                    results["failed_conditions"].append(f"최소 연소득 {income_min:,}원 이상 필요")
                    results["is_eligible"] = False
                elif income_max and user_income > income_max:
                    results["failed_conditions"].append(f"최대 연소득 {income_max:,}원 이하 필요")
                    results["is_eligible"] = False
                else:
                    results["passed_conditions"].append("소득 조건 충족")
            else:
                results["missing_info"].append("연소득 정보 필요")

            # 특별 조건 체크
            if eligibility.get("first_time_buyer_only"):
                if user_profile.get("is_first_time_buyer"):
                    results["passed_conditions"].append("생애최초 구입자 조건 충족")
                else:
                    results["failed_conditions"].append("생애최초 구입자만 신청 가능")
                    results["is_eligible"] = False

            if eligibility.get("newlywed_priority"):
                if user_profile.get("is_newlywed"):
                    results["passed_conditions"].append("신혼부부 우대 조건 충족")
                # 우대 조건이므로 필수는 아님

            if eligibility.get("multi_child_benefit"):
                if user_profile.get("has_multiple_children"):
                    results["passed_conditions"].append("다자녀 혜택 조건 충족")
                # 혜택 조건이므로 필수는 아님

            return results

        except Exception as e:
            logger.error(f"자격 조건 체크 실패: {str(e)}")
            return {"is_eligible": False, "error": "자격 조건 확인 중 오류가 발생했습니다."}

    async def search_policies_by_keyword(
        self, keyword: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """키워드로 정책 검색"""
        try:
            async with get_db_session() as db:
                policies = (
                    db.query(GovernmentPolicy)
                    .filter(
                        and_(
                            GovernmentPolicy.is_active == True,
                            or_(
                                GovernmentPolicy.policy_name.contains(keyword),
                                GovernmentPolicy.description.contains(keyword),
                                GovernmentPolicy.policy_type.contains(keyword),
                                GovernmentPolicy.policy_category.contains(keyword),
                            ),
                        )
                    )
                    .limit(limit)
                    .all()
                )

                results = []
                for policy in policies:
                    results.append(
                        {
                            "id": str(policy.id),
                            "policy_name": policy.policy_name,
                            "policy_type": policy.policy_type,
                            "policy_category": policy.policy_category,
                            "description": policy.description,
                            "loan_limit": policy.loan_limit,
                            "interest_rate": float(policy.interest_rate)
                            if policy.interest_rate
                            else None,
                        }
                    )

                return results

        except Exception as e:
            logger.error(f"키워드 정책 검색 실패: {str(e)}")
            return []

    async def get_popular_policies(self, limit: int = 5) -> list[dict[str, Any]]:
        """인기 정책 조회 (예시 구현)"""
        try:
            # 실제로는 신청 통계, 조회수 등을 기반으로 인기도 계산
            popular_policy_names = [
                "청년전세임대주택",
                "디딤돌 대출",
                "생애최초 특별공급",
                "LH청약플러스",
                "신혼부부 특별공급",
            ]

            async with get_db_session() as db:
                policies = (
                    db.query(GovernmentPolicy)
                    .filter(
                        and_(
                            GovernmentPolicy.is_active == True,
                            GovernmentPolicy.policy_name.in_(popular_policy_names),
                        )
                    )
                    .limit(limit)
                    .all()
                )

                results = []
                for policy in policies:
                    results.append(
                        {
                            "id": str(policy.id),
                            "policy_name": policy.policy_name,
                            "policy_type": policy.policy_type,
                            "description": policy.description,
                            "loan_limit": policy.loan_limit,
                            "interest_rate": float(policy.interest_rate)
                            if policy.interest_rate
                            else None,
                            "eligibility_summary": self._get_eligibility_summary(policy),
                        }
                    )

                return results

        except Exception as e:
            logger.error(f"인기 정책 조회 실패: {str(e)}")
            return []

    def _get_eligibility_summary(self, policy: GovernmentPolicy) -> str:
        """자격 조건 요약"""
        conditions = []

        if policy.age_min or policy.age_max:
            age_range = f"{policy.age_min or '제한없음'}~{policy.age_max or '제한없음'}세"
            conditions.append(f"나이: {age_range}")

        if policy.income_max:
            conditions.append(f"연소득: {policy.income_max:,}원 이하")

        if policy.first_time_buyer_only:
            conditions.append("생애최초 구입자")

        if policy.newlywed_priority:
            conditions.append("신혼부부 우대")

        return " | ".join(conditions) if conditions else "조건 없음"
