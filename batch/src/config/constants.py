"""
상수 정의 모듈
"""

# 데이터 타입 상수
DATA_TYPES = {
    "apt_rent": "아파트 전월세",
    "apt_trade": "아파트 매매",
    "rh_rent": "연립다세대 전월세", 
    "rh_trade": "연립다세대 매매",
    "offi_rent": "오피스텔 전월세",
    "offi_trade": "오피스텔 매매"
}

# OpenSearch 인덱스 이름
OPENSEARCH_INDICES = {
    "apt_rent": "apartment_rent",
    "apt_trade": "apartment_trade", 
    "rh_rent": "rh_rent",
    "rh_trade": "rh_trade",
    "offi_rent": "officetel_rent",
    "offi_trade": "officetel_trade"
}

# API 타입별 한글 이름
API_TYPE_NAMES = {
    "apt_rent": "아파트 전월세",
    "apt_trade": "아파트 매매 실거래가",
    "rh_rent": "연립다세대 전월세",
    "rh_trade": "연립다세대 매매 실거래가", 
    "offi_rent": "오피스텔 전월세",
    "offi_trade": "오피스텔 매매 실거래가"
}

# 스크립트 파일명 상수
SCRIPT_FILES = {
    "load_lawd_codes": "src/load_lawd_codes.py",
    "collect_data_now": "src/collect_data_now.py", 
    "collect_data_scheduled": "src/collect_data_scheduled.py",
    "main": "main.py"
}

# 테스트 파일명 상수
TEST_FILES = {
    "lawd_service": "tests/test_lawd_service.py",
    "data_service": "tests/test_data_service.py"
}

# 로그 파일 경로 상수
LOG_FILES = {
    "collect": "logs/collect.log",
    "scheduler": "logs/scheduler.log",
    "lawd": "logs/lawd.log"
}

# 기본 수집 설정 상수
DEFAULT_SETTINGS = {
    "years": 1,
    "schedule_time": "02:00",
    "log_level": "INFO"
}
