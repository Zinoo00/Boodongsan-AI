"""
국토교통부 및 서울시 공공 데이터 로딩 스크립트.

이 스크립트는 다음 데이터 소스에서 데이터를 수집하고 LightRAG에 삽입합니다:
1. 국토교통부 (MOLIT) - 실거래가 데이터
2. 서울시 열린 데이터 광장 - 시군구 행정구역 정보

Usage:
    uv run python -m scripts.load_data --help
    uv run python -m scripts.load_data load --mode sample
    uv run python -m scripts.load_data load --mode full --districts 강남구,서초구
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

import typer

from core.config import settings
from data.collectors.real_estate_collector import RealEstateCollector
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


@app.command()
def load(
    mode: str = typer.Option(
        "sample",
        "load --mode",
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
        uv run python -m scripts.load_data load --mode sample

        # 소량 테스트 (10개만)
        uv run python -m scripts.load_data load --mode full --districts 강남구 --limit 10

        # 전체 데이터 로딩 (매우 느림: 수 시간 소요)
        uv run python -m scripts.load_data load --mode full

        # 특정 자치구만 로딩
        uv run python -m scripts.load_data load --mode full --districts 강남구,서초구

        # 특정 연월 데이터 로딩
        uv run python -m scripts.load_data load --mode full --year-month 202410
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


if __name__ == "__main__":
    app()
