#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
법정동 코드 조회 및 데이터 수집 스크립트
OpenSearch의 lawd_codes 테이블에서 법정동 코드를 조회하고, 데이터 수집을 수행합니다.
"""

import logging
import argparse
import subprocess
import sys
from src.services.lawd_service import LawdService
from src.collectors.molit_policy_collector import MolitPolicyCollector
from src.utils.logger import get_logger

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_lawd_codes(level: str = "시군구") -> list:
    """법정동코드 조회 (OpenSearch에서 조회)"""
    lawd_service = LawdService()
    
    # OpenSearch에서 모든 법정동 코드 조회
    search_body = {
        "size": 1000,  # 충분한 크기로 설정
        "query": {
            "match_all": {}
        }
    }
    
    response = lawd_service.opensearch_client.client.search(
        index="lawd_codes", 
        body=search_body
    )
    
    lawd_codes = []
    for hit in response['hits']['hits']:
        source = hit['_source']
        # level_1, level_2, level_3을 조합하여 전체 이름 생성
        level_1 = source.get('level_1', '')
        level_2 = source.get('level_2', '')
        level_3 = source.get('level_3', '')
        
        # 이름 조합 (null 값 제외)
        name_parts = [part for part in [level_1, level_2, level_3] if part]
        full_name = ' '.join(name_parts) if name_parts else ''
        
        lawd_codes.append({
            'code': source.get('lawd_code', ''),
            'name': full_name,
            'level_1': level_1,
            'level_2': level_2,
            'level_3': level_3,
            'level': level
        })
    
    logger.info(f"OpenSearch에서 {len(lawd_codes)}개의 {level} 법정동코드를 조회했습니다.")
    return lawd_codes


def collect_data(data_type: str, lawd_cd: str, deal_ym: str) -> bool:
    """데이터 수집 직접 실행"""
    try:
        logger.info(f"🚀 데이터 수집 시작 - 타입: {data_type}, 지역: {lawd_cd}, 년월: {deal_ym}")
        
        # 필요한 모듈 import
        from src.services.data_service import DataService
        from src.services.vector_service import VectorService
        from src.services.s3_service import S3Service
        from src.config.settings import Config
        from src.collectors.apartment_collector import ApartmentDataCollector
        from src.collectors.rh_collector import RHDataCollector
        from src.collectors.offi_collector import OffiDataCollector
        
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
        else:
            logger.error(f"❌ 지원하지 않는 데이터 타입: {data_type}")
            return False
        
        # 데이터 수집 실행
        logger.info(f"📊 {data_type} 데이터 수집 중...")
        result = collect_method(lawd_cd, deal_ym)
        
        if result and 'clean_data' in result and result['clean_data'] is not None:
            logger.info(f"✅ 데이터 수집 완료 - {len(result['clean_data'])}개 레코드")
            
            # 결과 처리
            all_results = {data_type: result}
            processed_results = data_service.process_collection_results(all_results)
            
            # 벡터 데이터베이스 저장
            if processed_results:
                logger.info("벡터 데이터베이스에 저장 중...")
                success = vector_service.save_to_vector_db(processed_results, [lawd_cd], deal_ym)
                
                if success:
                    logger.info("벡터 데이터베이스 저장 완료")
                    
                    # S3에 CSV 형태로 저장
                    if s3_service:
                        logger.info("S3에 CSV 형태로 저장 중...")
                        s3_keys = s3_service.save_collection_results_to_s3(processed_results, [lawd_cd], deal_ym)
                        if s3_keys:
                            logger.info(f"S3 저장 완료: {len(s3_keys)}개 파일")
                            for key_type, s3_key in s3_keys.items():
                                logger.info(f"  - {key_type}: s3://{config.S3_BUCKET_NAME}/{s3_key}")
                        else:
                            logger.warning("S3 저장 실패")
                    else:
                        logger.info("S3 저장이 비활성화되어 있습니다.")
                    
                    return True
                else:
                    logger.error("벡터 데이터베이스 저장 실패")
                    return False
            else:
                logger.error("처리된 결과가 없습니다.")
                return False
        else:
            logger.warning(f"⚠️ {data_type} 데이터 수집 실패 또는 데이터 없음")
            return False
            
    except Exception as e:
        logger.error(f"❌ 데이터 수집 중 오류: {e}")
        return False


def get_lawd_codes_for_weekday(weekday: int) -> list:
    """요일별로 법정동 코드를 분할하여 반환"""
    try:
        # 모든 법정동 코드 조회
        all_lawd_codes = get_lawd_codes("시군구")
        
        # 요일별로 분할 (7등분)
        codes_per_day = len(all_lawd_codes) // 7
        remainder = len(all_lawd_codes) % 7
        
        start_idx = weekday * codes_per_day + min(weekday, remainder)
        end_idx = start_idx + codes_per_day + (1 if weekday < remainder else 0)
        
        return all_lawd_codes[start_idx:end_idx]
        
    except Exception as e:
        logger.error(f"요일별 법정동 코드 조회 실패: {e}")
        return []


def get_months_for_collection() -> list:
    """수집할 월 목록 생성 (최근 5년)"""
    from datetime import datetime, timedelta
    
    months = []
    current_date = datetime.now()
    
    # 최근 5년간의 모든 월 생성
    for year_offset in range(5):
        for month in range(1, 13):
            target_date = current_date.replace(
                year=current_date.year - year_offset,
                month=month,
                day=1
            )
            months.append(target_date.strftime("%Y%m"))
    
    return months


def schedule_collect_data(weekday: int = None):
    """스케줄된 데이터 수집 실행"""
    try:
        from datetime import datetime
        from src.config.settings import Config
        
        # 요일 확인
        if weekday is None:
            weekday = datetime.now().weekday()
        
        weekday_names = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        
        print("=" * 60)
        print(f"스케줄된 데이터 수집 ({weekday_names[weekday]})")
        print("=" * 60)
        
        # S3 설정 확인
        config = Config()
        if config.ENABLE_S3_STORAGE:
            print(f"📦 S3 저장 활성화 - 버킷: {config.S3_BUCKET_NAME}, 리전: {config.S3_REGION_NAME}")
        else:
            print("📦 S3 저장 비활성화")
        
        # 요일별 법정동 코드 조회
        lawd_codes = get_lawd_codes_for_weekday(weekday)
        if not lawd_codes:
            print("❌ 법정동 코드를 조회할 수 없습니다.")
            return False
        
        # 수집할 월 목록
        months = get_months_for_collection()
        
        print(f"📊 수집 대상: {len(lawd_codes)}개 법정동, {len(months)}개월")
        print(f"📊 예상 요청 수: {len(lawd_codes)} × {len(months)} × 6개 API = {len(lawd_codes) * len(months) * 6}회")
        
        # 데이터 타입 목록
        data_types = ['apt_rent', 'apt_trade', 'rh_rent', 'rh_trade', 'offi_rent', 'offi_trade']
        
        total_success = 0
        total_attempts = 0
        
        # 각 법정동별로 수집
        for i, lawd_code in enumerate(lawd_codes, 1):
            print(f"\n🔄 [{i}/{len(lawd_codes)}] 법정동 코드: {lawd_code}")
            
            for month in months:
                print(f"  📅 {month} 수집 중...")
                
                for data_type in data_types:
                    total_attempts += 1
                    try:
                        success = collect_data(data_type, lawd_code, month)
                        if success:
                            total_success += 1
                            print(f"    ✅ {data_type} 완료")
                        else:
                            print(f"    ❌ {data_type} 실패")
                    except Exception as e:
                        print(f"    ❌ {data_type} 오류: {e}")
                        logger.error(f"데이터 수집 오류: {e}")
        
        print(f"\n📊 최종 결과: {total_success}/{total_attempts} 성공")
        
        if total_success == total_attempts:
            print("✅ 모든 데이터 수집이 완료되었습니다.")
            return True
        elif total_success > 0:
            print("⚠️ 일부 데이터 수집이 완료되었습니다.")
            return True
        else:
            print("❌ 모든 데이터 수집에 실패했습니다.")
            return False
            
    except Exception as e:
        logger.error(f"스케줄된 데이터 수집 실패: {e}")
        return False


def reload_lawd_codes():
    """lawd_codes 테이블 재수집"""
    try:
        logger.info("🔄 lawd_codes 테이블 재수집 시작")
        
        # LawdService를 사용하여 전체 재수집
        lawd_service = LawdService()
        success = lawd_service.load_lawd_codes_to_opensearch()
        
        if success:
            logger.info("✅ lawd_codes 테이블 재수집 완료")
            
            # 재수집 후 통계 조회 (인덱스 반영 대기)
            import time
            time.sleep(1)  # 1초 대기
            
            stats = lawd_service.get_index_stats()
            if 'error' in stats:
                print(f"⚠️ 통계 조회 실패: {stats['error']}")
                # 대안으로 직접 카운트 조회
                search_body = {
                    'size': 0,
                    'query': {'match_all': {}}
                }
                response = lawd_service.opensearch_client.client.search(
                    index='lawd_codes', 
                    body=search_body
                )
                count = response['hits']['total']['value']
                print(f"📊 재수집된 법정동 코드: {count}개")
            else:
                print(f"📊 재수집된 법정동 코드: {stats.get('document_count', 0)}개")
            
            return True
        else:
            logger.error("❌ lawd_codes 테이블 재수집 실패")
            return False
            
    except Exception as e:
        logger.error(f"❌ lawd_codes 테이블 재수집 중 오류: {e}")
        return False


def main():
    """메인 함수 - 법정동 코드 조회 및 데이터 수집"""
    parser = argparse.ArgumentParser(
        description='법정동 코드 조회 및 데이터 수집',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python main.py --get_lawd_codes                  # 법정동 코드 조회만
  python main.py --reload_lawd_codes               # lawd_codes 테이블 재수집
  python main.py --collect_data --data_type apt_rent --lawd_cd 41480 --deal_ym 202412  # 데이터 수집
  python main.py --collect_data --lawd_cd 41480 --deal_ym 202412  # 데이터 수집
  python main.py --collect_data --lawd_cd 41480  # 데이터 수집
  python main.py --collect_data --lawd_cd 41480 --deal_year 2025  # 2025년 1월부터 현재 월까지 수집
  python main.py --schedule_collect                # 5년간 전체 데이터 수집 (현재 요일)
  python main.py --schedule_collect --weekday 0   # 월요일 데이터 수집
  python main.py --collect_policy --policy_mode md  # 국토부 정책(주거안정) 고정 페이지 → Markdown 업로드
  python main.py --collect_policy --policy_mode pdf --policy_max 5 --policy_start_date 2025-10-01 --policy_end_date 2025-10-31  # 보도자료 PDF 수집
        """
    )
    
    parser.add_argument(
        '--data_type',
        type=str,
        help='수집할 데이터 타입 (apt_rent, apt_trade, rh_rent, rh_trade, offi_rent, offi_trade)'
    )
    
    parser.add_argument(
        '--lawd_cd',
        type=str,
        help='법정동 코드'
    )
    
    parser.add_argument(
        '--deal_ym',
        type=str,
        help='거래 년월 (YYYYMM 형식)'
    )
    
    parser.add_argument(
        '--deal_year',
        type=str,
        help='거래 연도 (YYYY 형식) - 지정 시 해당 연도 1월부터 현재 월까지 수집'
    )
    
    parser.add_argument(
        '--reload_lawd_codes',
        action='store_true',
        help='lawd_codes 테이블 재수집'
    )
    
    parser.add_argument(
        '--get_lawd_codes',
        action='store_true',
        help='법정동 코드 조회'
    )
    
    parser.add_argument(
        '--collect_data',
        action='store_true',
        help='데이터 수집 실행'
    )
    
    parser.add_argument(
        '--schedule_collect',
        action='store_true',
        help='5년간 전체 데이터 수집 스케줄 실행 (API 제한 고려)'
    )
    
    parser.add_argument(
        '--weekday',
        type=int,
        choices=range(0, 7),
        help='요일별 수집 (0=월요일, 1=화요일, ..., 6=일요일)'
    )
    
    parser.add_argument(
        '--collect_policy',
        action='store_true',
        help='국토부 정책 수집 (pdf 또는 md 모드)'
    )

    parser.add_argument(
        '--policy_mode',
        type=str,
        choices=['pdf', 'md'],
        help='정책 수집 모드: pdf(보도자료 PDF) | md(정책 고정 페이지 Markdown)'
    )
    
    parser.add_argument(
        '--policy_max',
        type=int,
        default=3,
        help='수집할 최대 정책자료 건수 (기본값: 3)'
    )
    
    parser.add_argument(
        '--policy_start_date',
        type=str,
        help='정책자료 수집 시작일 (YYYY-MM-DD 형식)'
    )
    
    parser.add_argument(
        '--policy_end_date',
        type=str,
        help='정책자료 수집 종료일 (YYYY-MM-DD 형식)'
    )
    
    args = parser.parse_args()
    
    # 법정동 코드 조회 모드인지 확인
    if args.get_lawd_codes:
        print("=" * 60)
        print("법정동 코드 조회 (OpenSearch)")
        print("=" * 60)
        
        try:
            # 법정동 코드 조회
            lawd_codes = get_lawd_codes("시군구")
            
            if lawd_codes:
                print(f"✅ {len(lawd_codes)}개의 법정동 코드를 조회했습니다:")
                for i, lawd_info in enumerate(lawd_codes[:10], 1):  # 처음 10개만 표시
                    print(f"  {i}. {lawd_info['code']} - {lawd_info['name']}")
                
                if len(lawd_codes) > 10:
                    print(f"  ... 및 {len(lawd_codes) - 10}개 더")
            else:
                print("❌ 법정동 코드가 조회되지 않았습니다.")
                return 1
            
            print("=" * 60)
            return 0
            
        except Exception as e:
            print(f"❌ 법정동 코드 조회 중 오류가 발생했습니다: {e}")
            logger.error(f"법정동 코드 조회 실패: {e}")
            return 1
    
    # 데이터 수집 모드인지 확인
    elif args.collect_data:
        print("=" * 60)
        print("데이터 수집 모드")
        print("=" * 60)
        
        # 필수 파라미터 확인
        if not args.lawd_cd:
            print("❌ 오류: 데이터 수집 모드에서는 --lawd_cd 파라미터가 필요합니다.")
            print("사용 예시:")
            print("  python main.py --collect_data --data_type apt_rent --lawd_cd 41480 --deal_ym 202412")
            print("  python main.py --collect_data --lawd_cd 41480 --deal_ym 202412")
            print("  python main.py --collect_data --lawd_cd 41480  # 이번달 자동 수집")
            print("  python main.py --collect_data --lawd_cd 41480 --deal_year 2025  # 2025년 1월부터 현재 월까지 수집")
            return 1
        
        # deal_ym과 deal_year 동시 지정 확인
        if args.deal_ym and args.deal_year:
            print("❌ 오류: --deal_ym과 --deal_year는 동시에 지정할 수 없습니다.")
            return 1
        
        # deal_year가 지정된 경우 해당 연도 1월부터 현재 월까지 수집
        if args.deal_year:
            from datetime import datetime
            try:
                year = int(args.deal_year)
                current_date = datetime.now()
                current_year = current_date.year
                current_month = current_date.month
                
                # 연도 유효성 검사
                if year < 2000 or year > current_year:
                    print(f"❌ 오류: 유효하지 않은 연도입니다. (2000년부터 {current_year}년까지 가능)")
                    return 1
                
                # 해당 연도 1월부터 현재 월까지 목록 생성
                deal_ym_list = []
                if year == current_year:
                    # 올해인 경우 1월부터 현재 월까지
                    end_month = current_month
                else:
                    # 과거 연도인 경우 12월까지
                    end_month = 12
                
                for month in range(1, end_month + 1):
                    deal_ym_list.append(f"{year}{month:02d}")
                
                print(f"📅 {args.deal_year}년 1월부터 {end_month}월까지 총 {len(deal_ym_list)}개월 수집")
            except ValueError:
                print(f"❌ 오류: 올바른 연도 형식이 아닙니다. (YYYY 형식, 예: 2025)")
                return 1
        elif args.deal_ym:
            # deal_ym이 지정된 경우 단일 월 수집
            deal_ym_list = [args.deal_ym]
        else:
            # 둘 다 없으면 현재 월로 설정
            from datetime import datetime
            current_month = datetime.now().strftime("%Y%m")
            deal_ym_list = [current_month]
            print(f"⚠️ 거래 년월이 지정되지 않았습니다. 현재 월({current_month})을 사용합니다.")
        
        # 데이터 타입이 지정되지 않은 경우 기본값 설정
        if not args.data_type:
            print("⚠️ 데이터 타입이 지정되지 않았습니다. 모든 타입을 수집합니다.")
            data_types = ['apt_rent', 'apt_trade', 'rh_rent', 'rh_trade', 'offi_rent', 'offi_trade']
        else:
            data_types = [args.data_type]
        
        print(f"수집할 데이터 타입: {', '.join(data_types)}")
        print(f"법정동 코드: {args.lawd_cd}")
        print(f"거래 년월: {', '.join(deal_ym_list)}")
        print("=" * 60)
        
        try:
            success_count = 0
            total_count = len(data_types) * len(deal_ym_list)
            
            # 각 년월별로 데이터 수집
            for deal_ym in deal_ym_list:
                print(f"\n📅 {deal_ym} 수집 시작...")
                for data_type in data_types:
                    print(f"  🔄 {data_type} 데이터 수집 시작...")
                    success = collect_data(data_type, args.lawd_cd, deal_ym)
                    
                    if success:
                        print(f"  ✅ {data_type} 데이터 수집 완료")
                        success_count += 1
                    else:
                        print(f"  ❌ {data_type} 데이터 수집 실패")
            
            print(f"\n📊 수집 결과: {success_count}/{total_count} 성공")
            
            if success_count == total_count:
                print("✅ 모든 데이터 수집이 완료되었습니다.")
                return 0
            elif success_count > 0:
                print("⚠️ 일부 데이터 수집이 완료되었습니다.")
                return 0
            else:
                print("❌ 모든 데이터 수집에 실패했습니다.")
                return 1
                
        except Exception as e:
            print(f"❌ 데이터 수집 중 오류가 발생했습니다: {e}")
            logger.error(f"데이터 수집 실패: {e}")
            return 1
    
    # 스케줄된 데이터 수집 모드인지 확인
    elif args.schedule_collect:
        print("=" * 60)
        print("5년간 전체 데이터 수집 스케줄")
        print("=" * 60)
        
        try:
            # 요일별 수집 실행
            success = schedule_collect_data(args.weekday)
            
            if success:
                print("✅ 스케줄된 데이터 수집이 완료되었습니다.")
                return 0
            else:
                print("❌ 스케줄된 데이터 수집에 실패했습니다.")
                return 1
                
        except Exception as e:
            print(f"❌ 스케줄된 데이터 수집 중 오류가 발생했습니다: {e}")
            logger.error(f"스케줄된 데이터 수집 실패: {e}")
            return 1
    
    # lawd_codes 재수집 모드인지 확인
    elif args.reload_lawd_codes:
        print("=" * 60)
        print("lawd_codes 테이블 재수집")
        print("=" * 60)
        
        try:
            success = reload_lawd_codes()
            if success:
                print("✅ lawd_codes 테이블 재수집이 완료되었습니다.")
                return 0
            else:
                print("❌ lawd_codes 테이블 재수집에 실패했습니다.")
                return 1
        except Exception as e:
            print(f"❌ lawd_codes 테이블 재수집 중 오류가 발생했습니다: {e}")
            logger.error(f"lawd_codes 재수집 실패: {e}")
            return 1
    
    # 데이터 수집 모드인지 확인
    elif args.data_type or args.lawd_cd or args.deal_ym:
        # 모든 파라미터가 있는지 확인
        if not args.data_type or not args.lawd_cd or not args.deal_ym:
            print("❌ 오류: 데이터 수집 모드에서는 --data_type, --lawd_cd, --deal_ym 파라미터가 모두 필요합니다.")
            print("사용 예시:")
            print("  python main.py --data_type apt_rent --lawd_cd 41480 --deal_ym 202412")
            return 1
        
        # 데이터 수집 실행
        print("=" * 60)
        print("데이터 수집 모드")
        print("=" * 60)
        print(f"데이터 타입: {args.data_type}")
        print(f"법정동 코드: {args.lawd_cd}")
        print(f"거래 년월: {args.deal_ym}")
        print("=" * 60)
        
        try:
            success = collect_data(args.data_type, args.lawd_cd, args.deal_ym)
            if success:
                print("✅ 데이터 수집이 완료되었습니다.")
                return 0
            else:
                print("❌ 데이터 수집에 실패했습니다.")
                return 1
        except Exception as e:
            print(f"❌ 데이터 수집 중 오류가 발생했습니다: {e}")
            logger.error(f"데이터 수집 실패: {e}")
            return 1
    
    # 국토부 정책자료 수집 모드인지 확인
    elif args.collect_policy:
        print("=" * 60)
        print("국토부 정책 수집")
        print("=" * 60)

        # 모드 필수 확인
        if not args.policy_mode:
            print("❌ 오류: --collect_policy 사용 시 --policy_mode (pdf|md)를 지정해야 합니다.")
            print("사용 예시:")
            print("  python main.py --collect_policy --policy_mode md")
            print("  python main.py --collect_policy --policy_mode pdf --policy_max 5 --policy_start_date 2025-10-01 --policy_end_date 2025-10-31")
            return 1

        try:
            collector = MolitPolicyCollector()

            if args.policy_mode == 'md':
                # 고정 정책 페이지 → Markdown 업로드
                results = collector.collect_policy_pages_to_markdown()
                if results:
                    print(f"✅ {len(results)}건의 정책 페이지를 Markdown으로 업로드했습니다:")
                    for i, result in enumerate(results, 1):
                        print(f"  {i}. {result['title']}")
                        print(f"     S3 위치: {result['s3_url']}")
                        print()
                else:
                    print("❌ 업로드된 Markdown이 없습니다.")
                    return 1
                print("=" * 60)
                return 0

            elif args.policy_mode == 'pdf':
                # PDF 수집은 파라미터 3개 모두 필수
                missing = []
                if args.policy_max is None:
                    missing.append('--policy_max')
                if not args.policy_start_date:
                    missing.append('--policy_start_date')
                if not args.policy_end_date:
                    missing.append('--policy_end_date')
                if missing:
                    print(f"❌ 오류: pdf 모드에서는 {', '.join(missing)} 파라미터가 필요합니다.")
                    print("사용 예시:")
                    print("  python main.py --collect_policy --policy_mode pdf --policy_max 5 --policy_start_date 2025-10-01 --policy_end_date 2025-10-31")
                    return 1

                results = collector.collect(
                    max_items=args.policy_max,
                    start_date=args.policy_start_date,
                    end_date=args.policy_end_date
                )

                if results:
                    print(f"✅ {len(results)}건의 정책자료 PDF를 수집했습니다:")
                    for i, result in enumerate(results, 1):
                        print(f"  {i}. {result['title']} ({result['date']})")
                        print(f"     S3 위치: {result['s3_url']}")
                        print()
                else:
                    print("❌ 조건에 맞는 정책자료 PDF를 찾을 수 없습니다.")
                    return 1
                print("=" * 60)
                return 0

        except Exception as e:
            print(f"❌ 정책자료 수집 중 오류가 발생했습니다: {e}")
            logger.error(f"정책자료 수집 실패: {e}")
            return 1
    
    else:
        # 기본 모드 - 도움말 표시
        print("=" * 60)
        print("법정동 코드 조회 및 데이터 수집 도구")
        print("=" * 60)
        print("사용 가능한 옵션:")
        print("  --get_lawd_codes                  # 법정동 코드 조회")
        print("  --reload_lawd_codes               # lawd_codes 테이블 재수집")
        print("  --collect_data --lawd_cd --deal_ym # 데이터 수집")
        print("  --schedule_collect                # 5년간 전체 데이터 수집")
        print("  --collect_policy --policy_mode md  # 국토부 정책(고정 페이지) Markdown 업로드")
        print("  --collect_policy --policy_mode pdf --policy_max --policy_start_date --policy_end_date  # 보도자료 PDF 수집")
        print("  --help                           # 도움말 표시")
        print("=" * 60)
        return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())