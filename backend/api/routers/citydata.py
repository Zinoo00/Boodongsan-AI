"""
서울 열린데이터 광장의 실시간 도시 데이터 API(OA-21285) 라우터.
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query, Request, status

from core.exceptions import ErrorCode, ExternalServiceError, ValidationError
from services.seoul_city_data_service import SeoulCityDataService

router = APIRouter()


async def _get_citydata_service(request: Request) -> SeoulCityDataService:
    service = getattr(request.app.state, "citydata_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": "서울시 실시간 데이터 서비스가 초기화되지 않았습니다."},
        )
    return service


async def _execute_snapshot(
    request: Request,
    executor: Callable[[SeoulCityDataService], Any],
) -> dict[str, Any]:
    service = await _get_citydata_service(request)

    try:
        return await executor(service)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=exc.to_dict()) from exc
    except ExternalServiceError as exc:
        status_code = status.HTTP_502_BAD_GATEWAY
        if exc.error_code == ErrorCode.EXTERNAL_API_RATE_LIMIT:
            status_code = status.HTTP_429_TOO_MANY_REQUESTS
        elif exc.error_code == ErrorCode.EXTERNAL_API_TIMEOUT:
            status_code = status.HTTP_504_GATEWAY_TIMEOUT
        raise HTTPException(status_code, detail=exc.to_dict()) from exc


@router.get(
    "",
    summary="서울시 실시간 도시 데이터 조회",
    response_description="정규화된 도시 데이터 스냅샷",
)
async def get_city_snapshot(
    request: Request,
    location: str | None = Query(
        default=None,
        description="장소명 (예: 광화문·덕수궁). Provide either location or area_code.",
    ),
    area_code: str | None = Query(
        default=None,
        description="서울시 실시간 도시데이터 장소 코드 (예: POI009). Provide either location or area_code.",
    ),
    start: int = Query(
        default=1,
        ge=1,
        le=1000,
        description="API start row (default 1).",
    ),
    end: int = Query(
        default=5,
        ge=1,
        le=1000,
        description="API end row (inclusive, default 5).",
    ),
) -> dict[str, Any]:
    """서울 실시간 도시 데이터 전체 스냅샷을 조회한다."""

    return await _execute_snapshot(
        request,
        lambda svc: svc.get_city_snapshot(
            location_name=location,
            area_code=area_code,
            start_row=start,
            end_row=end,
        ),
    )


@router.get(
    "/population",
    summary="서울시 실시간 인구 데이터 조회",
    response_description="OA-21778 기반 인구 중심 스냅샷",
)
async def get_population_snapshot(
    request: Request,
    location: str | None = Query(
        default=None,
        description="장소명 (예: 광화문·덕수궁). Provide either location or area_code.",
    ),
    area_code: str | None = Query(
        default=None,
        description="서울시 실시간 인구데이터 장소 코드 (예: POI009). Provide either location or area_code.",
    ),
    start: int = Query(default=1, ge=1, le=1000, description="API start row (default 1)."),
    end: int = Query(default=5, ge=1, le=1000, description="API end row (inclusive, default 5)."),
) -> dict[str, Any]:
    """서울 실시간 인구 전용 데이터(OA-21778)를 조회한다."""

    return await _execute_snapshot(
        request,
        lambda svc: svc.get_population_snapshot(
            location_name=location,
            area_code=area_code,
            start_row=start,
            end_row=end,
        ),
    )


@router.get(
    "/commercial",
    summary="서울시 실시간 상권 데이터 조회",
    response_description="OA-22385 기반 상권 중심 스냅샷",
)
async def get_commercial_snapshot(
    request: Request,
    location: str | None = Query(
        default=None,
        description="장소명 (예: 광화문·덕수궁). Provide either location or area_code.",
    ),
    area_code: str | None = Query(
        default=None,
        description="서울시 실시간 상권현황 장소 코드 (예: POI009). Provide either location or area_code.",
    ),
    start: int = Query(default=1, ge=1, le=1000, description="API start row (default 1)."),
    end: int = Query(default=5, ge=1, le=1000, description="API end row (inclusive, default 5)."),
) -> dict[str, Any]:
    """서울 실시간 상권 전용 데이터(OA-22385)를 조회한다."""

    return await _execute_snapshot(
        request,
        lambda svc: svc.get_commercial_snapshot(
            location_name=location,
            area_code=area_code,
            start_row=start,
            end_row=end,
        ),
    )
