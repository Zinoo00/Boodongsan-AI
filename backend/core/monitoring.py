"""
CloudWatch monitoring integration for AWS deployment.
AWS 배포를 위한 CloudWatch 모니터링 통합
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class CloudWatchMetrics:
    """
    AWS CloudWatch 메트릭 전송 서비스.

    커스텀 메트릭을 CloudWatch에 전송하여 모니터링 및 알람 설정 가능.
    """

    def __init__(self, namespace: str = "BODA/DataCollection", region: str = "ap-northeast-2"):
        """
        Args:
            namespace: CloudWatch 네임스페이스
            region: AWS 리전
        """
        self.namespace = namespace
        self.region = region
        self._cloudwatch_client = None
        self._enabled = False

        try:
            import boto3

            self._cloudwatch_client = boto3.client("cloudwatch", region_name=region)
            self._enabled = True
            logger.info(f"CloudWatch metrics enabled (namespace: {namespace})")
        except ImportError:
            logger.warning(
                "boto3 not installed. CloudWatch metrics disabled. "
                "Install with: pip install boto3"
            )
        except Exception as e:
            logger.warning(f"Failed to initialize CloudWatch client: {e}")

    def put_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = "Count",
        dimensions: dict[str, str] | None = None,
    ) -> bool:
        """
        CloudWatch에 메트릭 전송.

        Args:
            metric_name: 메트릭 이름
            value: 메트릭 값
            unit: 메트릭 단위 (Count, Seconds, Percent, etc.)
            dimensions: 메트릭 차원 (선택)

        Returns:
            성공 여부
        """
        if not self._enabled:
            return False

        try:
            metric_data = {
                "MetricName": metric_name,
                "Value": value,
                "Unit": unit,
                "Timestamp": datetime.utcnow(),
            }

            if dimensions:
                metric_data["Dimensions"] = [
                    {"Name": key, "Value": val} for key, val in dimensions.items()
                ]

            self._cloudwatch_client.put_metric_data(
                Namespace=self.namespace,
                MetricData=[metric_data],
            )

            return True

        except Exception as e:
            logger.error(f"Failed to send metric to CloudWatch: {e}")
            return False

    def track_documents_processed(self, count: int, job_id: str | None = None) -> bool:
        """
        처리된 문서 수 추적.

        Args:
            count: 처리된 문서 수
            job_id: 작업 ID (선택)

        Returns:
            성공 여부
        """
        dimensions = {"JobId": job_id} if job_id else None
        return self.put_metric("DocumentsProcessed", count, "Count", dimensions)

    def track_processing_rate(self, docs_per_minute: float, job_id: str | None = None) -> bool:
        """
        처리 속도 추적 (분당 문서 수).

        Args:
            docs_per_minute: 분당 처리 문서 수
            job_id: 작업 ID (선택)

        Returns:
            성공 여부
        """
        dimensions = {"JobId": job_id} if job_id else None
        return self.put_metric("ProcessingRate", docs_per_minute, "Count/Minute", dimensions)

    def track_errors(self, error_count: int, job_id: str | None = None) -> bool:
        """
        에러 발생 추적.

        Args:
            error_count: 에러 수
            job_id: 작업 ID (선택)

        Returns:
            성공 여부
        """
        dimensions = {"JobId": job_id} if job_id else None
        return self.put_metric("Errors", error_count, "Count", dimensions)

    def track_job_duration(self, duration_seconds: float, job_id: str | None = None) -> bool:
        """
        작업 실행 시간 추적.

        Args:
            duration_seconds: 실행 시간 (초)
            job_id: 작업 ID (선택)

        Returns:
            성공 여부
        """
        dimensions = {"JobId": job_id} if job_id else None
        return self.put_metric("JobDuration", duration_seconds, "Seconds", dimensions)

    def track_api_response_time(self, response_time_ms: float, endpoint: str | None = None) -> bool:
        """
        API 응답 시간 추적.

        Args:
            response_time_ms: 응답 시간 (밀리초)
            endpoint: API 엔드포인트 (선택)

        Returns:
            성공 여부
        """
        dimensions = {"Endpoint": endpoint} if endpoint else None
        return self.put_metric("APIResponseTime", response_time_ms, "Milliseconds", dimensions)

    def track_memory_usage(self, memory_mb: float) -> bool:
        """
        메모리 사용량 추적.

        Args:
            memory_mb: 메모리 사용량 (MB)

        Returns:
            성공 여부
        """
        return self.put_metric("MemoryUsage", memory_mb, "Megabytes")

    def track_cpu_usage(self, cpu_percent: float) -> bool:
        """
        CPU 사용률 추적.

        Args:
            cpu_percent: CPU 사용률 (%)

        Returns:
            성공 여부
        """
        return self.put_metric("CPUUsage", cpu_percent, "Percent")


class MetricsAggregator:
    """
    메트릭 집계 및 배치 전송 서비스.

    여러 메트릭을 모아서 한 번에 전송하여 API 호출 비용 절감.
    """

    def __init__(
        self,
        cloudwatch: CloudWatchMetrics,
        batch_size: int = 20,
        flush_interval_seconds: int = 60,
    ):
        """
        Args:
            cloudwatch: CloudWatch 메트릭 서비스
            batch_size: 배치 크기 (최대 20)
            flush_interval_seconds: 자동 플러시 간격 (초)
        """
        self.cloudwatch = cloudwatch
        self.batch_size = min(batch_size, 20)  # CloudWatch limit
        self.flush_interval = flush_interval_seconds
        self._metrics_buffer: list[dict[str, Any]] = []
        self._last_flush = datetime.utcnow()

    def add_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = "Count",
        dimensions: dict[str, str] | None = None,
    ) -> None:
        """
        메트릭을 버퍼에 추가.

        Args:
            metric_name: 메트릭 이름
            value: 메트릭 값
            unit: 메트릭 단위
            dimensions: 메트릭 차원
        """
        metric = {
            "MetricName": metric_name,
            "Value": value,
            "Unit": unit,
            "Timestamp": datetime.utcnow(),
        }

        if dimensions:
            metric["Dimensions"] = [{"Name": key, "Value": val} for key, val in dimensions.items()]

        self._metrics_buffer.append(metric)

        # 자동 플러시 (배치 크기 또는 시간 간격 도달 시)
        should_flush = (
            len(self._metrics_buffer) >= self.batch_size
            or (datetime.utcnow() - self._last_flush).seconds >= self.flush_interval
        )
        if should_flush:
            self.flush()

    def flush(self) -> bool:
        """
        버퍼의 모든 메트릭을 CloudWatch로 전송.

        Returns:
            성공 여부
        """
        if not self._metrics_buffer:
            return True

        if not self.cloudwatch._enabled:
            self._metrics_buffer.clear()
            return False

        try:
            self.cloudwatch._cloudwatch_client.put_metric_data(
                Namespace=self.cloudwatch.namespace,
                MetricData=self._metrics_buffer,
            )

            logger.info(f"Flushed {len(self._metrics_buffer)} metrics to CloudWatch")
            self._metrics_buffer.clear()
            self._last_flush = datetime.utcnow()

            return True

        except Exception as e:
            logger.error(f"Failed to flush metrics to CloudWatch: {e}")
            return False
