#!/bin/bash

# Rancher Desktop용 부동산 데이터 수집기 중지 스크립트

echo "🛑 Rancher Desktop 환경에서 부동산 데이터 수집기를 중지합니다..."

# 서비스 중지
echo "⏹️  서비스를 중지합니다..."
nerdctl compose -f docker-compose.rancher.yml down

# 컨테이너 정리
echo "🧹 컨테이너를 정리합니다..."
nerdctl compose -f docker-compose.rancher.yml down --remove-orphans

# 사용하지 않는 이미지 정리 (선택사항)
read -p "🗑️  사용하지 않는 이미지도 삭제하시겠습니까? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🗑️  사용하지 않는 이미지를 삭제합니다..."
    nerdctl image prune -f
fi

echo ""
echo "✅ 부동산 데이터 수집기가 성공적으로 중지되었습니다!"
echo ""
echo "📋 남은 리소스 확인:"
echo "  컨테이너: nerdctl ps -a"
echo "  이미지: nerdctl images"
echo "  볼륨: nerdctl volume ls"
