"""
정부 정책 API 라우터
정부 지원 정책 조회 및 매칭 엔드포인트
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ...services.policy_service import PolicyService

logger = logging.getLogger(__name__)

router = APIRouter()

# Pydantic 모델들
class PolicySearchRequest(BaseModel):
    """정책 검색 요청 모델"""
    user_profile: dict[str, Any] = Field(..., description="사용자 프로필 정보")

class PolicyListResponse(BaseModel):
    """정책 목록 응답 모델"""
    policies: list[dict[str, Any]] = Field(..., description="정책 목록")
    total_count: int = Field(..., description="전체 정책 수")
    filters_applied: dict[str, Any] = Field(..., description="적용된 필터")

class PolicyDetailResponse(BaseModel):
    """정책 상세 응답 모델"""
    policy: dict[str, Any] = Field(..., description="정책 상세 정보")

class PolicyBenefitResponse(BaseModel):
    """정책 혜택 계산 응답 모델"""
    benefit_calculation: dict[str, Any] = Field(..., description="혜택 계산 결과")

@router.post("/search", response_model=PolicyListResponse)
async def search_applicable_policies(request: PolicySearchRequest):
    """사용자 프로필 기반 적용 가능한 정책 검색"""
    try:
        policy_service = PolicyService()
        
        # 적용 가능한 정책 검색
        policies = await policy_service.find_applicable_policies(request.user_profile)
        
        # 정책 정보 포맷팅
        formatted_policies = []
        for policy in policies:
            formatted_policies.append({
                "id": str(policy.id),
                "policy_name": policy.policy_name,
                "policy_type": policy.policy_type,
                "policy_category": policy.policy_category,
                "description": policy.description,
                "loan_limit": policy.loan_limit,
                "interest_rate": float(policy.interest_rate) if policy.interest_rate else None,
                "loan_period_max": policy.loan_period_max,
                "eligibility_summary": {
                    "age_range": f"{policy.age_min or '제한없음'}~{policy.age_max or '제한없음'}세" if policy.age_min or policy.age_max else None,
                    "income_limit": policy.income_max,
                    "special_conditions": {
                        "first_time_buyer_only": policy.first_time_buyer_only,
                        "newlywed_priority": policy.newlywed_priority,
                        "multi_child_benefit": policy.multi_child_benefit
                    }
                },
                "application_info": {
                    "application_url": policy.application_url,
                    "contact_info": policy.contact_info
                }
            })
        
        return PolicyListResponse(
            policies=formatted_policies,
            total_count=len(formatted_policies),
            filters_applied={
                "user_age": request.user_profile.get("age"),
                "user_income": request.user_profile.get("annual_income"),
                "user_region": request.user_profile.get("region_preference")
            }
        )
        
    except Exception as e:
        logger.error(f"정책 검색 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="정책 검색 중 오류가 발생했습니다."
        )

@router.get("/", response_model=PolicyListResponse)
async def list_policies(
    policy_type: str | None = Query(None, description="정책 유형 필터"),
    policy_category: str | None = Query(None, description="정책 카테고리 필터"),
    active_only: bool = Query(True, description="활성 정책만 조회"),
    limit: int = Query(20, description="조회 개수", le=100),
    offset: int = Query(0, description="오프셋")
):
    """정책 목록 조회"""
    try:
        policy_service = PolicyService()
        
        # 검색 조건에 따라 정책 조회
        # (실제로는 PolicyService에 list_policies 메소드를 추가해야 함)
        
        # 임시로 인기 정책 반환
        if not policy_type and not policy_category:
            policies_data = await policy_service.get_popular_policies(limit)
        else:
            # 키워드 검색 활용
            search_keyword = policy_type or policy_category or ""
            policies_data = await policy_service.search_policies_by_keyword(search_keyword, limit)
        
        return PolicyListResponse(
            policies=policies_data,
            total_count=len(policies_data),
            filters_applied={
                "policy_type": policy_type,
                "policy_category": policy_category,
                "active_only": active_only,
                "limit": limit,
                "offset": offset
            }
        )
        
    except Exception as e:
        logger.error(f"정책 목록 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="정책 목록 조회 중 오류가 발생했습니다."
        )

@router.get("/{policy_id}", response_model=PolicyDetailResponse)
async def get_policy_detail(policy_id: str):
    """정책 상세 정보 조회"""
    try:
        policy_service = PolicyService()
        policy_detail = await policy_service.get_policy_details(policy_id)
        
        if not policy_detail:
            raise HTTPException(
                status_code=404,
                detail="해당 정책을 찾을 수 없습니다."
            )
        
        return PolicyDetailResponse(policy=policy_detail)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"정책 상세 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="정책 상세 정보 조회 중 오류가 발생했습니다."
        )

@router.post("/{policy_id}/calculate-benefit", response_model=PolicyBenefitResponse)
async def calculate_policy_benefit(
    policy_id: str,
    user_profile: dict[str, Any]
):
    """사용자 기준 정책 혜택 계산"""
    try:
        policy_service = PolicyService()
        benefit_calculation = await policy_service.calculate_policy_benefit(
            policy_id, user_profile
        )
        
        if "error" in benefit_calculation:
            raise HTTPException(
                status_code=400,
                detail=benefit_calculation["error"]
            )
        
        return PolicyBenefitResponse(benefit_calculation=benefit_calculation)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"정책 혜택 계산 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="정책 혜택 계산 중 오류가 발생했습니다."
        )

@router.get("/search/keyword", response_model=PolicyListResponse)
async def search_policies_by_keyword(
    keyword: str = Query(..., description="검색 키워드"),
    limit: int = Query(10, description="조회 개수", le=50)
):
    """키워드 기반 정책 검색"""
    try:
        policy_service = PolicyService()
        policies_data = await policy_service.search_policies_by_keyword(keyword, limit)
        
        return PolicyListResponse(
            policies=policies_data,
            total_count=len(policies_data),
            filters_applied={
                "keyword": keyword,
                "limit": limit
            }
        )
        
    except Exception as e:
        logger.error(f"키워드 정책 검색 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="키워드 정책 검색 중 오류가 발생했습니다."
        )

@router.get("/popular/list", response_model=PolicyListResponse)
async def get_popular_policies(
    limit: int = Query(5, description="조회 개수", le=20)
):
    """인기 정책 목록 조회"""
    try:
        policy_service = PolicyService()
        policies_data = await policy_service.get_popular_policies(limit)
        
        return PolicyListResponse(
            policies=policies_data,
            total_count=len(policies_data),
            filters_applied={
                "type": "popular",
                "limit": limit
            }
        )
        
    except Exception as e:
        logger.error(f"인기 정책 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="인기 정책 조회 중 오류가 발생했습니다."
        )

@router.get("/types/list")
async def get_policy_types():
    """정책 유형 목록 조회"""
    try:
        # 정적 정책 유형 목록 반환
        policy_types = [
            {
                "type": "전세자금",
                "description": "전세 보증금 대출 지원",
                "count": 3
            },
            {
                "type": "구입자금", 
                "description": "주택 구입 자금 대출 지원",
                "count": 2
            },
            {
                "type": "임대주택",
                "description": "공공 임대주택 공급",
                "count": 1
            },
            {
                "type": "특별공급",
                "description": "계층별 주택 특별공급",
                "count": 3
            },
            {
                "type": "청약",
                "description": "주택 청약 관련 지원",
                "count": 2
            },
            {
                "type": "보증보험",
                "description": "전세 보증금 보험",
                "count": 1
            }
        ]
        
        return {
            "policy_types": policy_types,
            "total_types": len(policy_types)
        }
        
    except Exception as e:
        logger.error(f"정책 유형 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="정책 유형 조회 중 오류가 발생했습니다."
        )

@router.get("/categories/list")
async def get_policy_categories():
    """정책 카테고리 목록 조회"""
    try:
        # 정적 정책 카테고리 목록 반환
        policy_categories = [
            {
                "category": "청년",
                "description": "만 39세 이하 청년층 대상",
                "count": 2
            },
            {
                "category": "신혼부부",
                "description": "혼인 7년 이내 신혼부부 대상", 
                "count": 1
            },
            {
                "category": "다자녀",
                "description": "미성년 자녀 3명 이상 가구 대상",
                "count": 1
            },
            {
                "category": "생애최초",
                "description": "생애최초 주택 구입자 대상",
                "count": 1
            },
            {
                "category": "일반",
                "description": "일반 계층 대상",
                "count": 7
            }
        ]
        
        return {
            "policy_categories": policy_categories,
            "total_categories": len(policy_categories)
        }
        
    except Exception as e:
        logger.error(f"정책 카테고리 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="정책 카테고리 조회 중 오류가 발생했습니다."
        )