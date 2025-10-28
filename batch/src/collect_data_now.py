"""
즉시 데이터 수집 스크립트 (collect_data_now.py)
현재 시점의 부동산 데이터를 즉시 수집합니다.
"""

import argparse
import sys
import os
import pandas as pd
from typing import List

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.settings import Config
from src.config.constants import DATA_TYPES
from src.services.data_service import DataService
from src.services.vector_service import VectorService
from src.services.s3_service import S3Service
from src.utils.helpers import get_lawd_codes, get_recent_months
from src.utils.logger import setup_logger
from src.collectors.apartment_collector import ApartmentDataCollector
from src.collectors.rh_collector import RHDataCollector
from src.collectors.offi_collector import OffiDataCollector

def main():
    """즉시 데이터 수집 메인 함수"""
    parser = argparse.ArgumentParser(description='즉시 부동산 데이터 수집')
    
    # 데이터 수집 옵션
    parser.add_argument('--data_type', type=str, default='all',
                       choices=['all'] + list(DATA_TYPES.keys()),
                       help='수집할 데이터 타입')
    parser.add_argument('--regions', nargs='+', default=get_lawd_codes(),
                       help='법정동코드 리스트')
    parser.add_argument('--recent', action='store_true', 
                       help='최근 데이터만 수집')
    
    args = parser.parse_args()
    
    # 로거 설정
    logger = setup_logger('collect_now', 'logs/collect.log')
    
    try:
        # 서비스 초기화
        data_service = DataService()
        vector_service = VectorService()
        
        # S3 서비스 초기화 (설정에 따라)
        config = Config()
        s3_service = None
        if config.ENABLE_S3_STORAGE:
            s3_service = S3Service(
                bucket_name=config.S3_BUCKET_NAME,
                region_name=config.S3_REGION_NAME
            )
            # S3 버킷 존재 확인 및 생성
            if not s3_service.check_bucket_exists():
                logger.info("S3 버킷이 존재하지 않습니다. 버킷을 생성합니다...")
                if s3_service.create_bucket_if_not_exists():
                    logger.info("S3 버킷 생성 완료")
                else:
                    logger.warning("S3 버킷 생성 실패. S3 저장을 건너뜁니다.")
                    s3_service = None
        
        # 수집기 초기화
        collectors = {
            'apt': ApartmentDataCollector(),
            'rh': RHDataCollector(),
            'offi': OffiDataCollector()
        }
        
        # 데이터 타입 결정
        if args.data_type == 'all':
            data_types = list(DATA_TYPES.keys())
        else:
            data_types = [args.data_type]
        
        # 거래년월 결정
        if args.recent:
            deal_ymds = get_recent_months(1)
        else:
            deal_ymds = get_recent_months(1)  # 즉시 수집은 최근 1개월만
        
        logger.info(f"즉시 데이터 수집 시작: {data_types}, 지역: {args.regions}, 기간: {deal_ymds}")
        
        # 데이터 수집
        all_results = {}
        
        for data_type in data_types:
            logger.info(f"{data_type} 데이터 수집 중...")
            
            # 수집기 선택
            if data_type.startswith('apt'):
                collector = collectors['apt']
                if data_type == 'apt_rent':
                    collect_method = collector.collect_apt_rent_data
                else:
                    collect_method = collector.collect_apt_trade_data
            elif data_type.startswith('rh'):
                collector = collectors['rh']
                if data_type == 'rh_rent':
                    collect_method = collector.collect_rh_rent_data
                else:
                    collect_method = collector.collect_rh_trade_data
            elif data_type.startswith('offi'):
                collector = collectors['offi']
                if data_type == 'offi_rent':
                    collect_method = collector.collect_offi_rent_data
                else:
                    collect_method = collector.collect_offi_trade_data
            
            # 데이터 수집 실행
            for lawd_cd in args.regions:
                for deal_ymd in deal_ymds:
                    try:
                        result = collect_method(lawd_cd, deal_ymd)
                        if result and 'clean_data' in result and result['clean_data'] is not None:
                            if data_type not in all_results:
                                all_results[data_type] = {'clean_data': None, 'raw_data': []}
                            
                            # 데이터 병합
                            if all_results[data_type]['clean_data'] is None:
                                all_results[data_type]['clean_data'] = result['clean_data']
                            else:
                                all_results[data_type]['clean_data'] = pd.concat([
                                    all_results[data_type]['clean_data'],
                                    result['clean_data']
                                ], ignore_index=True)
                            
                            all_results[data_type]['raw_data'].extend(result.get('raw_data', []))
                            
                    except Exception as e:
                        logger.error(f"{data_type} 데이터 수집 실패 ({lawd_cd}, {deal_ymd}): {e}")
        
        # 결과 처리
        processed_results = data_service.process_collection_results(all_results)
        
        # 벡터 데이터베이스 저장
        if processed_results:
            logger.info("벡터 데이터베이스에 저장 중...")
            success = vector_service.save_to_vector_db(processed_results, args.regions, deal_ymds[0])
            
            if success:
                logger.info("벡터 데이터베이스 저장 완료")
                
                # S3에 CSV 형태로 저장
                if s3_service:
                    logger.info("S3에 CSV 형태로 저장 중...")
                    s3_keys = s3_service.save_collection_results_to_s3(processed_results, args.regions, deal_ymds[0])
                    if s3_keys:
                        logger.info(f"S3 저장 완료: {len(s3_keys)}개 파일")
                        for key_type, s3_key in s3_keys.items():
                            logger.info(f"  - {key_type}: s3://{config.S3_BUCKET_NAME}/{s3_key}")
                    else:
                        logger.warning("S3 저장 실패")
                else:
                    logger.info("S3 저장이 비활성화되어 있습니다.")
            else:
                logger.error("벡터 데이터베이스 저장 실패")
        
        logger.info("즉시 데이터 수집 완료")
        
    except Exception as e:
        logger.error(f"즉시 수집 중 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
