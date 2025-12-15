"""
Data collectors for Korean Real Estate data sources.

Collectors:
- RealEstateCollector: 국토교통부 실거래가 API (MOLIT)
- SeoulOpenDataCollector: 서울 열린 데이터 광장 API (7개 작동 서비스, 2024.12 기준)
  - real_transaction: 부동산 실거래가
  - redevelopment: 정비사업 현황
  - subway_station: 지하철역 정보 (역코드)
  - subway_info: 지하철역 정보 (역명)
  - bus_stop: 버스정류소 위치정보
  - living_population: 서울 생활인구
  - real_estate_agency: 부동산 중개업소
- SigunguService: 시군구 코드 조회 서비스
"""

from .real_estate_collector import RealEstateCollector
from .seoul_opendata_collector import (
    DataCategory,
    SEOUL_SERVICES,
    SeoulOpenDataCollector,
    SeoulOpenDataService,
    format_agency_document,
    format_document,
    format_real_estate_document,
    format_redevelopment_document,
    format_transport_document,
)
from .sigungu_service import SigunguService, SigunguServiceSingleton

__all__ = [
    # Real Estate Collector (MOLIT)
    "RealEstateCollector",
    # Seoul Open Data Collector
    "SeoulOpenDataCollector",
    "SeoulOpenDataService",
    "DataCategory",
    "SEOUL_SERVICES",
    # Document formatters
    "format_document",
    "format_real_estate_document",
    "format_redevelopment_document",
    "format_transport_document",
    "format_agency_document",
    # Sigungu Service
    "SigunguService",
    "SigunguServiceSingleton",
]
