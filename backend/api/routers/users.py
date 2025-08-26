"""
사용자 API 라우터 (스텁)
사용자 프로필 관리 엔드포인트
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.user_profiling_service import UserProfilingService

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic 모델들
class UserProfileResponse(BaseModel):
    """사용자 프로필 응답 모델"""

    user_profile: dict[str, Any] = Field(..., description="사용자 프로필")


class UserAnalysisResponse(BaseModel):
    """사용자 분석 응답 모델"""

    analysis: dict[str, Any] = Field(..., description="사용자 분석 결과")


@router.get("/{user_id}/profile", response_model=UserProfileResponse)
async def get_user_profile(user_id: str):
    """사용자 프로필 조회"""
    try:
        profiling_service = UserProfilingService()
        profile = await profiling_service.get_user_profile(user_id)

        if not profile:
            raise HTTPException(status_code=404, detail="사용자 프로필을 찾을 수 없습니다.")

        return UserProfileResponse(user_profile=profile)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"사용자 프로필 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="사용자 프로필 조회 중 오류가 발생했습니다.")


@router.get("/{user_id}/analysis", response_model=UserAnalysisResponse)
async def get_user_analysis(user_id: str):
    """사용자 대화 패턴 분석"""
    try:
        profiling_service = UserProfilingService()
        analysis = await profiling_service.analyze_conversation_patterns(user_id)

        return UserAnalysisResponse(analysis=analysis)

    except Exception as e:
        logger.error(f"사용자 분석 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="사용자 분석 중 오류가 발생했습니다.")


@router.get("/{user_id}/suggestions")
async def get_missing_info_suggestions(user_id: str):
    """부족한 정보 제안"""
    try:
        profiling_service = UserProfilingService()
        suggestions = await profiling_service.suggest_missing_info(user_id)

        return {"suggestions": suggestions, "user_id": user_id}

    except Exception as e:
        logger.error(f"정보 제안 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="정보 제안 중 오류가 발생했습니다.")
