#!/bin/bash

# 부동산 데이터 수집기 Docker 환경 중지 스크립트

echo "🛑 부동산 데이터 수집기 Docker 환경 중지"

# Docker Compose 서비스 중지
echo "📦 Docker Compose 서비스 중지 중..."

if [ "$1" = "prod" ]; then
    echo "🏭 프로덕션 환경 중지"
    docker-compose -f docker-compose.yml -f docker-compose.prod.yml down
elif [ "$1" = "dev" ]; then
    echo "🔧 개발 환경 중지"
    docker-compose -f docker-compose.yml -f docker-compose.dev.yml down
else
    echo "🚀 기본 환경 중지"
    docker-compose down
fi

echo "✅ 서비스 중지 완료!"
echo ""
echo "🧹 볼륨도 함께 삭제하려면:"
echo "  docker-compose down -v"
echo ""
echo "🔄 서비스 재시작:"
echo "  ./scripts/start.sh"
