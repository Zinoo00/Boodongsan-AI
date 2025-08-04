#!/bin/bash

# 부동산 AI 챗봇 프로젝트 설정 스크립트

set -e

echo "🏠 부동산 AI 챗봇 프로젝트 설정을 시작합니다..."

# 환경 확인
check_requirements() {
    echo "📋 필요한 프로그램들을 확인합니다..."
    
    # Docker 확인
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker가 설치되어 있지 않습니다."
        echo "   https://docs.docker.com/get-docker/ 에서 Docker를 설치해주세요."
        exit 1
    fi
    
    # Docker Compose 확인
    if ! command -v docker-compose &> /dev/null; then
        echo "❌ Docker Compose가 설치되어 있지 않습니다."
        echo "   https://docs.docker.com/compose/install/ 에서 Docker Compose를 설치해주세요."
        exit 1
    fi
    
    # Python 확인
    if ! command -v python3 &> /dev/null; then
        echo "❌ Python 3가 설치되어 있지 않습니다."
        echo "   https://www.python.org/downloads/ 에서 Python을 설치해주세요."
        exit 1
    fi
    
    echo "✅ 모든 필요 프로그램이 설치되어 있습니다."
}

# 환경 변수 파일 설정
setup_env() {
    echo "📝 환경 변수를 설정합니다..."
    
    if [ ! -f .env ]; then
        cp .env.example .env
        echo "⚠️  .env 파일이 생성되었습니다. AWS 키를 설정해주세요:"
        echo "   - AWS_ACCESS_KEY_ID"
        echo "   - AWS_SECRET_ACCESS_KEY"
        echo "   - PINECONE_API_KEY (선택사항)"
        echo ""
        echo "   설정 후 다시 실행해주세요."
        exit 1
    fi
    
    echo "✅ 환경 변수 파일이 준비되었습니다."
}

# Docker 이미지 빌드
build_images() {
    echo "🔨 Docker 이미지를 빌드합니다..."
    docker-compose build
    echo "✅ Docker 이미지 빌드가 완료되었습니다."
}

# 데이터베이스 초기화
init_database() {
    echo "🗄️ 데이터베이스를 초기화합니다..."
    
    # 컨테이너 시작
    docker-compose up -d postgres redis
    
    # PostgreSQL이 준비될 때까지 대기
    echo "⏳ PostgreSQL이 준비될 때까지 대기합니다..."
    sleep 10
    
    # 백엔드 컨테이너에서 데이터베이스 초기화 실행
    echo "📊 테이블을 생성하고 시드 데이터를 추가합니다..."
    docker-compose run --rm backend python -c "
import asyncio
from database.connection import initialize_database, create_tables
from database.policy_seed_data import seed_government_policies

async def init():
    await initialize_database()
    await create_tables()
    await seed_government_policies()
    print('데이터베이스 초기화 완료!')

asyncio.run(init())
"
    
    echo "✅ 데이터베이스 초기화가 완료되었습니다."
}

# 애플리케이션 시작
start_app() {
    echo "🚀 애플리케이션을 시작합니다..."
    docker-compose up -d
    
    echo ""
    echo "🎉 설정이 완료되었습니다!"
    echo ""
    echo "📍 접속 정보:"
    echo "   • API 서버: http://localhost:8000"
    echo "   • API 문서: http://localhost:8000/docs"
    echo "   • 헬스체크: http://localhost:8000/api/v1/health"
    echo ""
    echo "🔧 유용한 명령어:"
    echo "   • 로그 확인: docker-compose logs -f"
    echo "   • 서비스 중지: docker-compose down"
    echo "   • 데이터베이스 리셋: docker-compose down -v && ./scripts/setup.sh"
    echo ""
}

# 메인 실행
main() {
    check_requirements
    setup_env
    build_images
    init_database
    start_app
}

# 스크립트가 직접 실행된 경우에만 main 함수 실행
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi