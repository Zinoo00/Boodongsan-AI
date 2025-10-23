#!/bin/bash

# 부동산 데이터 수집기 Docker 환경 시작 스크립트

set -e

echo "🚀 부동산 데이터 수집기 Docker 환경 시작"

# 환경 변수 파일 확인
if [ ! -f .env ]; then
    echo "⚠️  .env 파일이 없습니다. 기본 설정으로 진행합니다."
    # .env 파일이 없으면 생성 (SERVICE_KEY는 사용자가 직접 설정해야 함)
if [ ! -f .env ]; then
    echo "SERVICE_KEY=your_api_key_here" > .env
    echo "⚠️  .env 파일이 생성되었습니다. SERVICE_KEY를 실제 API 키로 변경해주세요."
fi
fi

# 필요한 디렉토리 생성
mkdir -p data logs config opensearch

# Docker Compose 서비스 시작
echo "📦 Docker Compose 서비스 시작 중..."

# 기본 환경으로 시작 (uv 사용)
echo "🚀 기본 환경으로 시작 (Python 3.11 + uv)"
docker-compose up -d

echo "✅ 서비스 시작 완료!"
echo ""
echo "📊 서비스 상태 확인:"
docker-compose ps
echo ""
echo "📝 로그 확인:"
echo "  docker-compose logs -f batch"
echo ""
echo "🛑 서비스 중지:"
echo "  docker-compose down"
echo ""
echo "🔄 서비스 재시작:"
echo "  docker-compose restart"
