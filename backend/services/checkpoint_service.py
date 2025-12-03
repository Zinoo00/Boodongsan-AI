"""
Checkpoint service for resumable long-running jobs.
재개 가능한 장기 실행 작업을 위한 체크포인트 서비스
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CheckpointService:
    """
    체크포인트 저장 및 로드 서비스.

    장기 실행 작업의 진행 상황을 저장하여, 중단 시 재개할 수 있도록 합니다.
    """

    def __init__(self, checkpoint_dir: str = "./checkpoints") -> None:
        """
        Args:
            checkpoint_dir: 체크포인트 파일을 저장할 디렉토리
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Checkpoint directory: {self.checkpoint_dir.absolute()}")

    def save_checkpoint(self, job_id: str, data: dict[str, Any]) -> bool:
        """
        작업 체크포인트 저장.

        Args:
            job_id: 작업 ID
            data: 저장할 체크포인트 데이터

        Returns:
            성공 여부
        """
        try:
            checkpoint_file = self.checkpoint_dir / f"{job_id}.json"

            # 타임스탬프 추가
            checkpoint_data = {
                **data,
                "checkpoint_timestamp": datetime.utcnow().isoformat(),
            }

            with open(checkpoint_file, "w") as f:
                json.dump(checkpoint_data, f, indent=2)

            logger.info(f"Checkpoint saved for job {job_id}: {checkpoint_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save checkpoint for job {job_id}: {e}")
            return False

    def load_checkpoint(self, job_id: str) -> dict[str, Any] | None:
        """
        작업 체크포인트 로드.

        Args:
            job_id: 작업 ID

        Returns:
            체크포인트 데이터 또는 None
        """
        try:
            checkpoint_file = self.checkpoint_dir / f"{job_id}.json"

            if not checkpoint_file.exists():
                logger.info(f"No checkpoint found for job {job_id}")
                return None

            with open(checkpoint_file) as f:
                data = json.load(f)

            logger.info(f"Checkpoint loaded for job {job_id}")
            return data

        except Exception as e:
            logger.error(f"Failed to load checkpoint for job {job_id}: {e}")
            return None

    def clear_checkpoint(self, job_id: str) -> bool:
        """
        완료된 작업의 체크포인트 삭제.

        Args:
            job_id: 작업 ID

        Returns:
            성공 여부
        """
        try:
            checkpoint_file = self.checkpoint_dir / f"{job_id}.json"

            if checkpoint_file.exists():
                checkpoint_file.unlink()
                logger.info(f"Checkpoint cleared for job {job_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to clear checkpoint for job {job_id}: {e}")
            return False

    def list_checkpoints(self) -> list[dict[str, Any]]:
        """
        모든 체크포인트 목록 조회.

        Returns:
            체크포인트 정보 리스트
        """
        checkpoints = []

        for checkpoint_file in self.checkpoint_dir.glob("*.json"):
            try:
                with open(checkpoint_file) as f:
                    data = json.load(f)

                checkpoints.append(
                    {
                        "job_id": checkpoint_file.stem,
                        "timestamp": data.get("checkpoint_timestamp"),
                        "data": data,
                    }
                )
            except Exception as e:
                logger.error(f"Failed to read checkpoint {checkpoint_file}: {e}")

        return checkpoints

    def cleanup_old_checkpoints(self, max_age_hours: int = 168) -> int:
        """
        오래된 체크포인트 삭제 (기본: 7일).

        Args:
            max_age_hours: 최대 보관 시간 (시간)

        Returns:
            삭제된 체크포인트 수
        """
        from datetime import timedelta

        deleted_count = 0
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

        for checkpoint_file in self.checkpoint_dir.glob("*.json"):
            try:
                with open(checkpoint_file) as f:
                    data = json.load(f)

                timestamp_str = data.get("checkpoint_timestamp")
                if not timestamp_str:
                    continue

                timestamp = datetime.fromisoformat(timestamp_str)

                if timestamp < cutoff_time:
                    checkpoint_file.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted old checkpoint: {checkpoint_file}")

            except Exception as e:
                logger.error(f"Failed to process checkpoint {checkpoint_file}: {e}")

        logger.info(f"Cleaned up {deleted_count} old checkpoints")
        return deleted_count
