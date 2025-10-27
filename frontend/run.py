#!/usr/bin/env python3
"""
Streamlit 앱 실행 스크립트
"""

import subprocess
import sys
import os
import argparse

def main():
    """Streamlit 앱 실행"""
    parser = argparse.ArgumentParser(description='부동산 데이터 AI 어시스턴트 실행')
    parser.add_argument('--host', default='0.0.0.0', help='호스트 주소 (기본값: 0.0.0.0)')
    parser.add_argument('--port', default='8501', help='포트 번호 (기본값: 8501)')
    parser.add_argument('--reload', action='store_true', help='자동 재로드 활성화')
    
    args = parser.parse_args()
    
    try:
        # 현재 디렉토리에서 실행
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        
        # Streamlit 실행
        cmd = [
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.port", args.port,
            "--server.address", args.host,
            "--browser.gatherUsageStats", "false"
        ]
        
        if args.reload:
            cmd.append("--server.runOnSave")
        
        print(f"🚀 Streamlit으로 앱을 실행합니다...")
        print(f"📍 접속 주소: http://{args.host}:{args.port}")
        subprocess.run(cmd)
            
    except KeyboardInterrupt:
        print("\n✅ 앱이 종료되었습니다.")
    except Exception as e:
        print(f"❌ 앱 실행 중 오류가 발생했습니다: {e}")

if __name__ == "__main__":
    main()
