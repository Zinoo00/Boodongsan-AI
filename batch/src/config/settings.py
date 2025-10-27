"""
설정 관리 모듈
"""

import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Config:
    """애플리케이션 설정 클래스"""
    
    # 공공데이터포털 API 설정
    # 아파트 전월세 API
    APT_RENT_BASE_URL = "http://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"

    # 아파트 매매 실거래가 API
    APT_TRADE_BASE_URL = "http://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"

    # 연립다세대 전월세 API
    RH_RENT_BASE_URL = "http://apis.data.go.kr/1613000/RTMSDataSvcRHRent/getRTMSDataSvcRHRent"

    # 연립다세대 매매 실거래가 API
    RH_TRADE_BASE_URL = "http://apis.data.go.kr/1613000/RTMSDataSvcRHTrade/getRTMSDataSvcRHTrade"

    # 오피스텔 전월세 API
    OFFI_RENT_BASE_URL = "http://apis.data.go.kr/1613000/RTMSDataSvcOffiRent/getRTMSDataSvcOffiRent"

    # 오피스텔 매매 실거래가 API
    OFFI_TRADE_BASE_URL = "http://apis.data.go.kr/1613000/RTMSDataSvcOffiTrade/getRTMSDataSvcOffiTrade"

    # API 키 (환경변수에서 가져옴)
    SERVICE_KEY = os.getenv("SERVICE_KEY", "")

    # 로그 설정
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # 무료 OpenSearch 설정 (Docker 컨테이너 사용)
    OPENSEARCH_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT", "http://localhost:9200")
    OPENSEARCH_USERNAME = os.getenv("OPENSEARCH_USERNAME", "admin")
    OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "admin")

    # 기본 수집 설정
    DEFAULT_YEARS = 1
    DEFAULT_SCHEDULE_TIME = "02:00"
    
    # S3 설정
    S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "bds-collect")
    S3_REGION_NAME = os.getenv("S3_REGION_NAME", "ap-northeast-2")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    
    # S3 저장 활성화 여부
    ENABLE_S3_STORAGE = os.getenv("ENABLE_S3_STORAGE", "true").lower() == "true"