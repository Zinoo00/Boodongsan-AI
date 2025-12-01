"""
Celery tasks for background job processing.
백그라운드 작업 처리를 위한 Celery 태스크

설계 목표:
- EC2에서 장시간(수십 시간) 독립 실행 가능
- 노트북 연결 불필요
- 체크포인트 기반 재개 지원
- Redis 기반 분산 체크포인트 (EC2 인스턴스 간 공유)
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

from celery import Task

from core.config import settings
from data.collectors.real_estate_collector import RealEstateCollector
from data.collectors.sigungu_service import SigunguServiceSingleton
from jobs.celery_app import celery_app
from services.ai_service import AIService
from services.lightrag_service import LightRAGService

logger = logging.getLogger(__name__)


# Redis 기반 체크포인트 서비스 (분산 환경 지원)
class RedisCheckpointService:
    """
    Redis 기반 체크포인트 서비스.

    분산 환경 (다중 EC2 인스턴스)에서도 체크포인트를 공유하여
    작업 재개가 가능하도록 함.
    """

    def __init__(self) -> None:
        import redis

        self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        self._prefix = "checkpoint:"

    def save_checkpoint(self, job_id: str, data: dict[str, Any]) -> bool:
        """체크포인트 저장."""
        import json

        try:
            key = f"{self._prefix}{job_id}"
            data["checkpoint_timestamp"] = datetime.utcnow().isoformat()
            self._redis.set(key, json.dumps(data), ex=86400 * 7)  # 7일 TTL
            logger.info(f"Checkpoint saved to Redis: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            return False

    def load_checkpoint(self, job_id: str) -> dict[str, Any] | None:
        """체크포인트 로드."""
        import json

        try:
            key = f"{self._prefix}{job_id}"
            data = self._redis.get(key)
            if data:
                logger.info(f"Checkpoint loaded from Redis: {job_id}")
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None

    def clear_checkpoint(self, job_id: str) -> bool:
        """체크포인트 삭제."""
        try:
            key = f"{self._prefix}{job_id}"
            self._redis.delete(key)
            logger.info(f"Checkpoint cleared: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear checkpoint: {e}")
            return False

    def cleanup_old_checkpoints(self, max_age_hours: int = 168) -> int:
        """오래된 체크포인트 정리."""
        # Redis TTL이 자동으로 처리하므로 여기서는 패스
        return 0


class CallbackTask(Task):
    """
    Base task with callback support and error handling.
    콜백 지원 및 에러 처리를 포함한 기본 태스크
    """

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Task 실패 시 호출"""
        logger.error(f"Task {task_id} failed: {exc}")
        # 체크포인트 유지 (재시작 가능하도록)

    def on_success(self, retval, task_id, args, kwargs):
        """Task 성공 시 호출"""
        logger.info(f"Task {task_id} completed successfully")
        # 체크포인트 삭제
        checkpoint_service = RedisCheckpointService()
        checkpoint_service.clear_checkpoint(task_id)


def format_property_document(property_record: dict[str, Any]) -> str:
    """
    부동산 거래 기록을 LightRAG가 이해할 수 있는 자연어 문서로 변환.
    """
    parts = []

    # 기본 정보
    property_type = property_record.get("property_type", "부동산")
    transaction_type = property_record.get("transaction_type", "거래")
    building_name = property_record.get("building_name", "")

    header = f"{property_type} {transaction_type} 정보"
    if building_name:
        header += f" - {building_name}"
    parts.append(header)

    # 위치 정보
    sido = property_record.get("sido")
    sigungu = property_record.get("sigungu")
    dong = property_record.get("dong")

    location_parts = []
    if sido:
        location_parts.append(sido)
    if sigungu:
        location_parts.append(sigungu)
    if dong:
        location_parts.append(dong)

    if location_parts:
        parts.append(f"위치: {' '.join(location_parts)}")

    # 가격 정보
    price = property_record.get("price")
    deposit = property_record.get("deposit")
    monthly_rent = property_record.get("monthly_rent")

    if transaction_type == "매매" and price:
        parts.append(f"매매가: {price:,}원")
    elif transaction_type == "전세" and deposit:
        parts.append(f"전세 보증금: {deposit:,}원")
    elif transaction_type == "월세":
        if deposit:
            parts.append(f"보증금: {deposit:,}원")
        if monthly_rent:
            parts.append(f"월세: {monthly_rent:,}원")

    # 면적 정보
    area_m2 = property_record.get("area_m2")
    area_pyeong = property_record.get("area_pyeong")
    if area_m2:
        pyeong_str = f" ({area_pyeong:.1f}평)" if area_pyeong else ""
        parts.append(f"전용면적: {area_m2:.2f}㎡{pyeong_str}")

    # 거래 날짜
    transaction_date = property_record.get("transaction_date")
    if transaction_date:
        try:
            dt = datetime.fromisoformat(transaction_date.replace("Z", "+00:00"))
            parts.append(f"거래일자: {dt.strftime('%Y년 %m월 %d일')}")
        except (ValueError, AttributeError):
            parts.append(f"거래일자: {transaction_date}")

    return "\n".join(parts)


def format_district_document(sigungu_info: Any) -> str:
    """시군구 행정구역 정보를 자연어 문서로 변환"""
    parts = [
        f"행정구역 정보: {sigungu_info.sigungu_name}",
        f"소속: {sigungu_info.sido_fullname}",
        f"행정구역 코드: {sigungu_info.sigungu_code}",
        f"{sigungu_info.sigungu_name}은(는) {sigungu_info.sido_fullname}에 속한 자치구입니다.",
    ]
    return "\n".join(parts)


def get_event_loop() -> asyncio.AbstractEventLoop:
    """
    이벤트 루프 가져오기 또는 생성.

    Celery worker에서는 기존 루프가 없을 수 있으므로 새로 생성.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


@celery_app.task(
    bind=True,
    base=CallbackTask,
    name="jobs.tasks.load_data_task",
    # EC2 장시간 실행을 위한 설정
    soft_time_limit=86400,  # 24시간 soft limit
    time_limit=86400 + 3600,  # 25시간 hard limit
    acks_late=True,  # 작업 완료 후 ack (실패 시 재시도 가능)
    reject_on_worker_lost=True,  # Worker 종료 시 다른 worker로 재할당
)
def load_data_task(
    self,
    mode: str = "sample",
    districts: list[str] | None = None,
    year_month: str | None = None,
    property_types: list[str] | None = None,
    max_records: int | None = None,
) -> dict[str, Any]:
    """
    데이터 로딩 백그라운드 작업 (재개 가능).

    EC2에서 장시간 실행을 위해 설계:
    - Redis 기반 체크포인트로 분산 환경 지원
    - 작업 실패 시 자동 재시도
    - 진행 상황 실시간 추적 (Flower UI)

    Args:
        mode: 로딩 모드 ('sample' 또는 'full')
        districts: 수집할 자치구 리스트
        year_month: 수집 기준 연월 (YYYYMM)
        property_types: 수집할 부동산 유형
        max_records: 최대 수집 레코드 수

    Returns:
        작업 결과 딕셔너리
    """

    async def _run_data_loading():
        nonlocal districts, property_types, max_records
        task_id = self.request.id
        checkpoint_service = RedisCheckpointService()

        # 체크포인트 로드 (이전 실행이 있으면 재개)
        checkpoint = checkpoint_service.load_checkpoint(task_id)
        start_count = 0
        processed_ids = set()
        districts_complete = False

        if checkpoint:
            start_count = checkpoint.get("documents_loaded", 0)
            processed_ids = set(checkpoint.get("processed_ids", []))
            districts_complete = checkpoint.get("districts_complete", False)
            logger.info(f"Resuming from checkpoint: {start_count} documents already processed")

        # 서비스 초기화
        logger.info("Initializing services...")
        ai_service = AIService()
        await ai_service.initialize()

        lightrag_service = LightRAGService(ai_service=ai_service)
        await lightrag_service.initialize()

        start_time = time.time()
        total_loaded = start_count
        errors = 0

        try:
            # Phase 1: 행정구역 데이터 (체크포인트에서 완료되지 않았으면)
            if not districts_complete:
                logger.info("Loading district data...")
                district_count = 0

                for sigungu_info in SigunguServiceSingleton.all_sigungu():
                    doc_id = f"district_{sigungu_info.sigungu_code}"

                    if doc_id in processed_ids:
                        continue

                    document = format_district_document(sigungu_info)
                    success = await lightrag_service.insert(document)

                    if success:
                        district_count += 1
                        processed_ids.add(doc_id)

                    if district_count % 10 == 0:
                        await asyncio.sleep(0.1)

                logger.info(f"District data loaded: {district_count} districts")

                # 체크포인트 저장
                checkpoint_service.save_checkpoint(
                    task_id,
                    {
                        "districts_complete": True,
                        "districts_loaded": district_count,
                        "documents_loaded": total_loaded,
                        "processed_ids": list(processed_ids),
                    },
                )

            # Phase 2: 실거래가 데이터
            logger.info("Loading real estate data...")

            # 샘플 모드 설정
            if mode == "sample":
                if districts is None:
                    districts = ["강남구", "서초구", "송파구"]
                if property_types is None:
                    property_types = ["apartment_rent"]
                if max_records is None:
                    max_records = 500

            logger.info(f"  - Mode: {mode}")
            logger.info(f"  - Districts: {districts if districts is not None else '전체'}")
            logger.info(
                f"  - Property types: {property_types if property_types is not None else '전체'}"
            )
            logger.info(
                f"  - Max records: {max_records if max_records is not None else '무제한'}"
            )

            collector = RealEstateCollector()
            property_count = 0

            try:
                async for property_record in collector.collect_all_data(
                    year_month=year_month,
                    districts=districts,
                    property_types=property_types,
                ):
                    # 고유 ID 생성
                    doc_id = (
                        f"property_{property_record.get('transaction_date', '')}_"
                        f"{property_record.get('address', '')}"
                    )

                    # 이미 처리된 문서 스킵
                    if doc_id in processed_ids:
                        continue

                    document = format_property_document(property_record)
                    success = await lightrag_service.insert(document)

                    if success:
                        property_count += 1
                        total_loaded += 1
                        processed_ids.add(doc_id)
                    else:
                        errors += 1

                    # 진행 상황 업데이트 (매 10개마다)
                    if property_count % 10 == 0:
                        elapsed = time.time() - start_time
                        rate = property_count / elapsed * 60 if elapsed > 0 else 0

                        # Celery task state 업데이트 (Flower UI에서 확인 가능)
                        self.update_state(
                            state="PROGRESS",
                            meta={
                                "current": total_loaded,
                                "total": max_records or 1000,
                                "rate_per_minute": round(rate, 1),
                                "errors": errors,
                                "elapsed_seconds": int(elapsed),
                                "status": f"Processing... {total_loaded} documents",
                            },
                        )

                        logger.info(
                            f"Progress: {property_count} documents | "
                            f"Rate: {rate:.1f} docs/min | "
                            f"Errors: {errors}"
                        )

                    # 체크포인트 저장 (매 50개마다)
                    if property_count % 50 == 0:
                        checkpoint_service.save_checkpoint(
                            task_id,
                            {
                                "districts_complete": True,
                                "documents_loaded": total_loaded,
                                "processed_ids": list(processed_ids),
                                "errors": errors,
                            },
                        )

                    # Rate limiting
                    if property_count % 50 == 0:
                        await asyncio.sleep(0.5)

                    # 최대 레코드 수 확인
                    if max_records and property_count >= max_records:
                        logger.info(f"Reached max records limit: {max_records}")
                        break

            finally:
                await collector.close()

            # 완료
            elapsed = time.time() - start_time
            logger.info(f"Data loading completed: {total_loaded} documents in {elapsed:.1f}s")

            return {
                "status": "success",
                "documents_loaded": total_loaded,
                "errors": errors,
                "elapsed_seconds": int(elapsed),
                "mode": mode,
            }

        except Exception as e:
            logger.error(f"Data loading failed: {e}", exc_info=True)

            # 체크포인트 저장 (재시도 가능하도록)
            checkpoint_service.save_checkpoint(
                task_id,
                {
                    "districts_complete": districts_complete,
                    "documents_loaded": total_loaded,
                    "processed_ids": list(processed_ids),
                    "errors": errors + 1,
                    "last_error": str(e),
                },
            )

            raise

        finally:
            await lightrag_service.finalize()
            await ai_service.close()

    # asyncio 이벤트 루프에서 실행
    loop = get_event_loop()
    return loop.run_until_complete(_run_data_loading())


@celery_app.task(name="jobs.tasks.cleanup_old_jobs")
def cleanup_old_jobs() -> dict[str, Any]:
    """
    오래된 작업 체크포인트 정리 (정기 작업).

    Returns:
        정리 결과
    """
    logger.info("Cleaning up old job checkpoints...")

    checkpoint_service = RedisCheckpointService()
    deleted_count = checkpoint_service.cleanup_old_checkpoints(max_age_hours=168)  # 7 days

    return {
        "status": "success",
        "deleted_checkpoints": deleted_count,
        "timestamp": datetime.utcnow().isoformat(),
    }


@celery_app.task(bind=True, name="jobs.tasks.test_task")
def test_task(self, duration: int = 10) -> dict[str, Any]:
    """
    테스트용 태스크 (진행 상황 업데이트 데모).

    Args:
        duration: 실행 시간 (초)

    Returns:
        테스트 결과
    """
    logger.info(f"Starting test task (duration: {duration}s)")

    for i in range(duration):
        time.sleep(1)

        # 진행 상황 업데이트
        self.update_state(
            state="PROGRESS",
            meta={
                "current": i + 1,
                "total": duration,
                "status": f"Processing step {i + 1}/{duration}",
            },
        )

        logger.info(f"Test task progress: {i + 1}/{duration}")

    return {
        "status": "success",
        "duration": duration,
        "timestamp": datetime.utcnow().isoformat(),
    }


@celery_app.task(bind=True, name="jobs.tasks.health_check")
def health_check(self) -> dict[str, Any]:
    """
    Worker health check task.

    Flower UI나 모니터링 시스템에서 worker 상태를 확인하는데 사용.
    """
    import socket

    return {
        "status": "healthy",
        "hostname": socket.gethostname(),
        "timestamp": datetime.utcnow().isoformat(),
        "task_id": self.request.id,
    }
