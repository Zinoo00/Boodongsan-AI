"""
한국부동산원 R-ONE API 데이터 수집기.

한국부동산원의 부동산통계정보시스템(R-ONE)에서 제공하는 Open API를 통해
부동산 가격지수, 시장동향 등의 통계 데이터를 수집합니다.

API 문서: https://www.reb.or.kr/r-one/portal/openapi/openApiDevPage.do

수집 가능한 데이터:
- 아파트 매매가격지수
- 아파트 전세가격지수
- 아파트 평균 매매가격
- 전세가격 대비 보증금 비율
- 토지가격지수

Usage:
    from data.collectors.reb_collector import REBCollector

    collector = REBCollector()
    async for record in collector.collect_all_statistics():
        print(record)
"""

from __future__ import annotations

import asyncio
import logging
import ssl
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

# R-ONE API 기본 URL
REB_API_BASE_URL = "https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do"

# 데이터 주기 코드
CYCLE_MONTHLY = "MM"
CYCLE_QUARTERLY = "QQ"
CYCLE_YEARLY = "YY"


@dataclass
class StatisticsTableConfig:
    """통계표 설정."""

    statbl_id: str  # 통계표 ID (예: A_2024_00045)
    cycle_cd: str  # 데이터 주기 (MM, QQ, YY)
    name_ko: str  # 한국어 이름
    name_en: str  # 영어 이름
    description: str  # 설명


# 사용 가능한 통계표 목록
STATISTICS_TABLES: dict[str, StatisticsTableConfig] = {
    "apartment_sale_index": StatisticsTableConfig(
        statbl_id="A_2024_00045",
        cycle_cd=CYCLE_MONTHLY,
        name_ko="아파트 매매가격지수",
        name_en="Apartment Sale Price Index",
        description="전국 및 지역별 아파트 매매가격지수 (기준: 2021.06 = 100)",
    ),
    "apartment_rent_index": StatisticsTableConfig(
        statbl_id="A_2024_00050",
        cycle_cd=CYCLE_MONTHLY,
        name_ko="아파트 전세가격지수",
        name_en="Apartment Jeonse Price Index",
        description="전국 및 지역별 아파트 전세가격지수 (기준: 2021.06 = 100)",
    ),
    "apartment_monthly_rent_index": StatisticsTableConfig(
        statbl_id="A_2024_00055",
        cycle_cd=CYCLE_MONTHLY,
        name_ko="아파트 월세가격지수",
        name_en="Apartment Monthly Rent Index",
        description="전국 및 지역별 아파트 월세가격지수",
    ),
    "apartment_sale_price": StatisticsTableConfig(
        statbl_id="A_2024_00060",
        cycle_cd=CYCLE_MONTHLY,
        name_ko="아파트 평균 매매가격",
        name_en="Average Apartment Sale Price",
        description="전국 및 지역별 아파트 평균 매매가격 (만원)",
    ),
    "apartment_rent_price": StatisticsTableConfig(
        statbl_id="A_2024_00065",
        cycle_cd=CYCLE_MONTHLY,
        name_ko="아파트 평균 전세가격",
        name_en="Average Apartment Jeonse Price",
        description="전국 및 지역별 아파트 평균 전세가격 (만원)",
    ),
    "apartment_monthly_rent_price": StatisticsTableConfig(
        statbl_id="A_2024_00070",
        cycle_cd=CYCLE_MONTHLY,
        name_ko="아파트 평균 월세가격",
        name_en="Average Apartment Monthly Rent",
        description="전국 및 지역별 아파트 평균 월세가격 (만원)",
    ),
    "rent_to_deposit_ratio": StatisticsTableConfig(
        statbl_id="A_2024_00075",
        cycle_cd=CYCLE_MONTHLY,
        name_ko="전세가격 대비 월세보증금 비율",
        name_en="Deposit to Jeonse Ratio",
        description="전국 및 지역별 전세가격 대비 월세보증금 비율 (%)",
    ),
    # 서울 지역 세부 통계
    "seoul_sale_index": StatisticsTableConfig(
        statbl_id="A_2024_00080",
        cycle_cd=CYCLE_MONTHLY,
        name_ko="서울 아파트 매매가격지수",
        name_en="Seoul Apartment Sale Index",
        description="서울 지역별 아파트 매매가격지수",
    ),
    "seoul_rent_index": StatisticsTableConfig(
        statbl_id="A_2024_00085",
        cycle_cd=CYCLE_MONTHLY,
        name_ko="서울 아파트 전세가격지수",
        name_en="Seoul Apartment Jeonse Index",
        description="서울 지역별 아파트 전세가격지수",
    ),
    # 연간 토지 통계
    "land_price_index_yearly": StatisticsTableConfig(
        statbl_id="A_2024_00900",
        cycle_cd=CYCLE_YEARLY,
        name_ko="토지가격지수 (연간)",
        name_en="Land Price Index (Yearly)",
        description="전국 및 지역별 토지가격지수 (연간)",
    ),
}

# 서울시 자치구 필터링을 위한 키워드
SEOUL_DISTRICTS = [
    "강남구", "강동구", "강북구", "강서구", "관악구",
    "광진구", "구로구", "금천구", "노원구", "도봉구",
    "동대문구", "동작구", "마포구", "서대문구", "서초구",
    "성동구", "성북구", "송파구", "양천구", "영등포구",
    "용산구", "은평구", "종로구", "중구", "중랑구",
]


@dataclass
class CollectionConfig:
    """데이터 수집 설정."""

    stat_types: list[str] | None = None  # None이면 전체 통계표
    regions: list[str] | None = None  # None이면 전체 지역 (서울 중심)
    start_year_month: str = "202401"  # 시작 연월 (YYYYMM)
    end_year_month: str | None = None  # 종료 연월 (None이면 현재월)
    include_national: bool = True  # 전국 통계 포함 여부
    seoul_only: bool = True  # 서울 지역만 수집 여부
    max_records: int | None = None  # 최대 레코드 수


class REBCollector:
    """
    한국부동산원 R-ONE API 데이터 수집기.

    이 수집기는 다음 기능을 제공합니다:
    1. 아파트 가격지수 (매매/전세/월세) 수집
    2. 아파트 평균 가격 수집
    3. 지역별 세부 통계 수집
    4. 시계열 데이터 수집 (월별/연별)
    """

    def __init__(self, api_key: str | None = None) -> None:
        """
        수집기 초기화.

        Args:
            api_key: R-ONE API 인증키 (None이면 샘플 데이터만 조회 가능, 10건 제한)
        """
        self.api_key = api_key
        self.session: aiohttp.ClientSession | None = None
        self.request_delay = 1.0  # API 호출 간 딜레이 (초)
        self._total_collected = 0

    async def _get_session(self) -> aiohttp.ClientSession:
        """HTTP 세션을 지연 생성."""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=30)
            # 한국부동산원 사이트는 자체 서명 인증서를 사용하므로 SSL 검증 비활성화
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return self.session

    async def close(self) -> None:
        """리소스 정리."""
        if self.session:
            await self.session.close()
            self.session = None

    def _generate_year_months(self, start_ym: str, end_ym: str | None) -> list[str]:
        """시작 연월부터 종료 연월까지의 연월 리스트 생성."""
        if end_ym is None:
            end_ym = datetime.now().strftime("%Y%m")

        year_months = []
        current = datetime.strptime(start_ym, "%Y%m")
        end = datetime.strptime(end_ym, "%Y%m")

        while current <= end:
            year_months.append(current.strftime("%Y%m"))
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

        return year_months

    def _generate_years(self, start_year: int, end_year: int | None) -> list[str]:
        """시작 연도부터 종료 연도까지의 연도 리스트 생성."""
        if end_year is None:
            end_year = datetime.now().year
        return [str(y) for y in range(start_year, end_year + 1)]

    async def _fetch_statistics(
        self,
        statbl_id: str,
        cycle_cd: str,
        time_id: str,
        page_index: int = 1,
        page_size: int = 1000,
    ) -> dict[str, Any]:
        """
        R-ONE API에서 통계 데이터를 조회.

        Args:
            statbl_id: 통계표 ID
            cycle_cd: 데이터 주기 코드
            time_id: 시간 식별자 (YYYYMM 또는 YYYY)
            page_index: 페이지 번호
            page_size: 페이지당 레코드 수

        Returns:
            API 응답 데이터
        """
        session = await self._get_session()

        params = {
            "STATBL_ID": statbl_id,
            "DTACYCLE_CD": cycle_cd,
            "WRTTIME_IDTFR_ID": time_id,
            "Type": "json",
            "pIndex": str(page_index),
            "pSize": str(page_size),
        }

        # 인증키가 있으면 추가
        if self.api_key:
            params["KEY"] = self.api_key

        try:
            async with session.get(REB_API_BASE_URL, params=params) as response:
                if response.status != 200:
                    logger.warning(
                        "R-ONE API 요청 실패: status=%d, statbl_id=%s, time=%s",
                        response.status,
                        statbl_id,
                        time_id,
                    )
                    return {"error": f"HTTP {response.status}"}

                # R-ONE API는 JSON을 text/html Content-Type으로 반환하므로 검증 비활성화
                data = await response.json(content_type=None)
                return data

        except Exception as e:
            logger.error("R-ONE API 요청 오류: %s", e)
            return {"error": str(e)}

    def _parse_response(self, data: dict[str, Any]) -> tuple[list[dict], int]:
        """
        API 응답을 파싱하여 레코드 리스트와 총 개수 반환.

        Args:
            data: API 응답 데이터

        Returns:
            (레코드 리스트, 총 레코드 수)
        """
        if "error" in data:
            return [], 0

        try:
            api_data = data.get("SttsApiTblData", [])
            if not api_data:
                return [], 0

            # head에서 총 개수 추출
            head = api_data[0].get("head", [])
            total_count = head[0].get("list_total_count", 0) if head else 0

            # 결과 코드 확인
            if len(head) > 1:
                result = head[1].get("RESULT", {})
                if result.get("CODE") != "INFO-000":
                    logger.warning(
                        "R-ONE API 오류: %s - %s",
                        result.get("CODE"),
                        result.get("MESSAGE"),
                    )
                    return [], 0

            # row에서 데이터 추출
            rows = api_data[1].get("row", []) if len(api_data) > 1 else []
            return rows, total_count

        except (KeyError, IndexError) as e:
            logger.error("R-ONE API 응답 파싱 오류: %s", e)
            return [], 0

    def _transform_record(
        self,
        row: dict[str, Any],
        table_config: StatisticsTableConfig,
    ) -> dict[str, Any]:
        """
        API 응답 행을 LightRAG 문서 형식으로 변환.

        Args:
            row: API 응답의 개별 행
            table_config: 통계표 설정

        Returns:
            변환된 레코드
        """
        # 지역 정보 파싱 (CLS_FULLNM: "서울>강남구" 형식)
        region_path = row.get("CLS_FULLNM", "")
        region_parts = region_path.split(">") if region_path else []

        sido = region_parts[0] if len(region_parts) > 0 else None
        sigungu = region_parts[1] if len(region_parts) > 1 else None
        dong = region_parts[2] if len(region_parts) > 2 else None

        # 시간 정보 파싱
        time_desc = row.get("WRTTIME_DESC", "")
        time_id = row.get("WRTTIME_IDTFR_ID", "")

        record = {
            "data_source": "REB_RONE",
            "stat_type": table_config.name_en,
            "stat_type_ko": table_config.name_ko,
            "stat_description": table_config.description,
            "statbl_id": row.get("STATBL_ID"),
            "cycle_cd": row.get("DTACYCLE_CD"),
            # 지역 정보
            "region_path": region_path,
            "sido": sido,
            "sigungu": sigungu,
            "dong": dong,
            "region_name": row.get("CLS_NM"),
            # 데이터
            "item_name": row.get("ITM_NM"),
            "item_fullname": row.get("ITM_FULLNM"),
            "value": row.get("DTA_VAL"),
            "unit": row.get("UI_NM"),
            # 시간
            "time_id": time_id,
            "time_desc": time_desc,
            # 메타데이터
            "collected_at": datetime.utcnow().isoformat(),
        }

        return record

    def _is_seoul_region(self, region_path: str) -> bool:
        """지역이 서울인지 확인."""
        if not region_path:
            return False
        if region_path == "전국":
            return False
        if region_path.startswith("서울"):
            return True
        return any(district in region_path for district in SEOUL_DISTRICTS)

    def _is_national(self, region_path: str) -> bool:
        """전국 통계인지 확인."""
        return region_path == "전국"

    async def collect_statistics(
        self,
        table_key: str,
        time_periods: list[str],
        config: CollectionConfig,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        특정 통계표의 데이터를 수집.

        Args:
            table_key: 통계표 키 (STATISTICS_TABLES의 키)
            time_periods: 시간 기간 리스트 (YYYYMM 또는 YYYY)
            config: 수집 설정

        Yields:
            변환된 통계 레코드
        """
        table_config = STATISTICS_TABLES.get(table_key)
        if not table_config:
            logger.error("알 수 없는 통계표: %s", table_key)
            return

        for time_id in time_periods:
            # API 호출
            data = await self._fetch_statistics(
                statbl_id=table_config.statbl_id,
                cycle_cd=table_config.cycle_cd,
                time_id=time_id,
            )

            rows, total_count = self._parse_response(data)

            if not rows:
                logger.debug(
                    "데이터 없음: %s, time=%s",
                    table_config.name_ko,
                    time_id,
                )
                await asyncio.sleep(self.request_delay)
                continue

            logger.info(
                "수집 중: %s [%s] - %d건",
                table_config.name_ko,
                time_id,
                len(rows),
            )

            for row in rows:
                record = self._transform_record(row, table_config)
                region_path = record.get("region_path", "")

                # 지역 필터링
                if config.seoul_only:
                    if not self._is_seoul_region(region_path):
                        if not (config.include_national and self._is_national(region_path)):
                            continue

                yield record
                self._total_collected += 1

                # 최대 레코드 수 체크
                if config.max_records and self._total_collected >= config.max_records:
                    logger.info(
                        "최대 레코드 수(%d)에 도달하여 수집 중단",
                        config.max_records,
                    )
                    return

            # API 요청 간 딜레이
            await asyncio.sleep(self.request_delay)

    async def collect_all_statistics(
        self,
        config: CollectionConfig | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        설정에 따라 모든 통계 데이터를 수집.

        Args:
            config: 수집 설정 (None이면 기본값 사용)

        Yields:
            변환된 통계 레코드
        """
        config = config or CollectionConfig()

        # 수집할 통계표 결정
        if config.stat_types:
            stat_types = [
                st for st in config.stat_types
                if st in STATISTICS_TABLES
            ]
        else:
            # 기본: 주요 통계만 수집
            stat_types = [
                "apartment_sale_index",
                "apartment_rent_index",
                "apartment_sale_price",
                "apartment_rent_price",
            ]

        logger.info(
            "R-ONE 통계 데이터 수집 시작: 통계표=%d개, 서울only=%s",
            len(stat_types),
            config.seoul_only,
        )

        self._total_collected = 0

        for stat_type in stat_types:
            table_config = STATISTICS_TABLES[stat_type]

            # 시간 기간 생성
            if table_config.cycle_cd == CYCLE_YEARLY:
                start_year = int(config.start_year_month[:4])
                end_year = int(config.end_year_month[:4]) if config.end_year_month else None
                time_periods = self._generate_years(start_year, end_year)
            else:
                time_periods = self._generate_year_months(
                    config.start_year_month,
                    config.end_year_month,
                )

            async for record in self.collect_statistics(stat_type, time_periods, config):
                yield record

                if config.max_records and self._total_collected >= config.max_records:
                    return

        logger.info("R-ONE 통계 데이터 수집 완료: 총 %d건", self._total_collected)

    def get_available_statistics(self) -> list[dict[str, str]]:
        """사용 가능한 통계표 목록 반환."""
        return [
            {
                "key": key,
                "name_ko": config.name_ko,
                "name_en": config.name_en,
                "description": config.description,
                "cycle": config.cycle_cd,
            }
            for key, config in STATISTICS_TABLES.items()
        ]


def format_statistics_document(record: dict[str, Any]) -> str:
    """
    통계 레코드를 LightRAG가 이해할 수 있는 자연어 문서로 변환.

    Args:
        record: 통계 레코드

    Returns:
        자연어 문서 문자열
    """
    parts = []

    # 헤더
    stat_type_ko = record.get("stat_type_ko", "부동산 통계")
    parts.append(f"[부동산 시장 통계 - {stat_type_ko}]")

    # 지역 정보
    region_path = record.get("region_path", "")
    if region_path:
        parts.append(f"지역: {region_path.replace('>', ' ')}")

    # 시간 정보
    time_desc = record.get("time_desc", "")
    if time_desc:
        parts.append(f"기준시점: {time_desc}")

    # 데이터 값
    value = record.get("value")
    item_name = record.get("item_name", "")
    unit = record.get("unit", "")

    if value is not None:
        if "지수" in stat_type_ko:
            parts.append(f"{item_name}: {value:.2f} (기준: 2021.06 = 100)")
            # 해석 추가
            if value > 100:
                diff = value - 100
                parts.append(f"의미: 기준시점 대비 {diff:.1f}% 상승")
            elif value < 100:
                diff = 100 - value
                parts.append(f"의미: 기준시점 대비 {diff:.1f}% 하락")
            else:
                parts.append("의미: 기준시점과 동일 수준")
        elif "가격" in stat_type_ko:
            # 만원 단위를 억원 단위로 변환
            if value >= 10000:
                parts.append(f"{item_name}: {value/10000:.2f}억원")
            else:
                parts.append(f"{item_name}: {value:,.0f}만원")
        elif "비율" in stat_type_ko:
            parts.append(f"{item_name}: {value:.1f}%")
        else:
            parts.append(f"{item_name}: {value}")

    # 통계 설명
    description = record.get("stat_description", "")
    if description:
        parts.append(f"설명: {description}")

    # 데이터 출처
    parts.append("데이터 출처: 한국부동산원 R-ONE")

    return "\n".join(parts)
