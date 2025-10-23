#!/bin/bash

# Rancher Desktop용 부동산 데이터 수집기 시작 스크립트

set -e

echo "🐳 Rancher Desktop 환경에서 부동산 데이터 수집기를 시작합니다..."

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
echo "📁 필요한 디렉토리를 생성합니다..."
mkdir -p data logs config opensearch

# Rancher Desktop 상태 확인
echo "🔍 Rancher Desktop 상태를 확인합니다..."
if ! nerdctl info > /dev/null 2>&1; then
    echo "❌ Rancher Desktop 데몬에 연결할 수 없습니다."
    echo "   Rancher Desktop이 실행 중인지 확인해주세요."
    echo "   또는 Preferences → Container Engine에서 Docker가 선택되어 있는지 확인해주세요."
    exit 1
fi

echo "✅ Rancher Desktop이 정상적으로 실행 중입니다."

# 기존 컨테이너 정리
echo "🧹 기존 컨테이너를 정리합니다..."
nerdctl compose -f docker-compose.yml down --remove-orphans 2>/dev/null || true

# 이미지 빌드 (Python 3.11 + uv 사용)
echo "🔨 Docker 이미지를 빌드합니다 (Python 3.11 + uv)..."
nerdctl compose -f docker-compose.yml build

# 서비스 시작
echo "🚀 서비스를 시작합니다..."
nerdctl compose -f docker-compose.yml up -d

# 상태 확인
echo "⏳ 서비스 상태를 확인합니다..."
sleep 10

# 컨테이너 상태 출력
echo "📊 컨테이너 상태:"
nerdctl compose -f docker-compose.yml ps

# 로그 확인
echo "📝 최근 로그 (마지막 10줄):"
nerdctl compose -f docker-compose.yml logs --tail=10

echo ""
echo "🎉 부동산 데이터 수집기가 성공적으로 시작되었습니다! (Python 3.11 + uv)"
echo ""
echo "📋 유용한 명령어:"
echo "  로그 확인: nerdctl compose -f docker-compose.yml logs -f"
echo "  서비스 중지: nerdctl compose -f docker-compose.yml down"
echo "  즉시 수집: ./scripts/immediate-collect-rancher.sh"
echo "  상태 확인: nerdctl compose -f docker-compose.yml ps"
echo ""
echo "🌐 AWS OpenSearch 대시보드: AWS 콘솔에서 확인"
