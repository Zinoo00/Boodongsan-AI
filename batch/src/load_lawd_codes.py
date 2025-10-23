"""
법정동 코드를 OpenSearch에 로드하는 스크립트
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.lawd_service import LawdService
from src.utils.logger import get_logger

logger = get_logger(__name__)

def main():
    """법정동 코드 로드 메인 함수"""
    try:
        logger.info("법정동 코드 로드 시작")
        
        # LawdService 인스턴스 생성
        lawd_service = LawdService()
        
        # 법정동 코드를 OpenSearch에 로드
        success = lawd_service.load_lawd_codes_to_opensearch()
        
        if success:
            logger.info("법정동 코드 로드 완료")
            
            # 인덱스 통계 조회
            stats = lawd_service.get_index_stats()
            if 'error' not in stats:
                logger.info(f"인덱스 통계: 문서 수 {stats['document_count']}, 크기 {stats['size']} bytes")
            else:
                logger.error(f"통계 조회 실패: {stats['error']}")
        else:
            logger.error("법정동 코드 로드 실패")
            return 1
            
    except Exception as e:
        logger.error(f"법정동 코드 로드 중 오류 발생: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
