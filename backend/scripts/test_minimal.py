"""
최소한의 서비스 테스트 스크립트.

이 스크립트는 다음을 테스트합니다:
1. AIService (AWS Bedrock 연결)
2. LightRAGService (초기화 및 기본 작동)
3. 간단한 문서 삽입 및 쿼리

Usage:
    cd backend
    uv run python -m scripts.test_minimal
"""

from __future__ import annotations

import asyncio
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_ai_service() -> bool:
    """AIService (AWS Bedrock) 연결 테스트."""
    from services.ai_service import AIService

    logger.info("=" * 50)
    logger.info("1. AIService (AWS Bedrock) 테스트")
    logger.info("=" * 50)

    ai_service = AIService()
    try:
        await ai_service.initialize()
        logger.info(f"✅ AIService 초기화 성공")
        logger.info(f"   Provider: {ai_service.provider}")
        logger.info(f"   Embedding Dim: {ai_service.embedding_dim}")

        # 임베딩 테스트
        logger.info("\n   임베딩 테스트 중...")
        test_text = "서울시 강남구 아파트"
        start = time.time()
        embeddings = await ai_service.generate_embeddings([test_text])
        elapsed = time.time() - start
        logger.info(f"✅ 임베딩 생성 성공 ({elapsed:.2f}초)")
        logger.info(f"   입력: '{test_text}'")
        logger.info(f"   차원: {len(embeddings[0])}")
        logger.info(f"   샘플: {embeddings[0][:5]}...")

        # 텍스트 생성 테스트
        logger.info("\n   텍스트 생성 테스트 중...")
        start = time.time()
        response = await ai_service.generate_text(
            "한국의 부동산 시장에 대해 한 문장으로 설명해주세요.",
            max_tokens=100,
        )
        elapsed = time.time() - start
        logger.info(f"✅ 텍스트 생성 성공 ({elapsed:.2f}초)")
        # response는 dict 또는 str일 수 있음
        if isinstance(response, dict):
            response_text = response.get("text", str(response))
        else:
            response_text = str(response)
        logger.info(f"   응답: {response_text[:200] if len(response_text) > 200 else response_text}")

        return True
    except Exception as e:
        logger.error(f"❌ AIService 테스트 실패: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        await ai_service.close()


async def test_lightrag_service() -> bool:
    """LightRAGService 초기화 및 기본 작동 테스트."""
    from services.ai_service import AIService
    from services.lightrag_service import LightRAGService

    logger.info("\n" + "=" * 50)
    logger.info("2. LightRAGService 테스트")
    logger.info("=" * 50)

    ai_service = AIService()
    lightrag_service = None

    try:
        await ai_service.initialize()
        lightrag_service = LightRAGService(ai_service=ai_service)
        await lightrag_service.initialize()

        logger.info(f"✅ LightRAGService 초기화 성공")
        logger.info(f"   Storage Backend: {lightrag_service.storage_backend_type}")
        logger.info(f"   Working Dir: {lightrag_service.working_dir}")

        # 데이터베이스가 비어있는지 확인
        is_empty = lightrag_service.is_empty()
        logger.info(f"   데이터베이스 비어있음: {is_empty}")

        # 샘플 문서 삽입
        logger.info("\n   샘플 문서 삽입 테스트 중...")
        sample_doc = """
        아파트 매매 정보 - 테스트 데이터
        위치: 서울특별시 강남구 삼성동
        건물명: 테스트 아파트
        매매가: 15억 원
        전용면적: 84.12㎡ (25.4평)
        층수: 15층
        건축년도: 2018년
        거래일자: 2024년 10월 15일
        데이터 출처: 테스트

        이 아파트는 서울 강남구 삼성동에 위치한 고급 아파트입니다.
        지하철 2호선 삼성역에서 도보 5분 거리에 있으며,
        주변에 코엑스, 현대백화점 등 편의시설이 잘 갖추어져 있습니다.
        """

        start = time.time()
        success = await lightrag_service.insert(sample_doc)
        elapsed = time.time() - start

        if success:
            logger.info(f"✅ 문서 삽입 성공 ({elapsed:.2f}초)")
        else:
            logger.warning(f"⚠️ 문서 삽입 실패 ({elapsed:.2f}초)")

        # 쿼리 테스트
        logger.info("\n   쿼리 테스트 중...")
        test_query = "강남구 아파트 가격이 얼마인가요?"

        start = time.time()
        response = await lightrag_service.query(test_query, mode="hybrid")
        elapsed = time.time() - start

        if response:
            logger.info(f"✅ 쿼리 성공 ({elapsed:.2f}초)")
            logger.info(f"   질문: {test_query}")
            # response는 dict 또는 str일 수 있음
            if isinstance(response, dict):
                response_text = response.get("response", str(response))
            else:
                response_text = str(response)
            logger.info(f"   응답: {response_text[:300] if len(response_text) > 300 else response_text}")
        else:
            logger.warning(f"⚠️ 쿼리 응답 없음 ({elapsed:.2f}초)")

        return True

    except Exception as e:
        logger.error(f"❌ LightRAGService 테스트 실패: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        if lightrag_service:
            await lightrag_service.finalize()
        await ai_service.close()


async def main():
    """메인 테스트 함수."""
    logger.info("\n🚀 BODA 서비스 최소 테스트 시작\n")

    results = {}

    # 1. AI Service 테스트
    results["ai_service"] = await test_ai_service()

    # 2. LightRAG Service 테스트
    results["lightrag_service"] = await test_lightrag_service()

    # 결과 요약
    logger.info("\n" + "=" * 50)
    logger.info("📊 테스트 결과 요약")
    logger.info("=" * 50)

    all_passed = True
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"   {name}: {status}")
        if not passed:
            all_passed = False

    if all_passed:
        logger.info("\n🎉 모든 테스트 통과!")
    else:
        logger.info("\n⚠️ 일부 테스트 실패. 로그를 확인하세요.")

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
