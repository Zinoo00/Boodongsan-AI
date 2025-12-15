"""
PublicDataReader 기반 포괄적 실거래가 데이터 수집기.

PublicDataReader 라이브러리를 사용하여 국토교통부 실거래가 API에서
서울시 전체 25개 자치구의 모든 부동산 유형 데이터를 수집합니다.

지원 부동산 유형:
- 아파트 (매매/전월세)
- 오피스텔 (매매/전월세)
- 연립다세대 (매매/전월세)
- 단독다가구 (매매/전월세)

Usage:
    from data.collectors.pdr_collector import PublicDataReaderCollector

    collector = PublicDataReaderCollector(service_key="YOUR_API_KEY")
    async for record in collector.collect_all_data():
        print(record)
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from core.config import settings

logger = logging.getLogger(__name__)

# 서울시 25개 자치구 코드 (5자리 시군구 코드)
SEOUL_DISTRICTS: dict[str, str] = {
    "11110": "종로구",
    "11140": "중구",
    "11170": "용산구",
    "11200": "성동구",
    "11215": "광진구",
    "11230": "동대문구",
    "11260": "중랑구",
    "11290": "성북구",
    "11305": "강북구",
    "11320": "도봉구",
    "11350": "노원구",
    "11380": "은평구",
    "11410": "서대문구",
    "11440": "마포구",
    "11470": "양천구",
    "11500": "강서구",
    "11530": "구로구",
    "11545": "금천구",
    "11560": "영등포구",
    "11590": "동작구",
    "11620": "관악구",
    "11650": "서초구",
    "11680": "강남구",
    "11710": "송파구",
    "11740": "강동구",
}

# 역방향 매핑 (구 이름 -> 코드)
DISTRICT_NAME_TO_CODE: dict[str, str] = {v: k for k, v in SEOUL_DISTRICTS.items()}

# 부동산 유형별 API 메서드 매핑
# PublicDataReader.TransactionPrice 클래스의 메서드명
PROPERTY_METHOD_MAP: dict[tuple[str, str], str] = {
    # 아파트
    ("아파트", "매매"): "get_data",  # 아파트 매매
    ("아파트", "전월세"): "get_data",  # 아파트 전월세
    # 오피스텔
    ("오피스텔", "매매"): "get_data",  # 오피스텔 매매
    ("오피스텔", "전월세"): "get_data",  # 오피스텔 전월세
    # 연립다세대
    ("연립다세대", "매매"): "get_data",  # 연립다세대 매매
    ("연립다세대", "전월세"): "get_data",  # 연립다세대 전월세
    # 단독다가구
    ("단독다가구", "매매"): "get_data",  # 단독다가구 매매
    ("단독다가구", "전월세"): "get_data",  # 단독다가구 전월세
}

# PublicDataReader property_type 파라미터 매핑
PDR_PROPERTY_TYPES: dict[str, str] = {
    "아파트": "아파트",
    "오피스텔": "오피스텔",
    "연립다세대": "연립다세대",
    "단독다가구": "단독다가구",
}

# PublicDataReader trade_type 파라미터 매핑
PDR_TRADE_TYPES: dict[str, str] = {
    "매매": "매매",
    "전월세": "전월세",
}


@dataclass
class CollectionConfig:
    """데이터 수집 설정."""

    districts: list[str] | None = None  # None이면 전체 서울시
    property_types: list[str] | None = None  # None이면 전체 유형
    trade_types: list[str] | None = None  # None이면 매매+전월세
    start_year_month: str = "202401"  # 시작 연월 (YYYYMM)
    end_year_month: str | None = None  # 종료 연월 (None이면 현재월)
    max_records: int | None = None  # 최대 레코드 수


class PublicDataReaderCollector:
    """
    PublicDataReader를 사용한 포괄적 실거래가 데이터 수집기.

    이 수집기는 다음 기능을 제공합니다:
    1. 서울시 전체 25개 자치구 데이터 수집
    2. 4개 부동산 유형 (아파트, 오피스텔, 연립다세대, 단독다가구)
    3. 2개 거래 유형 (매매, 전월세)
    4. 지정 기간 동안의 월별 데이터 수집
    """

    def __init__(self, service_key: str | None = None) -> None:
        """
        수집기 초기화.

        Args:
            service_key: 공공데이터포털 API 서비스 키 (None이면 환경변수 사용)
        """
        self.service_key = service_key or settings.MOLIT_API_KEY
        self._api = None
        self._executor = ThreadPoolExecutor(max_workers=2)
        self.request_delay = 1.0  # API 호출 간 딜레이 (초)
        self._total_collected = 0

    def _get_api(self):
        """PublicDataReader API 인스턴스를 지연 로딩."""
        if self._api is None:
            try:
                from PublicDataReader import TransactionPrice
                self._api = TransactionPrice(self.service_key)
            except ImportError as e:
                logger.error("PublicDataReader 라이브러리가 설치되지 않았습니다: %s", e)
                raise
        return self._api

    def _generate_year_months(self, start_ym: str, end_ym: str | None) -> list[str]:
        """시작 연월부터 종료 연월까지의 연월 리스트 생성."""
        if end_ym is None:
            end_ym = datetime.now().strftime("%Y%m")

        year_months = []
        current = datetime.strptime(start_ym, "%Y%m")
        end = datetime.strptime(end_ym, "%Y%m")

        while current <= end:
            year_months.append(current.strftime("%Y%m"))
            # 다음 달로 이동
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

        return year_months

    def _fetch_data_sync(
        self,
        sigungu_code: str,
        year_month: str,
        property_type: str,
        trade_type: str,
    ) -> pd.DataFrame | None:
        """
        동기 방식으로 API 데이터를 가져옴 (ThreadPoolExecutor에서 실행).

        PublicDataReader는 동기 라이브러리이므로 별도 스레드에서 실행합니다.
        """
        try:
            api = self._get_api()

            # PublicDataReader의 get_data 메서드 호출
            # property_type: "아파트", "오피스텔", "연립다세대", "단독다가구"
            # trade_type: "매매", "전월세"
            df = api.get_data(
                property_type=property_type,
                trade_type=trade_type,
                sigungu_code=sigungu_code,
                year_month=year_month,
            )

            if df is None or df.empty:
                return None

            return df

        except Exception as e:
            logger.warning(
                "데이터 수집 실패 - 코드=%s, 월=%s, 유형=%s/%s: %s",
                sigungu_code, year_month, property_type, trade_type, e
            )
            return None

    async def _fetch_data_async(
        self,
        sigungu_code: str,
        year_month: str,
        property_type: str,
        trade_type: str,
    ) -> pd.DataFrame | None:
        """비동기 래퍼 - ThreadPoolExecutor에서 동기 함수 실행."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._fetch_data_sync,
            sigungu_code,
            year_month,
            property_type,
            trade_type,
        )

    def _transform_record(
        self,
        row: pd.Series,
        sigungu_code: str,
        property_type: str,
        trade_type: str,
    ) -> dict[str, Any]:
        """DataFrame 행을 LightRAG 문서 형식으로 변환."""
        sigungu_name = SEOUL_DISTRICTS.get(sigungu_code, "알수없음")

        # 공통 필드 추출 (PublicDataReader 컬럼명 기준)
        record: dict[str, Any] = {
            "data_source": "MOLIT_PDR",
            "property_type": property_type,
            "transaction_type": self._determine_transaction_type(row, trade_type),
            "sigungu": sigungu_name,
            "sigungu_code": sigungu_code,
            "sido": "서울특별시",
        }

        # 지역 정보
        record["dong"] = self._safe_get(row, ["법정동", "동"])
        record["jibun"] = self._safe_get(row, ["지번", "번지"])

        # 건물 정보
        record["building_name"] = self._safe_get(row, ["아파트", "단지명", "건물명", "연립다세대"])

        # 면적 정보
        area_m2 = self._safe_float(row, ["전용면적", "전용면적(㎡)", "계약면적"])
        record["area_m2"] = area_m2
        record["area_pyeong"] = round(area_m2 / 3.3058, 2) if area_m2 else None

        # 층수 및 건축년도
        record["floor"] = self._safe_int(row, ["층", "계약층"])
        record["building_year"] = self._safe_int(row, ["건축년도", "건축연도"])

        # 가격 정보 (거래 유형에 따라 다름)
        if trade_type == "매매":
            price = self._safe_price(row, ["거래금액", "거래금액(만원)"])
            record["price"] = price
            record["deposit"] = None
            record["monthly_rent"] = None
        else:  # 전월세
            deposit = self._safe_price(row, ["보증금", "보증금액", "보증금(만원)"])
            monthly_rent = self._safe_price(row, ["월세", "월세금액", "월세(만원)"])
            record["price"] = deposit  # 주요 가격은 보증금
            record["deposit"] = deposit
            record["monthly_rent"] = monthly_rent

        # 거래 날짜
        year = self._safe_int(row, ["년", "계약년도"])
        month = self._safe_int(row, ["월", "계약월"])
        day = self._safe_int(row, ["일", "계약일"])

        record["transaction_year"] = year
        record["transaction_month"] = month
        record["transaction_day"] = day
        record["transaction_date"] = self._compose_date(year, month, day)

        # 주소 구성
        record["address"] = self._compose_address(record)

        # 소스 ID 생성
        record["source_id"] = self._generate_source_id(record)

        # 수집 시간
        record["collected_at"] = datetime.utcnow().isoformat()

        return record

    def _determine_transaction_type(self, row: pd.Series, trade_type: str) -> str:
        """거래 유형 결정 (전월세의 경우 전세/월세 구분)."""
        if trade_type == "매매":
            return "매매"

        # 전월세의 경우 월세가 0이면 전세
        monthly_rent = self._safe_price(row, ["월세", "월세금액", "월세(만원)"])
        if monthly_rent == 0:
            return "전세"
        return "월세"

    def _safe_get(self, row: pd.Series, keys: list[str]) -> str | None:
        """여러 키 중 존재하는 값을 안전하게 가져옴."""
        for key in keys:
            if key in row.index:
                val = row[key]
                if pd.notna(val) and str(val).strip():
                    return str(val).strip()
        return None

    def _safe_int(self, row: pd.Series, keys: list[str]) -> int | None:
        """여러 키 중 존재하는 정수 값을 안전하게 가져옴."""
        for key in keys:
            if key in row.index:
                val = row[key]
                if pd.notna(val):
                    try:
                        return int(float(str(val).replace(",", "").strip()))
                    except (ValueError, TypeError):
                        continue
        return None

    def _safe_float(self, row: pd.Series, keys: list[str]) -> float | None:
        """여러 키 중 존재하는 실수 값을 안전하게 가져옴."""
        for key in keys:
            if key in row.index:
                val = row[key]
                if pd.notna(val):
                    try:
                        return float(str(val).replace(",", "").strip())
                    except (ValueError, TypeError):
                        continue
        return None

    def _safe_price(self, row: pd.Series, keys: list[str]) -> int:
        """가격 값을 안전하게 가져옴 (만원 단위)."""
        val = self._safe_int(row, keys)
        return val if val is not None else 0

    def _compose_date(self, year: int | None, month: int | None, day: int | None) -> str | None:
        """연, 월, 일을 ISO 날짜 문자열로 조합."""
        if not year or not month:
            return None
        day = day or 1
        try:
            return datetime(year=year, month=month, day=day).isoformat()
        except ValueError:
            return None

    def _compose_address(self, record: dict[str, Any]) -> str:
        """주소 문자열 구성."""
        parts = [
            record.get("sido"),
            record.get("sigungu"),
            record.get("dong"),
        ]
        if record.get("jibun"):
            parts.append(record["jibun"])
        return " ".join(filter(None, parts))

    def _generate_source_id(self, record: dict[str, Any]) -> str:
        """고유 소스 ID 생성."""
        import hashlib

        key_fields = [
            record.get("address", ""),
            str(record.get("price", "")),
            str(record.get("area_m2", "")),
            record.get("transaction_date", "") or "",
            record.get("property_type", ""),
            record.get("transaction_type", ""),
        ]

        return hashlib.md5("|".join(key_fields).encode("utf-8")).hexdigest()

    async def collect_all_data(
        self,
        config: CollectionConfig | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        설정에 따라 모든 데이터를 수집.

        Args:
            config: 수집 설정 (None이면 기본값 사용)

        Yields:
            변환된 거래 기록 딕셔너리
        """
        config = config or CollectionConfig()

        # 자치구 리스트 결정
        if config.districts:
            sigungu_codes = [
                DISTRICT_NAME_TO_CODE[d] for d in config.districts
                if d in DISTRICT_NAME_TO_CODE
            ]
        else:
            sigungu_codes = list(SEOUL_DISTRICTS.keys())

        # 부동산 유형 리스트 결정
        property_types = config.property_types or list(PDR_PROPERTY_TYPES.keys())

        # 거래 유형 리스트 결정
        trade_types = config.trade_types or list(PDR_TRADE_TYPES.keys())

        # 연월 리스트 생성
        year_months = self._generate_year_months(
            config.start_year_month,
            config.end_year_month,
        )

        # 총 조합 수 계산
        total_combinations = (
            len(sigungu_codes) * len(property_types) *
            len(trade_types) * len(year_months)
        )

        logger.info(
            "PublicDataReader 데이터 수집 시작: "
            "자치구=%d개, 유형=%d개, 거래=%d개, 월=%d개, 총조합=%d",
            len(sigungu_codes),
            len(property_types),
            len(trade_types),
            len(year_months),
            total_combinations,
        )

        processed = 0
        self._total_collected = 0

        for sigungu_code in sigungu_codes:
            sigungu_name = SEOUL_DISTRICTS[sigungu_code]

            for property_type in property_types:
                for trade_type in trade_types:
                    for year_month in year_months:
                        # 진행률 로깅
                        processed += 1
                        if processed % 10 == 0:
                            logger.info(
                                "진행 중: %d/%d (%.1f%%) - 수집된 레코드: %d",
                                processed,
                                total_combinations,
                                processed / total_combinations * 100,
                                self._total_collected,
                            )

                        # API 호출
                        df = await self._fetch_data_async(
                            sigungu_code,
                            year_month,
                            property_type,
                            trade_type,
                        )

                        if df is None or df.empty:
                            continue

                        # 각 행을 변환하여 yield
                        for _, row in df.iterrows():
                            record = self._transform_record(
                                row,
                                sigungu_code,
                                property_type,
                                trade_type,
                            )
                            self._total_collected += 1
                            yield record

                            # 최대 레코드 수 체크
                            if config.max_records and self._total_collected >= config.max_records:
                                logger.info(
                                    "최대 레코드 수(%d)에 도달하여 수집 중단",
                                    config.max_records,
                                )
                                return

                        # API 요청 간 딜레이
                        await asyncio.sleep(self.request_delay)

        logger.info(
            "PublicDataReader 데이터 수집 완료: 총 %d개 레코드",
            self._total_collected,
        )

    async def collect_by_district(
        self,
        district_name: str,
        property_types: list[str] | None = None,
        trade_types: list[str] | None = None,
        start_year_month: str = "202401",
        end_year_month: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """특정 자치구의 데이터만 수집."""
        config = CollectionConfig(
            districts=[district_name],
            property_types=property_types,
            trade_types=trade_types,
            start_year_month=start_year_month,
            end_year_month=end_year_month,
        )
        async for record in self.collect_all_data(config):
            yield record

    def get_available_districts(self) -> list[str]:
        """사용 가능한 자치구 목록 반환."""
        return list(SEOUL_DISTRICTS.values())

    def get_available_property_types(self) -> list[str]:
        """사용 가능한 부동산 유형 목록 반환."""
        return list(PDR_PROPERTY_TYPES.keys())

    def get_available_trade_types(self) -> list[str]:
        """사용 가능한 거래 유형 목록 반환."""
        return list(PDR_TRADE_TYPES.keys())

    def close(self) -> None:
        """리소스 정리."""
        self._executor.shutdown(wait=False)
        self._api = None
