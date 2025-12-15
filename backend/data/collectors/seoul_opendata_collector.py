"""
서울 열린 데이터 광장 API 컬렉터.

서울시 부동산, 정비사업, 교통, 용도지역 등 공공데이터를 수집합니다.

API 기본 URL: http://openapi.seoul.go.kr:8088/{인증키}/{타입}/{서비스명}/{시작위치}/{끝위치}/
API 문서: https://data.seoul.go.kr
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator

import httpx

logger = logging.getLogger(__name__)


class DataCategory(str, Enum):
    """데이터 카테고리."""

    REAL_ESTATE = "real_estate"  # 부동산 가격/거래
    REDEVELOPMENT = "redevelopment"  # 정비사업/재개발
    TRANSPORT = "transport"  # 교통/인프라
    LAND_USE = "land_use"  # 용도지역/공간정보
    POPULATION = "population"  # 인구/생활
    AGENCY = "agency"  # 중개업소


@dataclass
class SeoulOpenDataService:
    """서울 열린 데이터 서비스 정의."""

    service_name: str  # API 서비스명
    description: str  # 설명
    data_code: str  # 데이터셋 ID (OA-XXXXX)
    category: DataCategory  # 카테고리
    update_frequency: str  # 갱신 주기 (daily, monthly, yearly, as_needed)
    key_fields: list[str]  # 주요 필드


# ============================================================
# 서울 열린 데이터 광장 API 서비스 정의
# ============================================================

SEOUL_SERVICES: dict[str, SeoulOpenDataService] = {
    # ========== 부동산 가격/거래 데이터 ==========
    "real_transaction": SeoulOpenDataService(
        service_name="tbLnOpendataRtmsRent",
        description="부동산 실거래가 정보",
        data_code="OA-21275",
        category=DataCategory.REAL_ESTATE,
        update_frequency="daily",
        key_fields=["자치구", "법정동", "신고년도", "건물면적", "물건금액", "건축년도"],
    ),
    "rent_price": SeoulOpenDataService(
        service_name="tbLnOpendataRtmsRentV",
        description="부동산 전월세가 정보",
        data_code="OA-21276",
        category=DataCategory.REAL_ESTATE,
        update_frequency="daily",
        key_fields=["자치구", "법정동", "전월세구분", "보증금", "임대료", "계약년도"],
    ),
    "apartment_trade": SeoulOpenDataService(
        service_name="tbLnOpendataRtmsAptTrade",
        description="공동주택 아파트 정보",
        data_code="OA-15818",
        category=DataCategory.REAL_ESTATE,
        update_frequency="monthly",
        key_fields=["자치구", "법정동", "아파트", "전용면적", "거래금액"],
    ),
    "land_price": SeoulOpenDataService(
        service_name="IndvdLandPrice",
        description="개별공시지가 정보",
        data_code="OA-1180",
        category=DataCategory.REAL_ESTATE,
        update_frequency="yearly",
        key_fields=["자치구", "법정동", "지목", "공시지가"],
    ),
    # ========== 정비사업/재개발 데이터 ==========
    "urban_planning": SeoulOpenDataService(
        service_name="tbLnOpendataUpis",
        description="도시계획 정비사업 현황",
        data_code="OA-20281",
        category=DataCategory.REDEVELOPMENT,
        update_frequency="daily",
        key_fields=["정비구역명", "사업유형", "추진단계", "면적"],
    ),
    "redevelopment_legacy": SeoulOpenDataService(
        service_name="upisRebuild",
        description="정비사업 현황 (레거시)",
        data_code="OA-20281",
        category=DataCategory.REDEVELOPMENT,
        update_frequency="daily",
        key_fields=["PRJC_CD", "RGN_NM", "SCLSF", "AREA_CHG_AFTR"],
    ),
    "cleanup_biz": SeoulOpenDataService(
        service_name="CleanupBizInfo",
        description="재개발 재건축 정비사업 현황",
        data_code="OA-2253",
        category=DataCategory.REDEVELOPMENT,
        update_frequency="monthly",
        key_fields=["사업구분", "구역명", "추진단계", "사업면적"],
    ),
    "district_plan": SeoulOpenDataService(
        service_name="tbLnOpendataUpisUnit",
        description="지구단위계획 정보",
        data_code="OA-20280",
        category=DataCategory.REDEVELOPMENT,
        update_frequency="daily",
        key_fields=["지구명", "지구유형", "면적"],
    ),
    "decision_notice": SeoulOpenDataService(
        service_name="tbLnOpendataUpisDcsn",
        description="도시계획 결정고시 정보",
        data_code="OA-20283",
        category=DataCategory.REDEVELOPMENT,
        update_frequency="daily",
        key_fields=["고시명", "고시일자", "고시내용"],
    ),
    "renewal_promotion": SeoulOpenDataService(
        service_name="tbLnOpendataRhb",
        description="재정비 촉진 사업 현황",
        data_code="OA-20286",
        category=DataCategory.REDEVELOPMENT,
        update_frequency="daily",
        key_fields=["촉진지구명", "사업유형", "면적"],
    ),
    "urban_development": SeoulOpenDataService(
        service_name="tbLnOpendataDevl",
        description="도시 개발사업 현황",
        data_code="OA-20287",
        category=DataCategory.REDEVELOPMENT,
        update_frequency="daily",
        key_fields=["사업명", "사업유형", "면적", "추진단계"],
    ),
    # ========== 교통/인프라 데이터 ==========
    "subway_station": SeoulOpenDataService(
        service_name="SearchSTNBySubwayLineInfo",
        description="지하철역 정보 (역코드로 위치 조회)",
        data_code="OA-121",
        category=DataCategory.TRANSPORT,
        update_frequency="as_needed",
        key_fields=["STATION_CD", "STATION_NM", "LINE_NUM", "FR_CODE"],
    ),
    "subway_address": SeoulOpenDataService(
        service_name="SearchADDRBySubwayInfo",
        description="지하철역 주소 및 전화번호",
        data_code="OA-118",
        category=DataCategory.TRANSPORT,
        update_frequency="as_needed",
        key_fields=["STATION_NM", "ADDRESS", "TEL"],
    ),
    "bus_stop": SeoulOpenDataService(
        service_name="busStopLocationXyInfo",
        description="버스정류소 위치정보",
        data_code="OA-15067",
        category=DataCategory.TRANSPORT,
        update_frequency="monthly",
        key_fields=["STOP_NO", "STOP_NM", "XCODE", "YCODE"],
    ),
    # ========== 용도지역/공간정보 데이터 ==========
    "land_use_zone": SeoulOpenDataService(
        service_name="tbLnSgguLanduse",
        description="용도지역(도시지역) 공간정보",
        data_code="OA-21136",
        category=DataCategory.LAND_USE,
        update_frequency="daily",
        key_fields=["용도지역명", "면적"],
    ),
    "district_unit_zone": SeoulOpenDataService(
        service_name="tbLnSgguDistrictUnit",
        description="지구단위계획구역 공간정보",
        data_code="OA-21161",
        category=DataCategory.LAND_USE,
        update_frequency="daily",
        key_fields=["지구명", "지구유형", "면적"],
    ),
    "greenbelt": SeoulOpenDataService(
        service_name="tbLnSgguGrn",
        description="개발제한구역 공간정보",
        data_code="OA-21123",
        category=DataCategory.LAND_USE,
        update_frequency="daily",
        key_fields=["구역명", "면적"],
    ),
    # ========== 인구/생활 데이터 ==========
    "living_population": SeoulOpenDataService(
        service_name="SPOP_DAILYSUM_JACHI",
        description="서울 생활인구 (일별)",
        data_code="N/A",
        category=DataCategory.POPULATION,
        update_frequency="daily",
        key_fields=["기준일", "자치구", "총생활인구"],
    ),
    # ========== 중개업소 데이터 ==========
    "real_estate_agency": SeoulOpenDataService(
        service_name="landBizInfo",
        description="부동산 중개업소 정보",
        data_code="OA-15550",
        category=DataCategory.AGENCY,
        update_frequency="as_needed",
        key_fields=["업소명", "주소", "대표자", "등록번호"],
    ),
}


# 정비사업 유형 매핑
REDEVELOPMENT_TYPE_MAP = {
    "재개발": "urban_redevelopment",
    "재건축": "reconstruction",
    "도시환경정비": "urban_environment",
    "주거환경개선": "residential_improvement",
    "가로주택정비": "street_housing",
    "소규모재건축": "small_scale_reconstruction",
}

# 정비사업 단계 매핑
PROJECT_STAGE_MAP = {
    "정비구역지정": "zone_designation",
    "조합설립추진위원회승인": "promotion_committee",
    "조합설립인가": "association_establishment",
    "사업시행인가": "project_implementation",
    "관리처분인가": "disposal_authorization",
    "착공": "construction_start",
    "준공": "completion",
}


class SeoulOpenDataCollector:
    """
    서울 열린 데이터 광장 API 컬렉터.

    API 기본 URL: http://openapi.seoul.go.kr:8088/{인증키}/{타입}/{서비스명}/{시작위치}/{끝위치}/

    주요 데이터셋:
    - 부동산 실거래가 (OA-21275): 매매 실거래가
    - 부동산 전월세가 (OA-21276): 전월세 실거래가
    - 개별공시지가 (OA-1180): 토지 공시가격
    - 정비사업 현황 (OA-20281): 재개발/재건축 등
    - 지하철역 정보 (OA-121): 역 위치 및 노선
    - 버스정류소 (OA-15067): 정류소 위치
    - 용도지역 (OA-21136): 도시지역 용도
    """

    BASE_URL = "http://openapi.seoul.go.kr:8088"
    DEFAULT_BATCH_SIZE = 1000
    DEFAULT_RATE_LIMIT_DELAY = 0.3  # 초

    def __init__(self, api_key: str | None = None):
        """
        컬렉터 초기화.

        Args:
            api_key: 서울 열린 데이터 광장 API 키
        """
        from core.config import settings

        self.api_key = api_key or getattr(settings, "SEOUL_OPEN_API_KEY", None)
        if not self.api_key:
            logger.warning("SEOUL_OPEN_API_KEY가 설정되지 않았습니다")

        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """HTTP 클라이언트 반환."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """HTTP 클라이언트 종료."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def get_available_services(
        self, category: DataCategory | None = None
    ) -> dict[str, SeoulOpenDataService]:
        """
        사용 가능한 서비스 목록 반환.

        Args:
            category: 필터링할 카테고리 (None이면 전체)

        Returns:
            서비스 정의 딕셔너리
        """
        if category is None:
            return SEOUL_SERVICES.copy()
        return {k: v for k, v in SEOUL_SERVICES.items() if v.category == category}

    async def test_connection(self, service_key: str = "redevelopment_legacy") -> bool:
        """
        API 연결 테스트.

        Args:
            service_key: 테스트할 서비스 키

        Returns:
            연결 성공 여부
        """
        if not self.api_key:
            logger.error("API 키가 설정되지 않았습니다")
            return False

        service = SEOUL_SERVICES.get(service_key)
        if not service:
            logger.error(f"알 수 없는 서비스: {service_key}")
            return False

        client = await self._get_client()
        url = f"{self.BASE_URL}/{self.api_key}/json/{service.service_name}/1/1/"

        try:
            response = await client.get(url)
            data = response.json()

            # 오류 응답 체크
            if "RESULT" in data:
                code = data["RESULT"].get("CODE", "")
                message = data["RESULT"].get("MESSAGE", "")
                logger.warning(f"API 오류: {code} - {message}")
                return False

            logger.info(f"API 연결 성공: {service.service_name}")
            return True

        except Exception as e:
            logger.error(f"API 연결 실패: {e}")
            return False

    async def _fetch_data(
        self,
        service_name: str,
        start_index: int,
        end_index: int,
    ) -> dict[str, Any] | None:
        """
        API에서 데이터 조회.

        Args:
            service_name: API 서비스명
            start_index: 시작 인덱스 (1부터)
            end_index: 종료 인덱스

        Returns:
            API 응답 데이터 또는 None
        """
        if not self.api_key:
            logger.error("API 키가 설정되지 않았습니다")
            return None

        client = await self._get_client()
        url = f"{self.BASE_URL}/{self.api_key}/json/{service_name}/{start_index}/{end_index}/"

        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            # 오류 응답 체크
            if "RESULT" in data:
                code = data["RESULT"].get("CODE", "")
                message = data["RESULT"].get("MESSAGE", "")
                # INFO-000: 해당 데이터 없음 (정상 종료)
                if code == "INFO-000":
                    return None
                logger.warning(f"API 오류 ({service_name}): {code} - {message}")
                return None

            return data

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP 오류: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"데이터 조회 실패: {e}")
            return None

    def _extract_records(
        self, data: dict[str, Any], service_name: str
    ) -> tuple[list[dict[str, Any]], int]:
        """
        API 응답에서 레코드 추출.

        Args:
            data: API 응답 데이터
            service_name: 서비스명

        Returns:
            (레코드 리스트, 전체 레코드 수)
        """
        # 데이터 키 찾기 (서비스명에 따라 다름)
        for key in data.keys():
            if key != "RESULT" and isinstance(data[key], dict):
                if "row" in data[key]:
                    service_data = data[key]
                    records = service_data.get("row", [])
                    total_count = service_data.get("list_total_count", 0)
                    return records, total_count

        logger.warning(f"데이터 키를 찾을 수 없음: {list(data.keys())}")
        return [], 0

    async def collect_data(
        self,
        service_key: str,
        max_records: int | None = None,
        batch_size: int | None = None,
        transform: bool = True,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        데이터 수집 (범용 메서드).

        Args:
            service_key: 서비스 키 (SEOUL_SERVICES의 키)
            max_records: 최대 레코드 수
            batch_size: 배치당 요청 레코드 수
            transform: 데이터 변환 여부

        Yields:
            수집된 레코드
        """
        service = SEOUL_SERVICES.get(service_key)
        if not service:
            logger.error(f"알 수 없는 서비스: {service_key}")
            return

        batch_size = batch_size or self.DEFAULT_BATCH_SIZE
        service_name = service.service_name

        logger.info(f"데이터 수집 시작: {service.description} ({service_name})")

        total_collected = 0
        start_index = 1

        while True:
            end_index = start_index + batch_size - 1

            data = await self._fetch_data(service_name, start_index, end_index)
            if data is None:
                break

            records, total_count = self._extract_records(data, service_name)
            if not records:
                logger.info("더 이상 데이터가 없습니다")
                break

            for record in records:
                if transform:
                    transformed = self._transform_record(record, service_key)
                    yield transformed
                else:
                    yield record

                total_collected += 1
                if max_records and total_collected >= max_records:
                    logger.info(f"최대 레코드 수({max_records})에 도달")
                    return

            # 전체 레코드 수 확인
            if start_index + batch_size > total_count:
                break

            start_index += batch_size
            await asyncio.sleep(self.DEFAULT_RATE_LIMIT_DELAY)

        logger.info(f"데이터 수집 완료: {total_collected}개")

    def _transform_record(
        self, record: dict[str, Any], service_key: str
    ) -> dict[str, Any]:
        """
        레코드 변환.

        Args:
            record: 원본 레코드
            service_key: 서비스 키

        Returns:
            변환된 레코드
        """
        service = SEOUL_SERVICES.get(service_key)
        if not service:
            return record

        # 기본 메타데이터 추가
        transformed = {
            "document_type": service_key,
            "data_source": "서울 열린 데이터 광장",
            "data_code": service.data_code,
            "category": service.category.value,
            "collected_at": datetime.now().isoformat(),
            "raw_data": record,
        }

        # 서비스별 특화 변환
        transform_method = getattr(self, f"_transform_{service_key}", None)
        if transform_method:
            transformed.update(transform_method(record))
        else:
            # 기본 변환: 원본 필드 그대로 포함
            transformed.update(record)

        return transformed

    # ============================================================
    # 부동산 가격/거래 데이터 변환
    # ============================================================

    def _transform_real_transaction(self, record: dict[str, Any]) -> dict[str, Any]:
        """부동산 실거래가 데이터 변환."""
        result = {}

        # 위치 정보
        if "SGG_NM" in record:
            result["district"] = record["SGG_NM"]  # 자치구
        if "BJDONG_NM" in record:
            result["legal_dong"] = record["BJDONG_NM"]  # 법정동

        # 거래 정보
        if "DEAL_YMD" in record:
            result["deal_date"] = record["DEAL_YMD"]  # 계약일
        if "OBJ_AMT" in record:
            try:
                result["price_10k"] = int(
                    str(record["OBJ_AMT"]).replace(",", "")
                )  # 거래금액 (만원)
            except (ValueError, TypeError):
                pass

        # 건물 정보
        if "BLDG_AREA" in record:
            try:
                result["area_m2"] = float(record["BLDG_AREA"])  # 건물면적
            except (ValueError, TypeError):
                pass
        if "BUILD_YEAR" in record:
            result["build_year"] = record["BUILD_YEAR"]  # 건축년도
        if "HOUSE_TYPE" in record:
            result["house_type"] = record["HOUSE_TYPE"]  # 주택유형

        return result

    def _transform_rent_price(self, record: dict[str, Any]) -> dict[str, Any]:
        """전월세가 데이터 변환."""
        result = {}

        # 위치 정보
        if "SGG_NM" in record:
            result["district"] = record["SGG_NM"]
        if "BJDONG_NM" in record:
            result["legal_dong"] = record["BJDONG_NM"]

        # 계약 유형
        if "RENT_GBN" in record:
            rent_type = record["RENT_GBN"]
            result["rent_type"] = rent_type
            result["rent_type_en"] = "jeonse" if "전세" in rent_type else "monthly"

        # 금액 정보
        if "RENT_GTN" in record:
            try:
                result["deposit_10k"] = int(
                    str(record["RENT_GTN"]).replace(",", "")
                )  # 보증금 (만원)
            except (ValueError, TypeError):
                pass
        if "RENT_FEE" in record:
            try:
                result["monthly_rent_10k"] = int(
                    str(record["RENT_FEE"]).replace(",", "")
                )  # 월세 (만원)
            except (ValueError, TypeError):
                pass

        # 계약 정보
        if "CNTRCT_DE" in record:
            result["contract_date"] = record["CNTRCT_DE"]

        return result

    def _transform_land_price(self, record: dict[str, Any]) -> dict[str, Any]:
        """개별공시지가 데이터 변환."""
        result = {}

        if "SGG_NM" in record:
            result["district"] = record["SGG_NM"]
        if "BJDONG_NM" in record:
            result["legal_dong"] = record["BJDONG_NM"]
        if "JIMOK" in record:
            result["land_category"] = record["JIMOK"]  # 지목
        if "PBLNTF_PC" in record:
            try:
                result["official_price_sqm"] = int(record["PBLNTF_PC"])  # 공시지가 (원/㎡)
            except (ValueError, TypeError):
                pass
        if "STDMT_YM" in record:
            result["standard_date"] = record["STDMT_YM"]  # 기준년월

        return result

    # ============================================================
    # 정비사업/재개발 데이터 변환
    # ============================================================

    def _transform_redevelopment_legacy(self, record: dict[str, Any]) -> dict[str, Any]:
        """정비사업 현황 데이터 변환 (레거시 API - upisRebuild)."""
        result = {}

        # 프로젝트 코드
        if "PRJC_CD" in record:
            result["project_code"] = record["PRJC_CD"]
        if "RPT_MNG_CD" in record:
            result["report_code"] = record["RPT_MNG_CD"]

        # 지역 정보
        if "LOGVM" in record:
            result["region"] = record["LOGVM"]  # 서울특별시

        # 보고서 유형 (변경, 신규 등)
        if "RPT_TYPE" in record:
            result["report_type"] = record["RPT_TYPE"]

        # 분류 체계
        if "LCLSF" in record:
            result["category_large"] = record["LCLSF"]  # 대분류
        if "MCLSF" in record:
            result["category_medium"] = record["MCLSF"]  # 중분류
        if "SCLSF" in record:
            project_type = record["SCLSF"]
            result["project_type"] = project_type

            # 사업 유형 영문 매핑
            if "재개발" in project_type:
                result["project_type_en"] = "redevelopment"
            elif "재건축" in project_type:
                result["project_type_en"] = "reconstruction"
            elif "도시환경" in project_type:
                result["project_type_en"] = "urban_environment"
            elif "주거환경" in project_type:
                result["project_type_en"] = "residential_improvement"
            else:
                result["project_type_en"] = "other"

        # 위치 정보
        if "PSTN_NM" in record:
            result["location_name"] = record["PSTN_NM"]

        # 구역명 (프로젝트명)
        if "RGN_NM" in record:
            result["project_name"] = record["RGN_NM"]

        # 면적 정보
        for field, key in [
            ("AREA_EXS", "area_existing_m2"),
            ("AREA_CHG", "area_changed_m2"),
            ("AREA_CHG_AFTR", "area_m2"),
        ]:
            if field in record and record[field]:
                try:
                    area = float(record[field])
                    result[key] = area
                    if key == "area_m2":
                        result["area_pyeong"] = area / 3.3058
                except (ValueError, TypeError):
                    pass

        # 결정고시관리코드
        if "DCSN_ANCMNT_MNG_CD" in record:
            result["decision_code"] = record["DCSN_ANCMNT_MNG_CD"]

        return result

    def _transform_cleanup_biz(self, record: dict[str, Any]) -> dict[str, Any]:
        """재개발 재건축 정비사업 현황 데이터 변환."""
        result = {}

        # 일반 필드 매핑
        field_mapping = {
            "GU_NM": "district",
            "ZONE_NM": "zone_name",
            "STEP_SE_NM": "stage",
            "BSNS_SE_NM": "business_type",
            "PROGRS_STTUS": "progress_status",
            "AR": "area_m2",
        }

        for src, dst in field_mapping.items():
            if src in record:
                result[dst] = record[src]

        # 면적 변환
        if "area_m2" in result:
            try:
                result["area_m2"] = float(result["area_m2"])
                result["area_pyeong"] = result["area_m2"] / 3.3058
            except (ValueError, TypeError):
                pass

        return result

    # ============================================================
    # 교통/인프라 데이터 변환
    # ============================================================

    def _transform_subway_station(self, record: dict[str, Any]) -> dict[str, Any]:
        """지하철역 정보 데이터 변환."""
        result = {}

        if "STATION_CD" in record:
            result["station_code"] = record["STATION_CD"]
        if "STATION_NM" in record:
            result["station_name"] = record["STATION_NM"]
        if "LINE_NUM" in record:
            result["line_number"] = record["LINE_NUM"]
        if "FR_CODE" in record:
            result["fr_code"] = record["FR_CODE"]

        return result

    def _transform_subway_address(self, record: dict[str, Any]) -> dict[str, Any]:
        """지하철역 주소 데이터 변환."""
        result = {}

        if "STATION_NM" in record:
            result["station_name"] = record["STATION_NM"]
        if "ADDRESS" in record:
            result["address"] = record["ADDRESS"]
        if "TEL" in record:
            result["phone"] = record["TEL"]

        return result

    def _transform_bus_stop(self, record: dict[str, Any]) -> dict[str, Any]:
        """버스정류소 위치 데이터 변환."""
        result = {}

        if "STOP_NO" in record:
            result["stop_number"] = record["STOP_NO"]
        if "STOP_NM" in record:
            result["stop_name"] = record["STOP_NM"]
        if "XCODE" in record:
            try:
                result["longitude"] = float(record["XCODE"])
            except (ValueError, TypeError):
                pass
        if "YCODE" in record:
            try:
                result["latitude"] = float(record["YCODE"])
            except (ValueError, TypeError):
                pass

        return result

    # ============================================================
    # 용도지역/공간정보 데이터 변환
    # ============================================================

    def _transform_land_use_zone(self, record: dict[str, Any]) -> dict[str, Any]:
        """용도지역 공간정보 데이터 변환."""
        # 기본 필드 그대로 반환 (API 응답 구조에 따라 조정 필요)
        return record

    def _transform_greenbelt(self, record: dict[str, Any]) -> dict[str, Any]:
        """개발제한구역 공간정보 데이터 변환."""
        return record

    # ============================================================
    # 중개업소 데이터 변환
    # ============================================================

    def _transform_real_estate_agency(self, record: dict[str, Any]) -> dict[str, Any]:
        """부동산 중개업소 정보 데이터 변환."""
        result = {}

        field_mapping = {
            "BSNM_NM": "business_name",
            "ADDR": "address",
            "REPRSNT_NM": "representative",
            "TLPHON_NO": "phone",
            "REGIST_NO": "registration_number",
        }

        for src, dst in field_mapping.items():
            if src in record:
                result[dst] = record[src]

        return result

    # ============================================================
    # 편의 메서드 (기존 API 호환성 유지)
    # ============================================================

    async def find_service_name(self) -> str | None:
        """
        정비사업 데이터의 올바른 서비스명을 찾습니다.
        (기존 API 호환성 유지)
        """
        # 확인된 기본 서비스명 먼저 시도
        if await self.test_connection("redevelopment_legacy"):
            return SEOUL_SERVICES["redevelopment_legacy"].service_name
        return None

    async def collect_redevelopment_data(
        self,
        service_name: str | None = None,
        max_records: int | None = None,
        batch_size: int = 100,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        정비사업 현황 데이터 수집.
        (기존 API 호환성 유지)
        """
        async for record in self.collect_data(
            "redevelopment_legacy",
            max_records=max_records,
            batch_size=batch_size,
        ):
            yield record

    # ============================================================
    # 카테고리별 수집 메서드
    # ============================================================

    async def collect_real_estate_data(
        self,
        service_key: str = "real_transaction",
        max_records: int | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """부동산 가격/거래 데이터 수집."""
        async for record in self.collect_data(service_key, max_records=max_records):
            yield record

    async def collect_transport_data(
        self,
        service_key: str = "subway_station",
        max_records: int | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """교통/인프라 데이터 수집."""
        async for record in self.collect_data(service_key, max_records=max_records):
            yield record

    async def collect_land_use_data(
        self,
        service_key: str = "land_use_zone",
        max_records: int | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """용도지역/공간정보 데이터 수집."""
        async for record in self.collect_data(service_key, max_records=max_records):
            yield record

    async def collect_all_redevelopment(
        self,
        max_records_per_service: int | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """모든 정비사업 관련 데이터 수집."""
        redevelopment_services = [
            "urban_planning",
            "redevelopment_legacy",
            "cleanup_biz",
            "district_plan",
            "decision_notice",
            "renewal_promotion",
            "urban_development",
        ]

        for service_key in redevelopment_services:
            logger.info(f"수집 중: {service_key}")
            try:
                async for record in self.collect_data(
                    service_key, max_records=max_records_per_service
                ):
                    yield record
            except Exception as e:
                logger.error(f"{service_key} 수집 실패: {e}")
                continue


# ============================================================
# 문서 포맷팅 함수 (LightRAG 통합용)
# ============================================================


def format_real_estate_document(record: dict[str, Any]) -> str:
    """부동산 거래 데이터를 LightRAG 문서로 포맷팅."""
    parts = []

    doc_type = record.get("document_type", "real_estate")
    if doc_type == "real_transaction":
        parts.append("서울시 부동산 실거래가 정보")
    elif doc_type == "rent_price":
        parts.append("서울시 부동산 전월세가 정보")
    else:
        parts.append(f"서울시 부동산 정보: {doc_type}")

    # 위치
    district = record.get("district")
    legal_dong = record.get("legal_dong")
    if district:
        location = district
        if legal_dong:
            location += f" {legal_dong}"
        parts.append(f"위치: {location}")

    # 가격 정보
    price = record.get("price_10k")
    if price:
        parts.append(f"거래금액: {price:,}만원")

    deposit = record.get("deposit_10k")
    if deposit:
        parts.append(f"보증금: {deposit:,}만원")

    monthly = record.get("monthly_rent_10k")
    if monthly:
        parts.append(f"월세: {monthly:,}만원")

    # 건물 정보
    area = record.get("area_m2")
    if area:
        parts.append(f"면적: {area:.1f}㎡ ({area / 3.3058:.1f}평)")

    build_year = record.get("build_year")
    if build_year:
        parts.append(f"건축년도: {build_year}년")

    # 메타데이터
    parts.append(f"데이터 출처: {record.get('data_source', '서울 열린 데이터 광장')}")

    return "\n".join(parts)


def format_redevelopment_document(record: dict[str, Any]) -> str:
    """
    정비사업 데이터를 LightRAG 문서로 포맷팅.

    Args:
        record: 변환된 정비사업 레코드

    Returns:
        자연어 문서
    """
    parts = []

    # 헤더 - 구역명/프로젝트명
    project_name = record.get("project_name", "정비사업")
    parts.append(f"서울시 정비사업 정보: {project_name}")

    # 사업 유형
    project_type = record.get("project_type", "")
    if project_type:
        parts.append(f"사업 유형: {project_type}")

    # 분류 체계
    category_medium = record.get("category_medium")
    if category_medium:
        parts.append(f"분류: {category_medium}")

    # 위치
    region = record.get("region")
    location_name = record.get("location_name")

    if region:
        location = region
        if location_name:
            location += f" {location_name}"
        parts.append(f"위치: {location}")

    # 보고서 유형
    report_type = record.get("report_type")
    if report_type:
        parts.append(f"보고서 유형: {report_type}")

    # 면적 정보
    area = record.get("area_m2")
    area_pyeong = record.get("area_pyeong")
    if area:
        if area_pyeong:
            parts.append(f"사업 면적: {area:,.0f}㎡ ({area_pyeong:,.0f}평)")
        else:
            parts.append(f"사업 면적: {area:,.0f}㎡")

    # 기존 면적 (변경 전)
    area_existing = record.get("area_existing_m2")
    if area_existing:
        parts.append(f"기존 면적: {area_existing:,.0f}㎡")

    # 변경 면적
    area_changed = record.get("area_changed_m2")
    if area_changed:
        parts.append(f"변경 면적: {area_changed:,.0f}㎡")

    # 추진 단계
    stage = record.get("stage")
    if stage:
        parts.append(f"추진 단계: {stage}")

    # 프로젝트 코드
    project_code = record.get("project_code")
    if project_code:
        parts.append(f"프로젝트 코드: {project_code}")

    # 메타데이터
    parts.append(f"데이터 출처: {record.get('data_source', '서울 열린 데이터 광장')}")

    return "\n".join(parts)


def format_transport_document(record: dict[str, Any]) -> str:
    """교통/인프라 데이터를 LightRAG 문서로 포맷팅."""
    parts = []

    doc_type = record.get("document_type", "transport")

    if doc_type in ("subway_station", "subway_address"):
        station_name = record.get("station_name", "지하철역")
        parts.append(f"서울시 지하철역 정보: {station_name}")

        line = record.get("line_number")
        if line:
            parts.append(f"노선: {line}")

        address = record.get("address")
        if address:
            parts.append(f"주소: {address}")

        phone = record.get("phone")
        if phone:
            parts.append(f"연락처: {phone}")

    elif doc_type == "bus_stop":
        stop_name = record.get("stop_name", "버스정류소")
        parts.append(f"서울시 버스정류소 정보: {stop_name}")

        stop_number = record.get("stop_number")
        if stop_number:
            parts.append(f"정류소 번호: {stop_number}")

        lat = record.get("latitude")
        lon = record.get("longitude")
        if lat and lon:
            parts.append(f"좌표: ({lat}, {lon})")

    else:
        parts.append(f"서울시 교통 정보: {doc_type}")

    parts.append(f"데이터 출처: {record.get('data_source', '서울 열린 데이터 광장')}")

    return "\n".join(parts)


def format_agency_document(record: dict[str, Any]) -> str:
    """중개업소 데이터를 LightRAG 문서로 포맷팅."""
    parts = []

    business_name = record.get("business_name", "부동산 중개업소")
    parts.append(f"서울시 부동산 중개업소 정보: {business_name}")

    address = record.get("address")
    if address:
        parts.append(f"주소: {address}")

    representative = record.get("representative")
    if representative:
        parts.append(f"대표자: {representative}")

    phone = record.get("phone")
    if phone:
        parts.append(f"연락처: {phone}")

    reg_no = record.get("registration_number")
    if reg_no:
        parts.append(f"등록번호: {reg_no}")

    parts.append(f"데이터 출처: {record.get('data_source', '서울 열린 데이터 광장')}")

    return "\n".join(parts)


def format_document(record: dict[str, Any]) -> str:
    """
    레코드 타입에 따라 적절한 포맷 함수 선택.

    Args:
        record: 변환된 레코드

    Returns:
        자연어 문서
    """
    category = record.get("category")

    if category == DataCategory.REAL_ESTATE.value:
        return format_real_estate_document(record)
    elif category == DataCategory.REDEVELOPMENT.value:
        return format_redevelopment_document(record)
    elif category == DataCategory.TRANSPORT.value:
        return format_transport_document(record)
    elif category == DataCategory.AGENCY.value:
        return format_agency_document(record)
    else:
        # 기본 포맷
        return str(record)
