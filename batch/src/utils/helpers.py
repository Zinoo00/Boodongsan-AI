"""
헬퍼 함수 모듈
"""

import os
import json
from typing import List, Dict, Any
from datetime import datetime, timedelta

def ensure_directory(path: str) -> None:
    """
    디렉토리가 존재하지 않으면 생성
    
    Args:
        path: 디렉토리 경로
    """
    os.makedirs(path, exist_ok=True)

def get_lawd_codes() -> List[str]:
    """
    법정동코드 목록 반환
    
    Returns:
        법정동코드 리스트
    """
    return ["41480", "11680", "41135", "41280", "41290"]

def get_data_type_names() -> Dict[str, str]:
    """
    데이터 타입별 한글 이름 반환
    
    Returns:
        데이터 타입별 한글 이름 딕셔너리
    """
    return {
        "apt_rent": "아파트 전월세",
        "apt_trade": "아파트 매매",
        "rh_rent": "연립다세대 전월세",
        "rh_trade": "연립다세대 매매",
        "offi_rent": "오피스텔 전월세",
        "offi_trade": "오피스텔 매매"
    }

def get_recent_months(months: int = 1) -> List[str]:
    """
    최근 N개월의 년월 리스트 반환
    
    Args:
        months: 가져올 개월 수
        
    Returns:
        년월 리스트 (YYYYMM 형식)
    """
    months_list = []
    current_date = datetime.now()
    
    for i in range(months):
        target_date = current_date - timedelta(days=30 * i)
        months_list.append(target_date.strftime("%Y%m"))
    
    return months_list

def save_json(data: Any, filepath: str) -> bool:
    """
    JSON 파일로 데이터 저장
    
    Args:
        data: 저장할 데이터
        filepath: 파일 경로
        
    Returns:
        저장 성공 여부
    """
    try:
        ensure_directory(os.path.dirname(filepath))
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"JSON 저장 실패: {e}")
        return False

def load_json(filepath: str) -> Any:
    """
    JSON 파일에서 데이터 로드
    
    Args:
        filepath: 파일 경로
        
    Returns:
        로드된 데이터
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"JSON 로드 실패: {e}")
        return None
