import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Config:
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

    # 기본 파라미터 (스케줄러 모드에서만 사용)
    # 수동 수집 시에는 파라미터로 전달받아야 함

    # API 키 (환경변수에서 가져옴)
    SERVICE_KEY = os.getenv("SERVICE_KEY")
    if not SERVICE_KEY:
        raise ValueError(
            "SERVICE_KEY가 설정되지 않았습니다. "
            "1. .env 파일을 생성하고 SERVICE_KEY를 설정하세요. "
            "2. 또는 환경변수 SERVICE_KEY를 설정하세요. "
            "3. env_example.txt를 참고하세요."
        )

    # 데이터 저장 경로
    DATA_DIR = "data"

    # 새로운 직관적인 파일명
    APT_RENT_OUTPUT_FILE = "apartment_rent.csv"
    APT_TRADE_OUTPUT_FILE = "apartment_trade.csv"
    RH_RENT_OUTPUT_FILE = "rh_rent.csv"
    RH_TRADE_OUTPUT_FILE = "rh_trade.csv"
    OFFI_RENT_OUTPUT_FILE = "officetel_rent.csv"
    OFFI_TRADE_OUTPUT_FILE = "officetel_trade.csv"

    # API 요청 설정
    TIMEOUT = 30
    MAX_RETRIES = 3

    # 무료 OpenSearch 설정
    OPENSEARCH_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT", "http://localhost:9200")
    OPENSEARCH_USERNAME = os.getenv("OPENSEARCH_USERNAME", "admin")
    OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "admin")


    # 모델 설정
    MODEL_DIR = os.getenv("MODEL_DIR", "model")
    ONNX_MODEL_PATH = os.path.join(MODEL_DIR, "onnx")

    # 로그 설정
    LOG_DIR = os.getenv("LOG_DIR", "logs")
    SCHEDULER_LOG_FILE = os.path.join(LOG_DIR, "scheduler.log")
    COLLECT_LOG_FILE = os.path.join(LOG_DIR, "collect.log")
