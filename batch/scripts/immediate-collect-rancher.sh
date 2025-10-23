#!/bin/bash

# Rancher Desktop용 즉시 데이터 수집 스크립트

set -e

echo "🚀 Rancher Desktop 환경에서 즉시 데이터 수집을 시작합니다..."

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

# AWS OpenSearch 연결 확인
echo "🔍 AWS OpenSearch 연결을 확인합니다..."
echo "📊 OpenSearch 엔드포인트: ${OPENSEARCH_ENDPOINT}"

# 즉시 수집 서비스 실행 (Python 3.11 + uv 사용)
echo "📥 즉시 데이터 수집을 시작합니다 (Python 3.11 + uv)..."
nerdctl compose -f docker-compose.yml --profile immediate up batch-immediate

echo ""
echo "✅ 즉시 데이터 수집이 완료되었습니다!"
echo ""
echo "📋 결과 확인:"
echo "  데이터 파일: ls -la data/"
echo "  로그 파일: ls -la logs/"
echo "  서비스 상태: nerdctl compose -f docker-compose.yml ps"
