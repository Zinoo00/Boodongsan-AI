"""
관리자 API 라우터 - 데이터 로딩 및 시스템 관리.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from celery.result import AsyncResult
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.dependencies import get_lightrag_service
from data.collectors.sigungu_service import SigunguServiceSingleton
from jobs.celery_app import celery_app
from jobs.tasks import load_data_task, test_task

if TYPE_CHECKING:
    from services.lightrag_service import LightRAGService

router = APIRouter()


class DataLoadRequest(BaseModel):
    """데이터 로딩 요청."""

    mode: str = Field("sample", description="로딩 모드: 'sample' 또는 'full'")
    districts: list[str] | None = Field(None, description="수집할 자치구 리스트")
    year_month: str | None = Field(None, description="수집 기준 연월 (YYYYMM)")
    property_types: list[str] | None = Field(None, description="수집할 부동산 유형")
    max_records: int | None = Field(None, description="최대 수집 레코드 수")


class DataLoadResponse(BaseModel):
    """데이터 로딩 응답."""

    status: str
    message: str
    started_at: str
    stats: dict[str, Any] | None = None


class DataStatsResponse(BaseModel):
    """데이터 통계 응답."""

    lightrag_workspace: str
    working_directory: str
    sigungu_count: int
    available_districts: list[str]


# In-memory task tracking (간단한 구현)
_data_load_status: dict[str, Any] = {
    "is_loading": False,
    "last_load_time": None,
    "last_stats": None,
}


@router.post("/load-data", response_model=DataLoadResponse)
async def load_data(
    request: DataLoadRequest,
    background_tasks: BackgroundTasks,
    lightrag_service: LightRAGService = Depends(get_lightrag_service),
) -> DataLoadResponse:
    """
    국토교통부 및 서울시 공공 데이터를 LightRAG에 로딩합니다.

    배경 작업으로 실행되므로 즉시 응답을 반환합니다.
    /admin/status 엔드포인트로 진행 상황을 확인할 수 있습니다.
    """
    if _data_load_status["is_loading"]:
        raise HTTPException(
            status_code=409,
            detail="데이터 로딩이 이미 진행 중입니다. 완료될 때까지 기다려주세요.",
        )

    async def _load_in_background():
        """백그라운드 데이터 로딩 태스크."""
        from scripts.load_data import load_full_data, load_sample_data

        _data_load_status["is_loading"] = True
        _data_load_status["last_load_time"] = datetime.now().isoformat()

        try:
            if request.mode == "sample":
                stats = await load_sample_data(lightrag_service)
            else:
                stats = await load_full_data(
                    lightrag_service,
                    districts=request.districts,
                    year_month=request.year_month,
                )

            _data_load_status["last_stats"] = stats
        except Exception:
            _data_load_status["last_stats"] = {"error": "데이터 로딩 실패"}
        finally:
            _data_load_status["is_loading"] = False

    background_tasks.add_task(_load_in_background)

    return DataLoadResponse(
        status="started",
        message=f"데이터 로딩 시작됨 (모드: {request.mode})",
        started_at=datetime.now().isoformat(),
    )


@router.get("/status", response_model=dict[str, Any])
async def get_load_status() -> dict[str, Any]:
    """
    데이터 로딩 진행 상황을 확인합니다.
    """
    return {
        "is_loading": _data_load_status["is_loading"],
        "last_load_time": _data_load_status["last_load_time"],
        "last_stats": _data_load_status["last_stats"],
    }


@router.get("/stats", response_model=DataStatsResponse)
async def get_data_stats(
    lightrag_service: LightRAGService = Depends(get_lightrag_service),
) -> DataStatsResponse:
    """
    현재 데이터 소스 및 LightRAG 상태를 확인합니다.
    """
    from core.config import settings

    sigungu_list = list(SigunguServiceSingleton.all_sigungu())

    return DataStatsResponse(
        lightrag_workspace=settings.LIGHTRAG_WORKSPACE,
        working_directory=settings.LIGHTRAG_WORKING_DIR,
        sigungu_count=len(sigungu_list),
        available_districts=[info.sigungu_name for info in sigungu_list[:20]],  # 샘플
    )


@router.get("/districts")
async def get_available_districts() -> dict[str, Any]:
    """
    수집 가능한 모든 자치구 목록을 반환합니다.
    """
    districts = []
    for info in SigunguServiceSingleton.all_sigungu():
        districts.append(
            {
                "sigungu_name": info.sigungu_name,
                "sigungu_code": info.sigungu_code,
                "sido_name": info.sido_name,
                "sido_fullname": info.sido_fullname,
            }
        )

    return {
        "total_count": len(districts),
        "districts": districts,
    }


@router.delete("/clear-data")
async def clear_lightrag_data(
    lightrag_service: LightRAGService = Depends(get_lightrag_service),
    confirm: bool = Query(False, description="삭제 확인"),
) -> dict[str, Any]:
    """
    LightRAG 데이터를 완전히 삭제합니다.

    ⚠️ 주의: 이 작업은 되돌릴 수 없습니다!
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="데이터 삭제를 확인하려면 ?confirm=true 파라미터를 추가하세요.",
        )

    try:
        # LightRAG 종료
        await lightrag_service.finalize()

        # 작업 디렉토리 삭제 (주의!)
        import shutil
        from pathlib import Path

        from core.config import settings

        working_dir = Path(settings.LIGHTRAG_WORKING_DIR) / settings.LIGHTRAG_WORKSPACE
        if working_dir.exists():
            shutil.rmtree(working_dir)

        # 재초기화
        await lightrag_service.initialize()

        return {
            "status": "success",
            "message": "LightRAG 데이터가 완전히 삭제되었습니다.",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"데이터 삭제 중 오류 발생: {e}",
        ) from e


# ============================================================================
# Background Job Management (Celery)
# ============================================================================


class JobStartRequest(BaseModel):
    """백그라운드 작업 시작 요청."""

    mode: str = Field("sample", description="로딩 모드: 'sample' 또는 'full'")
    districts: list[str] | None = Field(None, description="수집할 자치구 리스트")
    year_month: str | None = Field(None, description="수집 기준 연월 (YYYYMM)")
    property_types: list[str] | None = Field(None, description="수집할 부동산 유형")
    max_records: int | None = Field(None, description="최대 수집 레코드 수")


class JobStatusResponse(BaseModel):
    """작업 상태 응답."""

    job_id: str
    state: str
    status: str | None = None
    current: int | None = None
    total: int | None = None
    rate_per_minute: float | None = None
    errors: int | None = None
    elapsed_seconds: int | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


@router.post("/jobs/load-data", response_model=dict[str, Any])
async def start_data_loading_job(request: JobStartRequest) -> dict[str, Any]:
    """
    백그라운드 데이터 로딩 작업 시작 (Celery).

    장점:
    - 재개 가능: 중단되어도 체크포인트에서 재시작
    - 진행 상황 추적: /jobs/{job_id} 엔드포인트로 실시간 확인
    - 안정성: 컨테이너 재시작 시에도 작업 유지

    Returns:
        작업 ID 및 시작 상태
    """
    # Celery task 시작
    task = load_data_task.delay(
        mode=request.mode,
        districts=request.districts,
        year_month=request.year_month,
        property_types=request.property_types,
        max_records=request.max_records,
    )

    return {
        "job_id": task.id,
        "status": "started",
        "message": f"데이터 로딩 작업이 시작되었습니다 (모드: {request.mode})",
        "check_progress": f"/api/v1/admin/jobs/{task.id}",
    }


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """
    백그라운드 작업 상태 조회.

    작업 상태:
    - PENDING: 대기 중
    - PROGRESS: 진행 중 (진행률 포함)
    - SUCCESS: 완료
    - FAILURE: 실패
    """
    task = AsyncResult(job_id, app=celery_app)

    if task.state == "PENDING":
        return JobStatusResponse(
            job_id=job_id,
            state=task.state,
            status="작업 대기 중...",
        )

    elif task.state == "PROGRESS":
        info = task.info or {}
        return JobStatusResponse(
            job_id=job_id,
            state=task.state,
            status="진행 중",
            current=info.get("current"),
            total=info.get("total"),
            rate_per_minute=info.get("rate_per_minute"),
            errors=info.get("errors"),
            elapsed_seconds=info.get("elapsed_seconds"),
        )

    elif task.state == "SUCCESS":
        return JobStatusResponse(
            job_id=job_id,
            state=task.state,
            status="완료",
            result=task.result,
        )

    else:  # FAILURE or other states
        return JobStatusResponse(
            job_id=job_id,
            state=task.state,
            status="실패",
            error=str(task.info) if task.info else None,
        )


@router.delete("/jobs/{job_id}")
async def cancel_job(job_id: str) -> dict[str, Any]:
    """
    실행 중인 작업 취소.

    주의: 이미 시작된 작업은 즉시 중단되지 않을 수 있습니다.
    """
    task = AsyncResult(job_id, app=celery_app)

    if task.state in ["PENDING", "PROGRESS"]:
        task.revoke(terminate=True)
        return {
            "job_id": job_id,
            "status": "cancelled",
            "message": "작업 취소 요청이 전송되었습니다.",
        }
    else:
        return {
            "job_id": job_id,
            "status": "cannot_cancel",
            "message": f"작업 상태가 '{task.state}'이므로 취소할 수 없습니다.",
        }


@router.get("/jobs")
async def list_jobs() -> dict[str, Any]:
    """
    현재 실행 중인 모든 작업 목록 조회.

    Note: Celery는 기본적으로 완료된 작업을 자동으로 추적하지 않습니다.
    실행 중인 작업만 확인할 수 있습니다.
    """
    # Celery inspect API 사용
    inspect = celery_app.control.inspect()

    active_tasks = inspect.active() or {}
    scheduled_tasks = inspect.scheduled() or {}
    reserved_tasks = inspect.reserved() or {}

    return {
        "active": active_tasks,
        "scheduled": scheduled_tasks,
        "reserved": reserved_tasks,
    }


@router.post("/jobs/test")
async def start_test_job(duration: int = 10) -> dict[str, Any]:
    """
    테스트용 작업 시작 (진행 상황 업데이트 데모).

    Args:
        duration: 실행 시간 (초)

    Returns:
        작업 ID
    """
    task = test_task.delay(duration=duration)

    return {
        "job_id": task.id,
        "status": "started",
        "message": f"테스트 작업 시작 (실행 시간: {duration}초)",
        "check_progress": f"/api/v1/admin/jobs/{task.id}",
    }
