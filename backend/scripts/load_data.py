"""
국토교통부 및 서울시 공공 데이터 로딩 스크립트.

이 스크립트는 다음 데이터 소스에서 데이터를 수집하고 LightRAG에 삽입합니다:
1. 국토교통부 (MOLIT) - 실거래가 데이터
2. 서울시 열린 데이터 광장 - 시군구 행정구역 정보

Usage:
    uv run python -m scripts.load_data --help
    uv run python -m scripts.load_data --mode sample
    uv run python -m scripts.load_data --mode full --districts 강남구,서초구
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

import typer

from core.config import settings
from data.collectors.pdr_collector import (
    CollectionConfig,
    PublicDataReaderCollector,
    SEOUL_DISTRICTS,
)
from data.collectors.reb_collector import (
    CollectionConfig as REBCollectionConfig,
    REBCollector,
    STATISTICS_TABLES,
    format_statistics_document,
)
from data.collectors.real_estate_collector import (
    RealEstateCollector,
    SUPPORTED_PROPERTY_TYPES,
)
from data.collectors.seoul_opendata_collector import (
    DataCategory,
    SEOUL_SERVICES,
    SeoulOpenDataCollector,
    format_document,
    format_redevelopment_document,
)
from data.collectors.sigungu_service import SigunguServiceSingleton
from services.ai_service import AIService
from services.lightrag_service import LightRAGService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = typer.Typer(help="데이터 로딩 및 관리 도구")


def format_property_document(property_record: dict[str, Any]) -> str:
    """
    부동산 거래 기록을 LightRAG가 이해할 수 있는 자연어 문서로 변환.

    LightRAG는 자연어 텍스트에서 엔티티와 관계를 추출하므로,
    구조화된 데이터를 문맥이 있는 문장으로 변환합니다.
    """
    parts = []

    # 기본 정보
    property_type = property_record.get("property_type", "부동산")
    transaction_type = property_record.get("transaction_type", "거래")
    address = property_record.get("address", "")
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
    if address:
        parts.append(f"주소: {address}")

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

    # 층수 및 건축 연도
    floor = property_record.get("floor")
    building_year = property_record.get("building_year")
    if floor:
        parts.append(f"층수: {floor}층")
    if building_year:
        parts.append(f"건축년도: {building_year}년")

    # 거래 날짜
    transaction_date = property_record.get("transaction_date")
    if transaction_date:
        try:
            dt = datetime.fromisoformat(transaction_date.replace("Z", "+00:00"))
            parts.append(f"거래일자: {dt.strftime('%Y년 %m월 %d일')}")
        except (ValueError, AttributeError):
            parts.append(f"거래일자: {transaction_date}")

    # 데이터 소스
    data_source = property_record.get("data_source")
    if data_source:
        parts.append(f"데이터 출처: {data_source}")

    return "\n".join(parts)


def format_district_document(sigungu_info: Any) -> str:
    """
    시군구 행정구역 정보를 자연어 문서로 변환.
    """
    parts = [
        f"행정구역 정보: {sigungu_info.sigungu_name}",
        f"소속: {sigungu_info.sido_fullname}",
        f"행정구역 코드: {sigungu_info.sigungu_code}",
        f"{sigungu_info.sigungu_name}은(는) {sigungu_info.sido_fullname}에 속한 자치구입니다.",
    ]
    return "\n".join(parts)


async def load_district_data(lightrag_service: LightRAGService) -> int:
    """
    시군구 행정구역 데이터를 LightRAG에 삽입.

    Returns:
        삽입된 문서 수
    """
    logger.info("시군구 행정구역 데이터 로딩 시작...")

    count = 0
    for sigungu_info in SigunguServiceSingleton.all_sigungu():
        document = format_district_document(sigungu_info)
        success = await lightrag_service.insert(document)
        if success:
            count += 1

        # Rate limiting to avoid overwhelming the system
        if count % 10 == 0:
            await asyncio.sleep(0.1)

    logger.info(f"시군구 데이터 {count}개 삽입 완료")
    return count


async def load_real_estate_data(
    lightrag_service: LightRAGService,
    districts: list[str] | None = None,
    year_month: str | None = None,
    property_types: list[str] | None = None,
    max_records: int | None = None,
) -> int:
    """
    국토교통부 실거래가 데이터를 LightRAG에 삽입.

    Args:
        lightrag_service: LightRAG 서비스 인스턴스
        districts: 수집할 자치구 리스트 (None이면 전체)
        year_month: 수집 기준 연월 (YYYYMM 형식, None이면 현재월)
        property_types: 수집할 부동산 유형 (None이면 전체)
        max_records: 최대 수집 레코드 수 (None이면 무제한)

    Returns:
        삽입된 문서 수
    """
    logger.info("국토교통부 실거래가 데이터 로딩 시작...")
    logger.info(f"  - 자치구: {districts or '전체'}")
    logger.info(f"  - 기준월: {year_month or '현재월'}")
    logger.info(f"  - 유형: {property_types or '전체'}")
    logger.info(f"  - 최대 레코드: {max_records or '무제한'}")
    logger.info("\n⚠️  LightRAG는 각 문서를 깊이 분석합니다 (엔티티 추출, 관계 그래프 구축)")
    logger.info("   예상 처리 속도: 분당 4-6개 문서 (API 속도에 따라 다름)")
    logger.info("   1000개 문서 = 약 3-4시간 소요 예상\n")

    collector = RealEstateCollector()
    count = 0
    import time

    start_time = time.time()

    try:
        async for property_record in collector.collect_all_data(
            year_month=year_month,
            districts=districts,
            property_types=property_types,
        ):
            document = format_property_document(property_record)
            success = await lightrag_service.insert(document)

            if success:
                count += 1

                # Progress logging with time estimates
                if count % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = count / elapsed * 60 if elapsed > 0 else 0
                    logger.info(f"진행 중: {count}개 삽입 완료 | 처리 속도: {rate:.1f}개/분")

                # Rate limiting
                if count % 50 == 0:
                    await asyncio.sleep(0.5)

            # Check max_records limit
            if max_records and count >= max_records:
                logger.info(f"최대 레코드 수({max_records})에 도달하여 수집 중단")
                break

    except Exception as e:
        logger.error(f"데이터 수집 중 오류 발생: {e}")
        raise
    finally:
        await collector.close()

    logger.info(f"실거래가 데이터 {count}개 삽입 완료")
    return count


async def load_sample_data(lightrag_service: LightRAGService) -> dict[str, int]:
    """
    샘플 데이터 로딩 (소규모 테스트용).

    서울시 강남구, 서초구, 송파구의 최근 1개월 아파트 매매 데이터만 수집.
    """
    logger.info("=== 샘플 데이터 로딩 시작 ===")

    stats = {
        "districts": 0,
        "properties": 0,
    }

    # 1. 행정구역 데이터 (전체)
    stats["districts"] = await load_district_data(lightrag_service)

    # 2. 실거래가 데이터 (샘플: 강남, 서초, 송파 아파트 전월세)
    # Note: apartment_trade requires separate API activation
    stats["properties"] = await load_real_estate_data(
        lightrag_service,
        districts=["강남구", "서초구", "송파구"],
        property_types=["apartment_rent"],  # 전월세 데이터 (API key has permission)
        max_records=500,  # 샘플 데이터는 최대 500건만
    )

    logger.info("=== 샘플 데이터 로딩 완료 ===")
    logger.info(f"  - 행정구역: {stats['districts']}개")
    logger.info(f"  - 부동산 거래: {stats['properties']}개")

    return stats


async def load_full_data(
    lightrag_service: LightRAGService,
    districts: list[str] | None = None,
    year_month: str | None = None,
) -> dict[str, int]:
    """
    전체 데이터 로딩 (프로덕션용).

    모든 자치구의 실거래가 데이터를 수집합니다.
    시간이 오래 걸릴 수 있습니다 (수십 분 ~ 수 시간).
    """
    logger.info("=== 전체 데이터 로딩 시작 ===")

    stats = {
        "districts": 0,
        "properties": 0,
    }

    # 1. 행정구역 데이터
    stats["districts"] = await load_district_data(lightrag_service)

    # 2. 실거래가 데이터 (전체 또는 지정된 자치구)
    stats["properties"] = await load_real_estate_data(
        lightrag_service,
        districts=districts,
        year_month=year_month,
        property_types=None,  # 모든 유형 수집
        max_records=None,  # 무제한
    )

    logger.info("=== 전체 데이터 로딩 완료 ===")
    logger.info(f"  - 행정구역: {stats['districts']}개")
    logger.info(f"  - 부동산 거래: {stats['properties']}개")

    return stats


async def load_pdr_data(
    lightrag_service: LightRAGService,
    districts: list[str] | None = None,
    property_types: list[str] | None = None,
    trade_types: list[str] | None = None,
    start_year_month: str = "202401",
    end_year_month: str | None = None,
    max_records: int | None = None,
) -> int:
    """
    PublicDataReader를 사용하여 포괄적인 실거래가 데이터를 LightRAG에 삽입.

    Args:
        lightrag_service: LightRAG 서비스 인스턴스
        districts: 수집할 자치구 리스트 (None이면 서울시 전체 25개)
        property_types: 수집할 부동산 유형 (None이면 전체: 아파트, 오피스텔, 연립다세대, 단독다가구)
        trade_types: 수집할 거래 유형 (None이면 전체: 매매, 전월세)
        start_year_month: 시작 연월 (YYYYMM 형식)
        end_year_month: 종료 연월 (None이면 현재월)
        max_records: 최대 수집 레코드 수 (None이면 무제한)

    Returns:
        삽입된 문서 수
    """
    logger.info("=" * 60)
    logger.info("PublicDataReader 포괄적 데이터 로딩 시작")
    logger.info("=" * 60)
    logger.info(f"  - 자치구: {districts or '서울시 전체 (25개 구)'}")
    logger.info(f"  - 부동산 유형: {property_types or '전체 (아파트, 오피스텔, 연립다세대, 단독다가구)'}")
    logger.info(f"  - 거래 유형: {trade_types or '전체 (매매, 전월세)'}")
    logger.info(f"  - 기간: {start_year_month} ~ {end_year_month or '현재'}")
    logger.info(f"  - 최대 레코드: {max_records or '무제한'}")
    logger.info("")
    logger.info("⚠️  LightRAG는 각 문서를 깊이 분석합니다 (엔티티 추출, 관계 그래프 구축)")
    logger.info("   예상 처리 속도: 분당 4-6개 문서 (API 및 LLM 속도에 따라 다름)")
    logger.info("   대량 데이터의 경우 수 시간 ~ 수일 소요 가능")
    logger.info("=" * 60)

    collector = PublicDataReaderCollector()
    config = CollectionConfig(
        districts=districts,
        property_types=property_types,
        trade_types=trade_types,
        start_year_month=start_year_month,
        end_year_month=end_year_month,
        max_records=max_records,
    )

    count = 0
    import time

    start_time = time.time()
    last_log_time = start_time

    try:
        async for property_record in collector.collect_all_data(config):
            document = format_property_document(property_record)
            success = await lightrag_service.insert(document)

            if success:
                count += 1

                # 진행률 로깅 (30초마다 또는 100개마다)
                current_time = time.time()
                if count % 100 == 0 or (current_time - last_log_time) > 30:
                    elapsed = current_time - start_time
                    rate = count / elapsed * 60 if elapsed > 0 else 0
                    logger.info(
                        "📊 진행 중: %d개 삽입 완료 | 처리 속도: %.1f개/분 | 경과 시간: %.1f분",
                        count,
                        rate,
                        elapsed / 60,
                    )
                    last_log_time = current_time

                # Rate limiting (LightRAG에 과부하 방지)
                if count % 50 == 0:
                    await asyncio.sleep(1.0)

    except KeyboardInterrupt:
        logger.warning("\n⚠️ 사용자 중단 요청 - 현재까지 수집된 데이터는 저장됨")
    except Exception as e:
        logger.error(f"데이터 수집 중 오류 발생: {e}")
        raise
    finally:
        collector.close()

    total_time = time.time() - start_time
    logger.info("=" * 60)
    logger.info("✅ PublicDataReader 데이터 로딩 완료!")
    logger.info(f"   - 총 삽입 문서: {count}개")
    logger.info(f"   - 총 소요 시간: {total_time / 60:.1f}분")
    logger.info(f"   - 평균 처리 속도: {count / total_time * 60:.1f}개/분")
    logger.info("=" * 60)

    return count


async def load_comprehensive_data(
    lightrag_service: LightRAGService,
    start_year_month: str = "202401",
    end_year_month: str | None = None,
    max_records: int | None = None,
) -> dict[str, int]:
    """
    서울시 전체 25개 자치구의 모든 부동산 유형 데이터를 로딩.

    이 함수는 다음 데이터를 모두 수집합니다:
    - 25개 자치구
    - 4개 부동산 유형 (아파트, 오피스텔, 연립다세대, 단독다가구)
    - 2개 거래 유형 (매매, 전월세)
    - 지정된 기간의 월별 데이터
    """
    logger.info("=" * 70)
    logger.info("🏠 서울시 전체 부동산 데이터 포괄적 로딩 시작")
    logger.info("=" * 70)

    stats = {
        "districts": 0,
        "properties": 0,
    }

    # 1. 행정구역 데이터
    stats["districts"] = await load_district_data(lightrag_service)

    # 2. PublicDataReader로 전체 실거래가 데이터 수집
    stats["properties"] = await load_pdr_data(
        lightrag_service,
        districts=None,  # 서울시 전체
        property_types=None,  # 모든 유형
        trade_types=None,  # 매매 + 전월세
        start_year_month=start_year_month,
        end_year_month=end_year_month,
        max_records=max_records,
    )

    logger.info("=" * 70)
    logger.info("🎉 서울시 전체 부동산 데이터 포괄적 로딩 완료!")
    logger.info(f"   - 행정구역: {stats['districts']}개")
    logger.info(f"   - 부동산 거래: {stats['properties']}개")
    logger.info(f"   - 총 문서: {stats['districts'] + stats['properties']}개")
    logger.info("=" * 70)

    return stats


@app.command()
def load(
    mode: str = typer.Option(
        "sample",
        "--mode",
        "-m",
        help="데이터 로딩 모드: 'sample' (테스트용) 또는 'full' (전체)",
    ),
    districts: str = typer.Option(
        None,
        "--districts",
        "-d",
        help="수집할 자치구 (쉼표로 구분, 예: '강남구,서초구,송파구')",
    ),
    year_month: str = typer.Option(
        None,
        "--year-month",
        "-ym",
        help="수집 기준 연월 (YYYYMM 형식, 예: '202410')",
    ),
    limit: int = typer.Option(
        None,
        "--limit",
        "-l",
        help="최대 수집 레코드 수 (테스트용, 예: 10)",
    ),
) -> None:
    """
    국토교통부 및 서울시 공공 데이터를 LightRAG에 로딩합니다.

    Examples:
        # 샘플 데이터 로딩 (테스트용)
        uv run python -m scripts.load_data --mode sample

        # 소량 테스트 (10개만)
        uv run python -m scripts.load_data --mode full --districts 강남구 --limit 10

        # 전체 데이터 로딩 (매우 느림: 수 시간 소요)
        uv run python -m scripts.load_data --mode full

        # 특정 자치구만 로딩
        uv run python -m scripts.load_data --mode full --districts 강남구,서초구

        # 특정 연월 데이터 로딩
        uv run python -m scripts.load_data --mode full --year-month 202410
    """

    async def _run():
        # Initialize services
        logger.info("서비스 초기화 중...")
        ai_service = AIService()
        await ai_service.initialize()

        lightrag_service = LightRAGService(ai_service=ai_service)
        await lightrag_service.initialize()

        try:
            # Parse districts
            district_list = None
            if districts:
                district_list = [d.strip() for d in districts.split(",")]

            # Load data based on mode
            if mode == "sample":
                stats = await load_sample_data(lightrag_service)
            elif mode == "full":
                # If limit is provided, use custom loading
                if limit:
                    logger.info(f"⚠️  제한 모드: 최대 {limit}개 문서만 수집합니다")
                    stats = {
                        "districts": await load_district_data(lightrag_service),
                        "properties": await load_real_estate_data(
                            lightrag_service,
                            districts=district_list,
                            year_month=year_month,
                            max_records=limit,
                        ),
                    }
                else:
                    stats = await load_full_data(
                        lightrag_service,
                        districts=district_list,
                        year_month=year_month,
                    )
            else:
                raise ValueError(f"알 수 없는 모드: {mode}")

            logger.info("\n✅ 데이터 로딩 성공!")
            logger.info(
                f"총 {stats['districts'] + stats['properties']}개 문서가 LightRAG에 삽입되었습니다."
            )

        except Exception as e:
            logger.error(f"\n❌ 데이터 로딩 실패: {e}", exc_info=True)
            raise typer.Exit(code=1)
        finally:
            await lightrag_service.finalize()
            await ai_service.close()

    asyncio.run(_run())


@app.command()
def check() -> None:
    """
    데이터 수집 환경 및 API 연결 상태를 확인합니다.
    """

    async def _check():
        logger.info("=== 환경 설정 확인 ===")

        # Check API keys
        if settings.MOLIT_API_KEY:
            logger.info("✅ 국토교통부 API 키: 설정됨")
        else:
            logger.error("❌ 국토교통부 API 키: 미설정 (MOLIT_API_KEY 환경변수 확인)")

        if settings.ANTHROPIC_API_KEY:
            logger.info("✅ Anthropic API 키: 설정됨")
        else:
            logger.error("❌ Anthropic API 키: 미설정 (ANTHROPIC_API_KEY 환경변수 확인)")

        # Check data sources
        logger.info(f"\n시군구 데이터: {len(list(SigunguServiceSingleton.all_sigungu()))}개 로드됨")

        # Test MOLIT API connection
        logger.info("\n국토교통부 API 연결 테스트 중...")
        collector = RealEstateCollector()
        try:
            is_connected = await collector.test_connection()
            if is_connected:
                logger.info("✅ 국토교통부 API 연결 성공")
            else:
                logger.error("❌ 국토교통부 API 연결 실패")
        except Exception as e:
            logger.error(f"❌ 국토교통부 API 연결 오류: {e}")
        finally:
            await collector.close()

        # Check LightRAG storage
        logger.info(f"\nLightRAG 작업 디렉토리: {settings.LIGHTRAG_WORKING_DIR}")
        logger.info(f"LightRAG 워크스페이스: {settings.LIGHTRAG_WORKSPACE}")

    asyncio.run(_check())


@app.command()
def comprehensive(
    districts: str = typer.Option(
        None,
        "--districts",
        "-d",
        help="수집할 자치구 (쉼표로 구분, 예: '강남구,서초구'). 미지정 시 서울 전체 25개 구",
    ),
    property_types: str = typer.Option(
        None,
        "--property-types",
        "-pt",
        help="수집할 부동산 유형 (쉼표로 구분: 아파트,오피스텔,연립다세대,단독다가구). 미지정 시 전체",
    ),
    trade_types: str = typer.Option(
        None,
        "--trade-types",
        "-tt",
        help="수집할 거래 유형 (쉼표로 구분: 매매,전월세). 미지정 시 전체",
    ),
    start_month: str = typer.Option(
        "202401",
        "--start",
        "-s",
        help="시작 연월 (YYYYMM 형식, 예: '202401')",
    ),
    end_month: str = typer.Option(
        None,
        "--end",
        "-e",
        help="종료 연월 (YYYYMM 형식). 미지정 시 현재월",
    ),
    limit: int = typer.Option(
        None,
        "--limit",
        "-l",
        help="최대 수집 레코드 수 (테스트용)",
    ),
) -> None:
    """
    PublicDataReader를 사용하여 포괄적인 부동산 데이터를 수집합니다.

    이 명령어는 서울시 전체 25개 자치구의 모든 부동산 유형 데이터를 수집합니다:
    - 4개 부동산 유형: 아파트, 오피스텔, 연립다세대, 단독다가구
    - 2개 거래 유형: 매매, 전월세
    - 지정된 기간의 월별 데이터

    Examples:
        # 소량 테스트 (100개만)
        uv run python -m scripts.load_data comprehensive --limit 100

        # 강남구만, 2024년 데이터
        uv run python -m scripts.load_data comprehensive -d 강남구 -s 202401 -e 202412

        # 아파트 매매만, 전체 서울
        uv run python -m scripts.load_data comprehensive -pt 아파트 -tt 매매

        # 전체 데이터 수집 (매우 느림: 수 시간 ~ 수일 소요)
        uv run python -m scripts.load_data comprehensive
    """

    async def _run():
        # Initialize services
        logger.info("서비스 초기화 중...")
        ai_service = AIService()
        await ai_service.initialize()

        lightrag_service = LightRAGService(ai_service=ai_service)
        await lightrag_service.initialize()

        try:
            # Parse arguments
            district_list = None
            if districts:
                district_list = [d.strip() for d in districts.split(",")]

            property_type_list = None
            if property_types:
                property_type_list = [p.strip() for p in property_types.split(",")]

            trade_type_list = None
            if trade_types:
                trade_type_list = [t.strip() for t in trade_types.split(",")]

            # Load comprehensive data
            if district_list or property_type_list or trade_type_list or limit:
                # Custom filtering
                stats = {
                    "districts": await load_district_data(lightrag_service),
                    "properties": await load_pdr_data(
                        lightrag_service,
                        districts=district_list,
                        property_types=property_type_list,
                        trade_types=trade_type_list,
                        start_year_month=start_month,
                        end_year_month=end_month,
                        max_records=limit,
                    ),
                }
            else:
                # Full comprehensive load
                stats = await load_comprehensive_data(
                    lightrag_service,
                    start_year_month=start_month,
                    end_year_month=end_month,
                    max_records=limit,
                )

            logger.info("\n✅ 데이터 로딩 성공!")
            logger.info(
                f"총 {stats['districts'] + stats['properties']}개 문서가 LightRAG에 삽입되었습니다."
            )

        except Exception as e:
            logger.error(f"\n❌ 데이터 로딩 실패: {e}", exc_info=True)
            raise typer.Exit(code=1)
        finally:
            await lightrag_service.finalize()
            await ai_service.close()

    asyncio.run(_run())


async def load_reb_statistics(
    lightrag_service: LightRAGService,
    stat_types: list[str] | None = None,
    start_year_month: str = "202401",
    end_year_month: str | None = None,
    seoul_only: bool = True,
    max_records: int | None = None,
) -> int:
    """
    한국부동산원 R-ONE 통계 데이터를 LightRAG에 삽입.

    Args:
        lightrag_service: LightRAG 서비스 인스턴스
        stat_types: 수집할 통계 유형 (None이면 기본 통계)
        start_year_month: 시작 연월
        end_year_month: 종료 연월
        seoul_only: 서울 지역만 수집
        max_records: 최대 레코드 수

    Returns:
        삽입된 문서 수
    """
    logger.info("=" * 60)
    logger.info("📊 한국부동산원 R-ONE 통계 데이터 로딩 시작")
    logger.info("=" * 60)
    logger.info(f"  - 통계 유형: {stat_types or '기본 (가격지수, 평균가격)'}")
    logger.info(f"  - 기간: {start_year_month} ~ {end_year_month or '현재'}")
    logger.info(f"  - 서울만: {seoul_only}")
    logger.info(f"  - 최대 레코드: {max_records or '무제한'}")
    logger.info("=" * 60)

    collector = REBCollector()
    config = REBCollectionConfig(
        stat_types=stat_types,
        start_year_month=start_year_month,
        end_year_month=end_year_month,
        seoul_only=seoul_only,
        include_national=True,
        max_records=max_records,
    )

    count = 0
    import time

    start_time = time.time()
    last_log_time = start_time

    try:
        async for record in collector.collect_all_statistics(config):
            document = format_statistics_document(record)
            success = await lightrag_service.insert(document)

            if success:
                count += 1

                # 진행률 로깅
                current_time = time.time()
                if count % 50 == 0 or (current_time - last_log_time) > 30:
                    elapsed = current_time - start_time
                    rate = count / elapsed * 60 if elapsed > 0 else 0
                    logger.info(
                        "📊 진행 중: %d개 삽입 완료 | 처리 속도: %.1f개/분",
                        count,
                        rate,
                    )
                    last_log_time = current_time

                # Rate limiting
                if count % 50 == 0:
                    await asyncio.sleep(0.5)

    except KeyboardInterrupt:
        logger.warning("\n⚠️ 사용자 중단 요청")
    except Exception as e:
        logger.error(f"데이터 수집 중 오류 발생: {e}")
        raise
    finally:
        await collector.close()

    total_time = time.time() - start_time
    logger.info("=" * 60)
    logger.info("✅ R-ONE 통계 데이터 로딩 완료!")
    logger.info(f"   - 총 삽입 문서: {count}개")
    logger.info(f"   - 총 소요 시간: {total_time / 60:.1f}분")
    logger.info("=" * 60)

    return count


@app.command()
def reb_stats(
    stat_types: str = typer.Option(
        None,
        "--stat-types",
        "-st",
        help="수집할 통계 유형 (쉼표로 구분). 예: apartment_sale_index,apartment_rent_index",
    ),
    start_month: str = typer.Option(
        "202401",
        "--start",
        "-s",
        help="시작 연월 (YYYYMM)",
    ),
    end_month: str = typer.Option(
        None,
        "--end",
        "-e",
        help="종료 연월 (YYYYMM). 미지정 시 현재월",
    ),
    seoul_only: bool = typer.Option(
        True,
        "--seoul-only/--all-regions",
        help="서울 지역만 수집 / 전체 지역 수집",
    ),
    limit: int = typer.Option(
        None,
        "--limit",
        "-l",
        help="최대 수집 레코드 수",
    ),
) -> None:
    """
    한국부동산원 R-ONE 통계 데이터를 LightRAG에 로딩합니다.

    수집 가능한 통계:
    - apartment_sale_index: 아파트 매매가격지수
    - apartment_rent_index: 아파트 전세가격지수
    - apartment_sale_price: 아파트 평균 매매가격
    - apartment_rent_price: 아파트 평균 전세가격
    - seoul_sale_index: 서울 아파트 매매가격지수
    - seoul_rent_index: 서울 아파트 전세가격지수

    Examples:
        # 기본 통계 수집 (서울만, 2024년)
        uv run python -m scripts.load_data reb-stats

        # 특정 통계만 수집
        uv run python -m scripts.load_data reb-stats -st apartment_sale_index,apartment_rent_index

        # 전체 지역 수집
        uv run python -m scripts.load_data reb-stats --all-regions

        # 테스트 (100개만)
        uv run python -m scripts.load_data reb-stats --limit 100
    """

    async def _run():
        logger.info("서비스 초기화 중...")
        ai_service = AIService()
        await ai_service.initialize()

        lightrag_service = LightRAGService(ai_service=ai_service)
        await lightrag_service.initialize()

        try:
            stat_type_list = None
            if stat_types:
                stat_type_list = [s.strip() for s in stat_types.split(",")]

            count = await load_reb_statistics(
                lightrag_service,
                stat_types=stat_type_list,
                start_year_month=start_month,
                end_year_month=end_month,
                seoul_only=seoul_only,
                max_records=limit,
            )

            logger.info(f"\n✅ 총 {count}개 통계 문서가 LightRAG에 삽입되었습니다.")

        except Exception as e:
            logger.error(f"\n❌ 데이터 로딩 실패: {e}", exc_info=True)
            raise typer.Exit(code=1)
        finally:
            await lightrag_service.finalize()
            await ai_service.close()

    asyncio.run(_run())


async def load_seoul_redevelopment(
    lightrag_service: LightRAGService,
    api_key: str | None = None,
    max_records: int | None = None,
) -> int:
    """
    서울시 정비사업 현황 데이터를 LightRAG에 삽입.

    Args:
        lightrag_service: LightRAG 서비스 인스턴스
        api_key: 서울 열린 데이터 API 키 (None이면 환경변수 사용)
        max_records: 최대 레코드 수

    Returns:
        삽입된 문서 수
    """
    logger.info("=" * 60)
    logger.info("🏗️ 서울시 정비사업 현황 데이터 로딩 시작")
    logger.info("=" * 60)
    logger.info(f"  - 데이터: 서울시 정비사업 현황 (OA-20281)")
    logger.info(f"  - 최대 레코드: {max_records or '무제한'}")
    logger.info("=" * 60)

    collector = SeoulOpenDataCollector(api_key=api_key)

    count = 0
    import time

    start_time = time.time()
    last_log_time = start_time

    try:
        async for record in collector.collect_redevelopment_data(
            max_records=max_records,
        ):
            document = format_redevelopment_document(record)
            success = await lightrag_service.insert(document)

            if success:
                count += 1

                # 진행률 로깅
                current_time = time.time()
                if count % 50 == 0 or (current_time - last_log_time) > 30:
                    elapsed = current_time - start_time
                    rate = count / elapsed * 60 if elapsed > 0 else 0
                    logger.info(
                        "🏗️ 진행 중: %d개 삽입 완료 | 처리 속도: %.1f개/분",
                        count,
                        rate,
                    )
                    last_log_time = current_time

                # Rate limiting
                if count % 50 == 0:
                    await asyncio.sleep(0.5)

    except KeyboardInterrupt:
        logger.warning("\n⚠️ 사용자 중단 요청")
    except Exception as e:
        logger.error(f"데이터 수집 중 오류 발생: {e}")
        raise
    finally:
        await collector.close()

    total_time = time.time() - start_time
    logger.info("=" * 60)
    logger.info("✅ 정비사업 현황 데이터 로딩 완료!")
    logger.info(f"   - 총 삽입 문서: {count}개")
    logger.info(f"   - 총 소요 시간: {total_time / 60:.1f}분")
    logger.info("=" * 60)

    return count


@app.command()
def seoul_redevelopment(
    api_key: str = typer.Option(
        None,
        "--api-key",
        "-k",
        help="서울 열린 데이터 API 키 (미지정 시 SEOUL_OPEN_API_KEY 환경변수 사용)",
    ),
    limit: int = typer.Option(
        None,
        "--limit",
        "-l",
        help="최대 수집 레코드 수",
    ),
) -> None:
    """
    서울시 정비사업 현황 데이터를 LightRAG에 로딩합니다.

    서울시 재개발, 재건축 등 정비사업 현황 정보를 수집합니다:
    - 사업명, 사업 유형 (재개발/재건축/도시환경정비 등)
    - 위치 정보 (구, 동, 주소)
    - 진행 단계 (조합설립/사업시행인가/착공/준공 등)
    - 규모 (면적, 세대수)
    - 조합, 시공사 정보

    Examples:
        # API 키로 수집
        uv run python -m scripts.load_data seoul-redevelopment -k YOUR_API_KEY

        # 테스트 (100개만)
        uv run python -m scripts.load_data seoul-redevelopment -k YOUR_API_KEY --limit 100

        # 환경변수 사용
        export SEOUL_OPEN_API_KEY=YOUR_API_KEY
        uv run python -m scripts.load_data seoul-redevelopment
    """

    async def _run():
        logger.info("서비스 초기화 중...")
        ai_service = AIService()
        await ai_service.initialize()

        lightrag_service = LightRAGService(ai_service=ai_service)
        await lightrag_service.initialize()

        try:
            count = await load_seoul_redevelopment(
                lightrag_service,
                api_key=api_key,
                max_records=limit,
            )

            logger.info(f"\n✅ 총 {count}개 정비사업 문서가 LightRAG에 삽입되었습니다.")

        except Exception as e:
            logger.error(f"\n❌ 데이터 로딩 실패: {e}", exc_info=True)
            raise typer.Exit(code=1)
        finally:
            await lightrag_service.finalize()
            await ai_service.close()

    asyncio.run(_run())


async def load_seoul_data_by_category(
    lightrag_service: LightRAGService,
    category: DataCategory | None = None,
    service_keys: list[str] | None = None,
    max_records_per_service: int | None = None,
) -> int:
    """
    서울 열린 데이터를 카테고리 또는 서비스별로 수집.

    Args:
        lightrag_service: LightRAG 서비스 인스턴스
        category: 수집할 카테고리 (None이면 service_keys 사용)
        service_keys: 수집할 서비스 키 리스트 (None이면 category의 모든 서비스)
        max_records_per_service: 서비스당 최대 레코드 수

    Returns:
        삽입된 총 문서 수
    """
    collector = SeoulOpenDataCollector()

    # 수집할 서비스 결정
    if service_keys:
        services_to_collect = service_keys
    elif category:
        services_to_collect = [
            k for k, v in SEOUL_SERVICES.items() if v.category == category
        ]
    else:
        services_to_collect = list(SEOUL_SERVICES.keys())

    total_count = 0
    import time

    start_time = time.time()

    try:
        for service_key in services_to_collect:
            service = SEOUL_SERVICES.get(service_key)
            if not service:
                logger.warning(f"알 수 없는 서비스: {service_key}")
                continue

            logger.info(f"\n📥 수집 중: {service.description} ({service.service_name})")
            service_count = 0
            last_log_time = time.time()

            try:
                async for record in collector.collect_data(
                    service_key,
                    max_records=max_records_per_service,
                ):
                    document = format_document(record)
                    success = await lightrag_service.insert(document)

                    if success:
                        service_count += 1
                        total_count += 1

                        # 진행률 로깅
                        current_time = time.time()
                        if service_count % 50 == 0 or (current_time - last_log_time) > 30:
                            elapsed = current_time - start_time
                            rate = total_count / elapsed * 60 if elapsed > 0 else 0
                            logger.info(
                                f"   {service_key}: {service_count}개 | 총 {total_count}개 | {rate:.1f}개/분"
                            )
                            last_log_time = current_time

                        # Rate limiting
                        if service_count % 50 == 0:
                            await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"❌ {service_key} 수집 실패: {e}")
                continue

            logger.info(f"   ✅ {service_key} 완료: {service_count}개")

    except KeyboardInterrupt:
        logger.warning("\n⚠️ 사용자 중단 요청")
    finally:
        await collector.close()

    return total_count


@app.command()
def seoul_transport(
    api_key: str = typer.Option(
        None,
        "--api-key",
        "-k",
        help="서울 열린 데이터 API 키 (미지정 시 SEOUL_OPEN_API_KEY 환경변수 사용)",
    ),
    limit: int = typer.Option(
        None,
        "--limit",
        "-l",
        help="서비스당 최대 수집 레코드 수",
    ),
    services: str = typer.Option(
        None,
        "--services",
        "-s",
        help="수집할 서비스 (쉼표로 구분: subway_station,subway_info,bus_stop). 미지정 시 전체",
    ),
) -> None:
    """
    서울시 교통/인프라 데이터를 LightRAG에 로딩합니다.

    수집 가능한 데이터 (2024.12 작동 확인):
    - subway_station: 지하철역 정보 (역코드로 조회)
    - subway_info: 지하철역 정보 (역명으로 조회)
    - bus_stop: 버스정류소 위치정보 (좌표 포함)

    Examples:
        # 모든 교통 데이터 수집
        uv run python -m scripts.load_data seoul-transport

        # 지하철 데이터만
        uv run python -m scripts.load_data seoul-transport -s subway_station,subway_info

        # 테스트 (서비스당 100개)
        uv run python -m scripts.load_data seoul-transport --limit 100
    """

    async def _run():
        logger.info("=" * 60)
        logger.info("🚇 서울시 교통/인프라 데이터 로딩 시작")
        logger.info("=" * 60)

        logger.info("서비스 초기화 중...")
        ai_service = AIService()
        await ai_service.initialize()

        lightrag_service = LightRAGService(ai_service=ai_service)
        await lightrag_service.initialize()

        try:
            service_list = None
            if services:
                service_list = [s.strip() for s in services.split(",")]

            count = await load_seoul_data_by_category(
                lightrag_service,
                category=DataCategory.TRANSPORT if not service_list else None,
                service_keys=service_list,
                max_records_per_service=limit,
            )

            logger.info("=" * 60)
            logger.info(f"✅ 총 {count}개 교통 문서가 LightRAG에 삽입되었습니다.")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"\n❌ 데이터 로딩 실패: {e}", exc_info=True)
            raise typer.Exit(code=1)
        finally:
            await lightrag_service.finalize()
            await ai_service.close()

    asyncio.run(_run())


@app.command()
def seoul_real_estate(
    api_key: str = typer.Option(
        None,
        "--api-key",
        "-k",
        help="서울 열린 데이터 API 키 (미지정 시 SEOUL_OPEN_API_KEY 환경변수 사용)",
    ),
    limit: int = typer.Option(
        None,
        "--limit",
        "-l",
        help="최대 수집 레코드 수",
    ),
) -> None:
    """
    서울시 부동산 실거래가 데이터를 LightRAG에 로딩합니다.

    수집 가능한 데이터 (2024.12 작동 확인):
    - real_transaction: 부동산 실거래가 정보 (OA-21275) - 277만건+
      (매매/전월세 통합, 아파트/연립다세대/오피스텔 등)

    NOTE: 전월세가(OA-21276), 공시지가(OA-1180) 등은 현재 서울시 API 오류로 미제공

    Examples:
        # 실거래가 데이터 수집
        uv run python -m scripts.load_data seoul-real-estate

        # 테스트 (100개만)
        uv run python -m scripts.load_data seoul-real-estate --limit 100
    """

    async def _run():
        logger.info("=" * 60)
        logger.info("🏠 서울시 부동산 실거래가 데이터 로딩 시작")
        logger.info("=" * 60)

        logger.info("서비스 초기화 중...")
        ai_service = AIService()
        await ai_service.initialize()

        lightrag_service = LightRAGService(ai_service=ai_service)
        await lightrag_service.initialize()

        try:
            # real_transaction 서비스만 수집 (현재 작동하는 유일한 real_estate 카테고리 서비스)
            count = await load_seoul_data_by_category(
                lightrag_service,
                service_keys=["real_transaction"],
                max_records_per_service=limit,
            )

            logger.info("=" * 60)
            logger.info(f"✅ 총 {count}개 실거래가 문서가 LightRAG에 삽입되었습니다.")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"\n❌ 데이터 로딩 실패: {e}", exc_info=True)
            raise typer.Exit(code=1)
        finally:
            await lightrag_service.finalize()
            await ai_service.close()

    asyncio.run(_run())


# NOTE: seoul_land_use 명령어는 현재 서울시 API에서 해당 서비스들이 ERROR-500 반환으로 주석 처리
# 향후 서비스 재개 시 활성화 가능
# @app.command()
def _seoul_land_use_disabled(
    api_key: str = typer.Option(
        None,
        "--api-key",
        "-k",
        help="서울 열린 데이터 API 키 (미지정 시 SEOUL_OPEN_API_KEY 환경변수 사용)",
    ),
    limit: int = typer.Option(
        None,
        "--limit",
        "-l",
        help="서비스당 최대 수집 레코드 수",
    ),
    services: str = typer.Option(
        None,
        "--services",
        "-s",
        help="수집할 서비스 (쉼표로 구분). 미지정 시 전체",
    ),
) -> None:
    """
    서울시 용도지역/공간정보 데이터를 LightRAG에 로딩합니다.

    수집 가능한 데이터:
    - land_use_zone: 용도지역(도시지역) 공간정보 (OA-21136)
    - district_unit_zone: 지구단위계획구역 공간정보 (OA-21161)
    - greenbelt: 개발제한구역 공간정보 (OA-21123)

    Examples:
        # 모든 용도지역 데이터 수집
        uv run python -m scripts.load_data seoul-land-use

        # 개발제한구역만
        uv run python -m scripts.load_data seoul-land-use -s greenbelt

        # 테스트 (서비스당 100개)
        uv run python -m scripts.load_data seoul-land-use --limit 100
    """

    async def _run():
        logger.info("=" * 60)
        logger.info("🗺️ 서울시 용도지역/공간정보 데이터 로딩 시작")
        logger.info("=" * 60)

        logger.info("서비스 초기화 중...")
        ai_service = AIService()
        await ai_service.initialize()

        lightrag_service = LightRAGService(ai_service=ai_service)
        await lightrag_service.initialize()

        try:
            service_list = None
            if services:
                service_list = [s.strip() for s in services.split(",")]

            count = await load_seoul_data_by_category(
                lightrag_service,
                category=DataCategory.LAND_USE if not service_list else None,
                service_keys=service_list,
                max_records_per_service=limit,
            )

            logger.info("=" * 60)
            logger.info(f"✅ 총 {count}개 용도지역 문서가 LightRAG에 삽입되었습니다.")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"\n❌ 데이터 로딩 실패: {e}", exc_info=True)
            raise typer.Exit(code=1)
        finally:
            await lightrag_service.finalize()
            await ai_service.close()

    asyncio.run(_run())


@app.command()
def seoul_all(
    api_key: str = typer.Option(
        None,
        "--api-key",
        "-k",
        help="서울 열린 데이터 API 키 (미지정 시 SEOUL_OPEN_API_KEY 환경변수 사용)",
    ),
    limit: int = typer.Option(
        None,
        "--limit",
        "-l",
        help="서비스당 최대 수집 레코드 수",
    ),
    categories: str = typer.Option(
        None,
        "--categories",
        "-c",
        help="수집할 카테고리 (쉼표로 구분: real_estate,redevelopment,transport,population,agency). 미지정 시 전체",
    ),
) -> None:
    """
    서울 열린 데이터 광장의 모든 부동산 관련 데이터를 수집합니다.

    현재 작동하는 서비스 (2024.12 기준, 총 7개):
    - real_estate: 실거래가 (1개) - 277만건+
    - redevelopment: 정비사업 현황 (1개)
    - transport: 지하철역, 버스정류소 (3개)
    - population: 생활인구 (1개)
    - agency: 부동산 중개업소 (1개)

    NOTE: land_use(용도지역), 전월세가, 공시지가 등 일부 서비스는 서울시 API 오류로 미제공

    Examples:
        # 모든 서울 데이터 수집
        uv run python -m scripts.load_data seoul-all

        # 특정 카테고리만
        uv run python -m scripts.load_data seoul-all -c real_estate,transport

        # 테스트 (서비스당 50개)
        uv run python -m scripts.load_data seoul-all --limit 50
    """

    async def _run():
        logger.info("=" * 70)
        logger.info("🌆 서울 열린 데이터 광장 전체 데이터 로딩 시작")
        logger.info("=" * 70)
        logger.info(f"총 {len(SEOUL_SERVICES)}개 서비스 수집 예정")
        logger.info("")

        # 카테고리별 서비스 수 표시
        for cat in DataCategory:
            services = [k for k, v in SEOUL_SERVICES.items() if v.category == cat]
            logger.info(f"  {cat.value}: {len(services)}개 - {', '.join(services)}")

        logger.info("")
        logger.info("⚠️  대량 데이터 수집은 수 시간이 소요될 수 있습니다.")
        logger.info("=" * 70)

        logger.info("\n서비스 초기화 중...")
        ai_service = AIService()
        await ai_service.initialize()

        lightrag_service = LightRAGService(ai_service=ai_service)
        await lightrag_service.initialize()

        try:
            # 카테고리 필터링
            category_filter = None
            if categories:
                category_list = [c.strip() for c in categories.split(",")]
                # 해당 카테고리의 모든 서비스 키 수집
                service_keys = []
                for cat_name in category_list:
                    try:
                        cat = DataCategory(cat_name)
                        service_keys.extend(
                            [k for k, v in SEOUL_SERVICES.items() if v.category == cat]
                        )
                    except ValueError:
                        logger.warning(f"알 수 없는 카테고리: {cat_name}")

                count = await load_seoul_data_by_category(
                    lightrag_service,
                    service_keys=service_keys if service_keys else None,
                    max_records_per_service=limit,
                )
            else:
                # 전체 수집
                count = await load_seoul_data_by_category(
                    lightrag_service,
                    max_records_per_service=limit,
                )

            logger.info("=" * 70)
            logger.info("🎉 서울 열린 데이터 전체 로딩 완료!")
            logger.info(f"   총 {count}개 문서가 LightRAG에 삽입되었습니다.")
            logger.info("=" * 70)

        except Exception as e:
            logger.error(f"\n❌ 데이터 로딩 실패: {e}", exc_info=True)
            raise typer.Exit(code=1)
        finally:
            await lightrag_service.finalize()
            await ai_service.close()

    asyncio.run(_run())


@app.command()
def list_options() -> None:
    """
    사용 가능한 자치구, 부동산 유형, 거래 유형, R-ONE 통계 목록을 표시합니다.
    """
    logger.info("=" * 50)
    logger.info("📍 서울시 자치구 목록 (25개)")
    logger.info("=" * 50)
    for code, name in sorted(SEOUL_DISTRICTS.items()):
        logger.info(f"  {code}: {name}")

    logger.info("")
    logger.info("=" * 50)
    logger.info("🏠 부동산 유형 (PublicDataReader)")
    logger.info("=" * 50)
    logger.info("  - 아파트")
    logger.info("  - 오피스텔")
    logger.info("  - 연립다세대")
    logger.info("  - 단독다가구")

    logger.info("")
    logger.info("=" * 50)
    logger.info("💰 거래 유형 (PublicDataReader)")
    logger.info("=" * 50)
    logger.info("  - 매매")
    logger.info("  - 전월세 (전세/월세 포함)")

    logger.info("")
    logger.info("=" * 50)
    logger.info("🏢 부동산 유형 (RealEstateCollector - data.go.kr)")
    logger.info("=" * 50)
    property_type_desc = {
        "apartment_trade": "아파트 매매",
        "apartment_trade_detail": "아파트 매매 상세 (실거래가 상세)",
        "apartment_rent": "아파트 전월세",
        "multifamily_trade": "연립다세대 매매",
        "multifamily_rent": "연립다세대 전월세",
        "officetel_trade": "오피스텔 매매",
        "officetel_rent": "오피스텔 전월세",
    }
    for prop_type in SUPPORTED_PROPERTY_TYPES:
        desc = property_type_desc.get(prop_type, prop_type)
        logger.info(f"  {prop_type}: {desc}")

    logger.info("")
    logger.info("=" * 50)
    logger.info("📊 R-ONE 통계 유형 (한국부동산원)")
    logger.info("=" * 50)
    for key, config in STATISTICS_TABLES.items():
        logger.info(f"  {key}:")
        logger.info(f"    - {config.name_ko}")
        logger.info(f"    - {config.description}")

    logger.info("")
    logger.info("=" * 50)
    logger.info("🌆 서울 열린 데이터 광장 (서울시)")
    logger.info("=" * 50)
    logger.info(f"  총 {len(SEOUL_SERVICES)}개 데이터셋")
    logger.info("")

    for cat in DataCategory:
        services = {k: v for k, v in SEOUL_SERVICES.items() if v.category == cat}
        if services:
            logger.info(f"  [{cat.value}] ({len(services)}개)")
            for key, service in services.items():
                logger.info(f"    - {key}: {service.description} ({service.data_code})")
            logger.info("")


if __name__ == "__main__":
    app()
