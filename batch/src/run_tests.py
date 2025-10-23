"""
상수를 활용한 테스트 실행 스크립트
"""

import sys
import os
import subprocess
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.constants import SCRIPT_FILES, TEST_FILES, DEFAULT_SETTINGS

def run_command(command, description):
    """명령어 실행 및 결과 출력"""
    print(f"\n{'='*60}")
    print(f"🚀 {description}")
    print(f"{'='*60}")
    print(f"명령어: {command}")
    print("-" * 60)
    
    try:
        result = subprocess.run(command, shell=True, cwd=project_root, 
                              capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print("✅ 성공!")
            if result.stdout:
                print("출력:")
                print(result.stdout)
        else:
            print("❌ 실패!")
            if result.stderr:
                print("에러:")
                print(result.stderr)
                
    except subprocess.TimeoutExpired:
        print("⏰ 시간 초과 (5분)")
    except Exception as e:
        print(f"❌ 실행 오류: {e}")

def main():
    """메인 테스트 실행 함수"""
    print("🏠 부동산 데이터 수집 시스템 테스트")
    print("=" * 60)
    
    # 테스트 순서 정의
    test_sequence = [
        {
            "command": f"python {SCRIPT_FILES['load_lawd_codes']}",
            "description": "1. 법정동 코드 로드 테스트"
        },
        {
            "command": f"python {TEST_FILES['lawd_service']}",
            "description": "2. 법정동 서비스 테스트"
        },
        {
            "command": f"python {SCRIPT_FILES['main']} --data_type apt_rent --lawd_cd 41480 --deal_ymd 202412",
            "description": "3. 기존 메인 데이터 수집 테스트"
        },
        {
            "command": f"python {SCRIPT_FILES['collect_data_now']}",
            "description": "4. 즉시 데이터 수집 테스트"
        },
        {
            "command": f"python {SCRIPT_FILES['collect_data_scheduled']} --data_type apt_rent --regions 41480 --recent",
            "description": "5. 스케줄된 데이터 수집 테스트"
        }
    ]
    
    # 테스트 실행
    for i, test in enumerate(test_sequence, 1):
        run_command(test["command"], test["description"])
        
        # 사용자 확인 (선택적)
        if i < len(test_sequence):
            response = input(f"\n다음 테스트를 계속하시겠습니까? (y/n/skip): ").lower()
            if response == 'n':
                print("테스트를 중단합니다.")
                break
            elif response == 'skip':
                print("나머지 테스트를 건너뜁니다.")
                break
    
    print(f"\n{'='*60}")
    print("🎉 모든 테스트 완료!")
    print("=" * 60)

if __name__ == "__main__":
    main()
