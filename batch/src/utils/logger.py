"""
로깅 유틸리티 모듈
"""

import logging
import os
from datetime import datetime

def setup_logger(name: str, log_file: str = None, level: str = "INFO") -> logging.Logger:
    """
    로거 설정
    
    Args:
        name: 로거 이름
        log_file: 로그 파일 경로 (선택사항)
        level: 로그 레벨
        
    Returns:
        설정된 로거
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # 기존 핸들러 제거
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 포맷터 설정
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 파일 핸들러 (선택사항)
    if log_file:
        # 로그 디렉토리 생성
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

def get_logger(name: str) -> logging.Logger:
    """
    기존 로거 가져오기
    
    Args:
        name: 로거 이름
        
    Returns:
        로거
    """
    return logging.getLogger(name)
