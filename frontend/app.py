"""
부동산 데이터 대화형 인터페이스
AWS Knowledge Base와 연결된 Streamlit 애플리케이션
"""

import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 리팩토링된 메인 앱 실행
from src.main import main

if __name__ == "__main__":
    main()
