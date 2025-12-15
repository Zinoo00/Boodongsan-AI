"""
국토교통부(MOLIT) 실거래가 API 수집기.

엔드포인트 구성은 아래 프로젝트 구조를 참고했다:
https://github.com/divetocode/budongsan-api
"""

from __future__ import annotations

import asyncio
import logging
import time
import xml.etree.ElementTree as ET
from collections.abc import AsyncGenerator, Callable
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import aiohttp

from core.config import settings
from data.collectors.sigungu_service import SigunguInfo, SigunguServiceSingleton

logger = logging.getLogger(__name__)

MOLIT_BASE_URL = "http://apis.data.go.kr/1613000"
DEFAULT_PAGE_SIZE = 1000
SUPPORTED_PROPERTY_TYPES = (
    "apartment_trade",  # 아파트 매매
    "apartment_trade_detail",  # 아파트 매매 상세
    "apartment_rent",  # 아파트 전월세
    "multifamily_trade",  # 연립다세대 매매
    "multifamily_rent",  # 연립다세대 전월세
    "officetel_trade",  # 오피스텔 매매
    "officetel_rent",  # 오피스텔 전월세
)


class RealEstateCollector:
    """국토교통부 실거래가 데이터를 비동기 방식으로 수집하는 클래스."""

    def __init__(self) -> None:
        self.session: aiohttp.ClientSession | None = None
        self.service_key = settings.MOLIT_API_KEY
        self.request_delay = 0.5
        self.last_request_time = 0.0

        self._property_handlers: dict[
            str, Callable[[SigunguInfo, str], AsyncGenerator[dict[str, Any], None]]
        ] = {
            "apartment_trade": self._collect_apartment_trade,
            "apartment_trade_detail": self._collect_apartment_trade_detail,
            "apartment_rent": self._collect_apartment_rent,
            "multifamily_trade": self._collect_multifamily_trade,
            "multifamily_rent": self._collect_multifamily_rent,
            "officetel_trade": self._collect_officetel_trade,
            "officetel_rent": self._collect_officetel_rent,
        }

    async def initialize(self) -> None:
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)

    async def close(self) -> None:
        if self.session:
            await self.session.close()
            self.session = None

    async def collect_all_data(
        self,
        year_month: str | None = None,
        districts: list[str] | None = None,
        property_types: list[str] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        await self.initialize()

        try:
            deal_ymd = year_month or datetime.now().strftime("%Y%m")
            property_types = property_types or list(SUPPORTED_PROPERTY_TYPES)

            sigungu_infos = self._resolve_districts(districts)
            total_combinations = len(sigungu_infos) * len(property_types)
            processed = 0

            logger.info(
                "국토교통부 실거래가 수집 시작 - 자치구 수=%s, 유형=%s, 기준월=%s",
                len(sigungu_infos),
                property_types,
                deal_ymd,
            )

            for sigungu_info in sigungu_infos:
                for property_type in property_types:
                    handler = self._property_handlers.get(property_type)
                    if not handler:
                        logger.warning("지원하지 않는 거래 유형: %s", property_type)
                        continue

                    try:
                        async for record in handler(sigungu_info, deal_ymd):
                            yield record
                        processed += 1
                        logger.info(
                            "수집 완료 %s/%s - %s (%s) [%s]",
                            processed,
                            total_combinations,
                            sigungu_info.sigungu_name,
                            sigungu_info.sigungu_code,
                            property_type,
                        )
                    except Exception as exc:
                        logger.exception(
                            "%s 수집 실패 - %s: %s",
                            property_type,
                            sigungu_info.sigungu_name,
                            exc,
                        )

            logger.info("국토교통부 실거래가 수집 종료: %s/%s 성공", processed, total_combinations)
        finally:
            await self.close()

    def get_available_property_types(self) -> list[str]:
        return list(SUPPORTED_PROPERTY_TYPES)

    def get_available_districts(self) -> list[str]:
        return [info.sigungu_name for info in SigunguServiceSingleton.all_sigungu()]

    async def test_connection(self) -> bool:
        await self.initialize()
        try:
            test_sigungu = next(iter(SigunguServiceSingleton.all_sigungu()), None)
            if not test_sigungu:
                logger.error("시군구 정보가 비어 있습니다.")
                return False

            # Test with January 2024 data (known to exist)
            test_month = "202401"
            logger.info("테스트 기준월: %s", test_month)

            # Try with rent data first (as working test uses rent endpoint)
            async for _ in self._iterate_endpoint(
                service="RTMSDataSvcAptRent",
                operation="getRTMSDataSvcAptRent",
                params={"LAWD_CD": "11680", "DEAL_YMD": test_month},
                page_size=10,
            ):
                logger.info("국토교통부 API 연결 테스트 성공 (Rent endpoint)")
                return True
            return False
        finally:
            await self.close()

    def _resolve_districts(self, districts: list[str] | None) -> list[SigunguInfo]:
        if not districts:
            return list(SigunguServiceSingleton.all_sigungu())

        resolved: list[SigunguInfo] = []
        for name in districts:
            info = SigunguServiceSingleton.get_by_name(name)
            if not info:
                logger.warning("알 수 없는 자치구 '%s' → 건너뜀", name)
                continue
            resolved.append(info)
        return resolved

    async def _collect_apartment_trade(
        self,
        sigungu_info: SigunguInfo,
        deal_ymd: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        async for item in self._iterate_endpoint(
            service="RTMSDataSvcAptTrade",
            operation="getRTMSDataSvcAptTrade",
            params={"LAWD_CD": sigungu_info.sigungu_code, "DEAL_YMD": deal_ymd},
        ):
            yield self._transform_trade_record(item, sigungu_info)

    async def _collect_apartment_rent(
        self,
        sigungu_info: SigunguInfo,
        deal_ymd: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        async for item in self._iterate_endpoint(
            service="RTMSDataSvcAptRent",
            operation="getRTMSDataSvcAptRent",
            params={"LAWD_CD": sigungu_info.sigungu_code, "DEAL_YMD": deal_ymd},
        ):
            yield self._transform_rent_record(item, sigungu_info)

    async def _iterate_endpoint(
        self,
        *,
        service: str,
        operation: str,
        params: dict[str, Any],
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> AsyncGenerator[dict[str, Any], None]:
        page = 1
        total_count = None

        while True:
            items, total_count = await self._fetch_endpoint(
                service=service,
                operation=operation,
                params=params,
                page=page,
                page_size=page_size,
            )

            if not items:
                break

            for item in items:
                yield item

            if total_count is None or page * page_size >= total_count:
                break

            page += 1

    async def _fetch_endpoint(
        self,
        *,
        service: str,
        operation: str,
        params: dict[str, Any],
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int | None]:
        await self._rate_limit()

        if not self.session:
            raise RuntimeError("HTTP session is not initialized")

        query_params = {
            "serviceKey": self.service_key,
            "pageNo": str(page),
            "numOfRows": str(page_size),
            **params,
        }

        # Manually construct URL to avoid double-encoding issues with Korean government APIs
        base_url = f"{MOLIT_BASE_URL}/{service}/{operation}"
        query_string = urlencode(query_params, safe="=")
        full_url = f"{base_url}?{query_string}"

        async with self.session.get(full_url) as response:
            text = await response.text()

            if response.status != 200:
                logger.error("국토교통부 API 요청 실패 (HTTP %s)", response.status)
                logger.error("URL: %s", full_url)
                logger.error("Params: %s", query_params)
                logger.error("Response: %s", text[:500])
                return [], None

        # Parse XML response (default format)
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            logger.error("국토교통부 응답 XML 파싱 실패: %s", exc)
            logger.error("Response: %s", text[:500])
            return [], None

        # Check result code
        result_code_elem = root.find(".//resultCode")
        result_msg_elem = root.find(".//resultMsg")

        if result_code_elem is not None:
            result_code = result_code_elem.text
            if result_code not in {"00", "000"}:
                result_msg = (
                    result_msg_elem.text if result_msg_elem is not None else "알 수 없는 오류"
                )
                logger.error("국토교통부 API 오류 (%s): %s", result_code, result_msg)
                return [], None

        # Extract items
        items_elements = root.findall(".//item")
        items = []
        for item_elem in items_elements:
            item_dict = {}
            for child in item_elem:
                item_dict[child.tag] = child.text
            items.append(item_dict)

        # Extract total count
        total_count_elem = root.find(".//totalCount")
        total_count = (
            int(total_count_elem.text)
            if total_count_elem is not None and total_count_elem.text
            else None
        )

        return items, total_count

    async def _rate_limit(self) -> None:
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.request_delay:
            await asyncio.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()

    def _transform_trade_record(self, item: dict[str, Any], sigungu: SigunguInfo) -> dict[str, Any]:
        price = self._parse_price(item.get("dealAmount"))
        area_m2 = self._parse_float(item.get("excluUseAr"))
        transaction_date = self._compose_transaction_date(
            item.get("dealYear"),
            item.get("dealMonth"),
            item.get("dealDay"),
        )

        record = {
            "data_source": "MOLIT",
            "property_type": "아파트",
            "transaction_type": "매매",
            "sigungu": sigungu.sigungu_name,
            "sigungu_code": sigungu.sigungu_code,
            "sido": sigungu.sido_fullname,
            "dong": item.get("umdNm"),
            "building_name": item.get("aptNm"),
            "price": price,
            "deposit": None,
            "monthly_rent": None,
            "area_m2": area_m2,
            "area_pyeong": round(area_m2 / 3.3058, 2) if area_m2 else None,
            "floor": self._parse_int(item.get("floor")),
            "jibun": self._clean_str(item.get("jibun")),
            "building_year": self._parse_int(item.get("buildYear")),
            "transaction_year": self._parse_int(item.get("dealYear")),
            "transaction_month": self._parse_int(item.get("dealMonth")),
            "transaction_day": self._parse_int(item.get("dealDay")),
            "transaction_date": transaction_date,
            "collected_at": datetime.utcnow().isoformat(),
        }

        record["address"] = self._compose_address(record, fallback=item.get("roadNm"))
        record["source_id"] = self._generate_source_id(record)
        return record

    def _transform_rent_record(self, item: dict[str, Any], sigungu: SigunguInfo) -> dict[str, Any]:
        deposit = self._parse_price(item.get("deposit"))
        monthly_rent = self._parse_price(item.get("monthlyRent"))
        transaction_type = "전세" if monthly_rent == 0 else "월세"
        area_m2 = self._parse_float(item.get("excluUseAr"))
        transaction_date = self._compose_transaction_date(
            item.get("dealYear"),
            item.get("dealMonth"),
            item.get("dealDay"),
        )

        record = {
            "data_source": "MOLIT",
            "property_type": "아파트",
            "transaction_type": transaction_type,
            "sigungu": sigungu.sigungu_name,
            "sigungu_code": sigungu.sigungu_code,
            "sido": sigungu.sido_fullname,
            "dong": item.get("umdNm"),
            "building_name": item.get("aptNm"),
            "price": deposit,
            "deposit": deposit,
            "monthly_rent": monthly_rent,
            "area_m2": area_m2,
            "area_pyeong": round(area_m2 / 3.3058, 2) if area_m2 else None,
            "floor": self._parse_int(item.get("floor")),
            "jibun": self._clean_str(item.get("jibun")),
            "building_year": self._parse_int(item.get("buildYear")),
            "transaction_year": self._parse_int(item.get("dealYear")),
            "transaction_month": self._parse_int(item.get("dealMonth")),
            "transaction_day": self._parse_int(item.get("dealDay")),
            "transaction_date": transaction_date,
            "collected_at": datetime.utcnow().isoformat(),
            "contract_type": self._clean_str(item.get("contractType")),
        }

        record["address"] = self._compose_address(record, fallback=item.get("roadNm"))
        record["source_id"] = self._generate_source_id(record)
        return record

    def _compose_transaction_date(
        self,
        year: Any,
        month: Any,
        day: Any,
    ) -> str | None:
        year_int = self._parse_int(year)
        month_int = self._parse_int(month)
        day_int = self._parse_int(day) or 1

        if not (year_int and month_int):
            return None

        try:
            return datetime(year=year_int, month=month_int, day=day_int).isoformat()
        except ValueError:
            return None

    def _compose_address(self, record: dict[str, Any], fallback: str | None = None) -> str:
        parts = [record.get("sido"), record.get("sigungu"), record.get("dong")]
        if record.get("jibun"):
            parts.append(record["jibun"])
        if not any(parts) and fallback:
            return fallback.strip()
        return " ".join(
            filter(
                None,
                (part.strip() if isinstance(part, str) else part for part in parts),
            )
        )

    def _parse_price(self, value: Any) -> int:
        if value in (None, "", " "):
            return 0
        text = str(value).replace(",", "").strip()
        if not text:
            return 0
        try:
            return int(float(text))
        except ValueError:
            return 0

    def _parse_int(self, value: Any) -> int | None:
        if value in (None, "", " "):
            return None
        try:
            return int(str(value).replace(",", "").strip())
        except ValueError:
            return None

    def _parse_float(self, value: Any) -> float | None:
        if value in (None, "", " "):
            return None
        try:
            return float(str(value).replace(",", "").strip())
        except ValueError:
            return None

    def _clean_str(self, value: Any) -> str | None:
        if value in (None, "", " "):
            return None
        return str(value).strip()

    def _generate_source_id(self, record: dict[str, Any]) -> str:
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

    # ========== 아파트 매매 상세 (RTMSDataSvcAptTradeDev) ==========

    async def _collect_apartment_trade_detail(
        self,
        sigungu_info: SigunguInfo,
        deal_ymd: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """아파트 매매 실거래가 상세 데이터 수집."""
        async for item in self._iterate_endpoint(
            service="RTMSDataSvcAptTradeDev",
            operation="getRTMSDataSvcAptTradeDev",
            params={"LAWD_CD": sigungu_info.sigungu_code, "DEAL_YMD": deal_ymd},
        ):
            yield self._transform_apartment_trade_detail_record(item, sigungu_info)

    def _transform_apartment_trade_detail_record(
        self, item: dict[str, Any], sigungu: SigunguInfo
    ) -> dict[str, Any]:
        """아파트 매매 상세 레코드 변환."""
        price = self._parse_price(item.get("dealAmount"))
        area_m2 = self._parse_float(item.get("excluUseAr"))
        transaction_date = self._compose_transaction_date(
            item.get("dealYear"),
            item.get("dealMonth"),
            item.get("dealDay"),
        )

        record = {
            "data_source": "MOLIT_DETAIL",
            "property_type": "아파트",
            "transaction_type": "매매",
            "sigungu": sigungu.sigungu_name,
            "sigungu_code": sigungu.sigungu_code,
            "sido": sigungu.sido_fullname,
            "dong": item.get("umdNm"),
            "building_name": item.get("aptNm"),
            "price": price,
            "deposit": None,
            "monthly_rent": None,
            "area_m2": area_m2,
            "area_pyeong": round(area_m2 / 3.3058, 2) if area_m2 else None,
            "floor": self._parse_int(item.get("floor")),
            "jibun": self._clean_str(item.get("jibun")),
            "building_year": self._parse_int(item.get("buildYear")),
            "transaction_year": self._parse_int(item.get("dealYear")),
            "transaction_month": self._parse_int(item.get("dealMonth")),
            "transaction_day": self._parse_int(item.get("dealDay")),
            "transaction_date": transaction_date,
            # 상세 데이터 추가 필드
            "road_name": self._clean_str(item.get("roadNm")),
            "road_name_bonbun": self._clean_str(item.get("roadNmBonbun")),
            "road_name_bubun": self._clean_str(item.get("roadNmBubun")),
            "apt_seq": self._clean_str(item.get("aptSeq")),
            "deal_type": self._clean_str(item.get("dealingGbn")),  # 중개/직거래
            "buyer_gbn": self._clean_str(item.get("buyerGbn")),  # 매수자 구분
            "rgst_date": self._clean_str(item.get("rgstDate")),  # 등기 일자
            "collected_at": datetime.utcnow().isoformat(),
        }

        record["address"] = self._compose_address(record, fallback=item.get("roadNm"))
        record["source_id"] = self._generate_source_id(record)
        return record

    # ========== 연립다세대 매매 (RTMSDataSvcRHTrade) ==========

    async def _collect_multifamily_trade(
        self,
        sigungu_info: SigunguInfo,
        deal_ymd: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """연립다세대 매매 실거래가 데이터 수집."""
        async for item in self._iterate_endpoint(
            service="RTMSDataSvcRHTrade",
            operation="getRTMSDataSvcRHTrade",
            params={"LAWD_CD": sigungu_info.sigungu_code, "DEAL_YMD": deal_ymd},
        ):
            yield self._transform_multifamily_trade_record(item, sigungu_info)

    def _transform_multifamily_trade_record(
        self, item: dict[str, Any], sigungu: SigunguInfo
    ) -> dict[str, Any]:
        """연립다세대 매매 레코드 변환."""
        price = self._parse_price(item.get("dealAmount"))
        area_m2 = self._parse_float(item.get("excluUseAr"))
        transaction_date = self._compose_transaction_date(
            item.get("dealYear"),
            item.get("dealMonth"),
            item.get("dealDay"),
        )

        record = {
            "data_source": "MOLIT",
            "property_type": "연립다세대",
            "transaction_type": "매매",
            "sigungu": sigungu.sigungu_name,
            "sigungu_code": sigungu.sigungu_code,
            "sido": sigungu.sido_fullname,
            "dong": item.get("umdNm"),
            "building_name": item.get("mhouseNm"),  # 연립다세대명
            "price": price,
            "deposit": None,
            "monthly_rent": None,
            "area_m2": area_m2,
            "area_pyeong": round(area_m2 / 3.3058, 2) if area_m2 else None,
            "floor": self._parse_int(item.get("floor")),
            "jibun": self._clean_str(item.get("jibun")),
            "building_year": self._parse_int(item.get("buildYear")),
            "transaction_year": self._parse_int(item.get("dealYear")),
            "transaction_month": self._parse_int(item.get("dealMonth")),
            "transaction_day": self._parse_int(item.get("dealDay")),
            "transaction_date": transaction_date,
            "land_area": self._parse_float(item.get("slerGbn")),  # 대지권면적
            "collected_at": datetime.utcnow().isoformat(),
        }

        record["address"] = self._compose_address(record)
        record["source_id"] = self._generate_source_id(record)
        return record
        return record

    # ========== 연립다세대 전월세 (RTMSDataSvcRHRent) ==========

    async def _collect_multifamily_rent(
        self,
        sigungu_info: SigunguInfo,
        deal_ymd: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """연립다세대 전월세 실거래가 데이터 수집."""
        async for item in self._iterate_endpoint(
            service="RTMSDataSvcRHRent",
            operation="getRTMSDataSvcRHRent",
            params={"LAWD_CD": sigungu_info.sigungu_code, "DEAL_YMD": deal_ymd},
        ):
            yield self._transform_multifamily_rent_record(item, sigungu_info)

    def _transform_multifamily_rent_record(
        self, item: dict[str, Any], sigungu: SigunguInfo
    ) -> dict[str, Any]:
        """연립다세대 전월세 레코드 변환."""
        deposit = self._parse_price(item.get("deposit"))
        monthly_rent = self._parse_price(item.get("monthlyRent"))
        transaction_type = "전세" if monthly_rent == 0 else "월세"
        area_m2 = self._parse_float(item.get("excluUseAr"))
        transaction_date = self._compose_transaction_date(
            item.get("dealYear"),
            item.get("dealMonth"),
            item.get("dealDay"),
        )

        record = {
            "data_source": "MOLIT",
            "property_type": "연립다세대",
            "transaction_type": transaction_type,
            "sigungu": sigungu.sigungu_name,
            "sigungu_code": sigungu.sigungu_code,
            "sido": sigungu.sido_fullname,
            "dong": item.get("umdNm"),
            "building_name": item.get("mhouseNm"),
            "price": deposit,
            "deposit": deposit,
            "monthly_rent": monthly_rent,
            "area_m2": area_m2,
            "area_pyeong": round(area_m2 / 3.3058, 2) if area_m2 else None,
            "floor": self._parse_int(item.get("floor")),
            "jibun": self._clean_str(item.get("jibun")),
            "building_year": self._parse_int(item.get("buildYear")),
            "transaction_year": self._parse_int(item.get("dealYear")),
            "transaction_month": self._parse_int(item.get("dealMonth")),
            "transaction_day": self._parse_int(item.get("dealDay")),
            "transaction_date": transaction_date,
            "collected_at": datetime.utcnow().isoformat(),
        }

        record["address"] = self._compose_address(record)
        record["source_id"] = self._generate_source_id(record)
        return record
        return record

    # ========== 오피스텔 매매 (RTMSDataSvcOffiTrade) ==========

    async def _collect_officetel_trade(
        self,
        sigungu_info: SigunguInfo,
        deal_ymd: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """오피스텔 매매 실거래가 데이터 수집."""
        async for item in self._iterate_endpoint(
            service="RTMSDataSvcOffiTrade",
            operation="getRTMSDataSvcOffiTrade",
            params={"LAWD_CD": sigungu_info.sigungu_code, "DEAL_YMD": deal_ymd},
        ):
            yield self._transform_officetel_trade_record(item, sigungu_info)

    def _transform_officetel_trade_record(
        self, item: dict[str, Any], sigungu: SigunguInfo
    ) -> dict[str, Any]:
        """오피스텔 매매 레코드 변환."""
        price = self._parse_price(item.get("dealAmount"))
        area_m2 = self._parse_float(item.get("excluUseAr"))
        transaction_date = self._compose_transaction_date(
            item.get("dealYear"),
            item.get("dealMonth"),
            item.get("dealDay"),
        )

        record = {
            "data_source": "MOLIT",
            "property_type": "오피스텔",
            "transaction_type": "매매",
            "sigungu": sigungu.sigungu_name,
            "sigungu_code": sigungu.sigungu_code,
            "sido": sigungu.sido_fullname,
            "dong": item.get("umdNm"),
            "building_name": item.get("offiNm"),  # 오피스텔명
            "price": price,
            "deposit": None,
            "monthly_rent": None,
            "area_m2": area_m2,
            "area_pyeong": round(area_m2 / 3.3058, 2) if area_m2 else None,
            "floor": self._parse_int(item.get("floor")),
            "jibun": self._clean_str(item.get("jibun")),
            "building_year": self._parse_int(item.get("buildYear")),
            "transaction_year": self._parse_int(item.get("dealYear")),
            "transaction_month": self._parse_int(item.get("dealMonth")),
            "transaction_day": self._parse_int(item.get("dealDay")),
            "transaction_date": transaction_date,
            "collected_at": datetime.utcnow().isoformat(),
        }

        record["address"] = self._compose_address(record)
        record["source_id"] = self._generate_source_id(record)
        return record
        return record

    # ========== 오피스텔 전월세 (RTMSDataSvcOffiRent) ==========

    async def _collect_officetel_rent(
        self,
        sigungu_info: SigunguInfo,
        deal_ymd: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """오피스텔 전월세 실거래가 데이터 수집."""
        async for item in self._iterate_endpoint(
            service="RTMSDataSvcOffiRent",
            operation="getRTMSDataSvcOffiRent",
            params={"LAWD_CD": sigungu_info.sigungu_code, "DEAL_YMD": deal_ymd},
        ):
            yield self._transform_officetel_rent_record(item, sigungu_info)

    def _transform_officetel_rent_record(
        self, item: dict[str, Any], sigungu: SigunguInfo
    ) -> dict[str, Any]:
        """오피스텔 전월세 레코드 변환."""
        deposit = self._parse_price(item.get("deposit"))
        monthly_rent = self._parse_price(item.get("monthlyRent"))
        transaction_type = "전세" if monthly_rent == 0 else "월세"
        area_m2 = self._parse_float(item.get("excluUseAr"))
        transaction_date = self._compose_transaction_date(
            item.get("dealYear"),
            item.get("dealMonth"),
            item.get("dealDay"),
        )

        record = {
            "data_source": "MOLIT",
            "property_type": "오피스텔",
            "transaction_type": transaction_type,
            "sigungu": sigungu.sigungu_name,
            "sigungu_code": sigungu.sigungu_code,
            "sido": sigungu.sido_fullname,
            "dong": item.get("umdNm"),
            "building_name": item.get("offiNm"),
            "price": deposit,
            "deposit": deposit,
            "monthly_rent": monthly_rent,
            "area_m2": area_m2,
            "area_pyeong": round(area_m2 / 3.3058, 2) if area_m2 else None,
            "floor": self._parse_int(item.get("floor")),
            "jibun": self._clean_str(item.get("jibun")),
            "building_year": self._parse_int(item.get("buildYear")),
            "transaction_year": self._parse_int(item.get("dealYear")),
            "transaction_month": self._parse_int(item.get("dealMonth")),
            "transaction_day": self._parse_int(item.get("dealDay")),
            "transaction_date": transaction_date,
            "collected_at": datetime.utcnow().isoformat(),
        }

        record["address"] = self._compose_address(record)
        record["source_id"] = self._generate_source_id(record)
        return record
