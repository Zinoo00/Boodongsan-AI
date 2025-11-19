"""
Celery application configuration for background job processing.
백그라운드 작업 처리를 위한 Celery 애플리케이션 설정
"""

from __future__ import annotations

import logging

from celery import Celery
from celery.signals import task_failure, task_success

from core.config import settings

logger = logging.getLogger(__name__)

# Celery app 생성
celery_app = Celery(
    "boda_jobs",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

# Import tasks explicitly to ensure they're registered
celery_app.conf.update(
    imports=["jobs.tasks"],
)

# Celery 설정
celery_app.conf.update(
    # Task 설정
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=True,

    # Result backend 설정
    result_expires=3600 * 24,  # 24 hours
    result_backend_transport_options={
        "master_name": "mymaster",
        "visibility_timeout": 3600,
    },

    # Worker 설정
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,

    # Task routing
    task_routes={
        "jobs.tasks.load_data_task": {"queue": "data_loading"},
        "jobs.tasks.cleanup_old_jobs": {"queue": "maintenance"},
    },

    # Beat 스케줄 (정기 작업)
    beat_schedule={
        "cleanup-old-jobs-daily": {
            "task": "jobs.tasks.cleanup_old_jobs",
            "schedule": 3600 * 24,  # 매일
        },
    },
)


# Task 성공 시 로깅
@task_success.connect
def task_success_handler(sender=None, result=None, **kwargs):
    """Task 성공 시 호출"""
    logger.info(f"Task {sender.name} succeeded: {result}")


# Task 실패 시 로깅
@task_failure.connect
def task_failure_handler(sender=None, exception=None, **kwargs):
    """Task 실패 시 호출"""
    logger.error(f"Task {sender.name} failed: {exception}")


# Force-import tasks module to ensure registration
try:
    import jobs.tasks  # noqa: F401
except ImportError:
    logger.warning("Failed to import jobs.tasks module")


if __name__ == "__main__":
    celery_app.start()
