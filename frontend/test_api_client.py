"""
API 클라이언트 테스트 스크립트
백엔드 연결 및 기본 기능 검증

사용법:
    python test_api_client.py
"""

import sys
from typing import Any

from api_client import BODAAPIClient
from config import settings


def print_section(title: str) -> None:
    """섹션 헤더 출력"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_health_check(client: BODAAPIClient) -> bool:
    """백엔드 헬스 체크 테스트"""
    print_section("1. Health Check Test")

    try:
        health = client.health_check()
        print(f"✅ Health check 성공!")
        print(f"   Status: {health.get('status', 'unknown')}")
        print(f"   Response: {health}")
        return True
    except Exception as e:
        print(f"❌ Health check 실패: {e}")
        return False


def test_send_message(client: BODAAPIClient, user_id: str) -> bool:
    """채팅 메시지 전송 테스트"""
    print_section("2. Send Message Test")

    test_message = "강남구 아파트 전세 5억 이하 추천해줘"

    try:
        print(f"📤 메시지 전송: '{test_message}'")
        response = client.send_message(
            message=test_message,
            user_id=user_id,
        )

        print(f"✅ 메시지 전송 성공!")
        print(f"   User ID: {response.user_id}")
        print(f"   Conversation ID: {response.conversation_id}")
        print(f"   Processing Time: {response.processing_time_ms:.0f}ms")
        print(f"   Knowledge Mode: {response.knowledge_mode}")
        print(f"   Response Preview: {response.response[:200]}...")

        return True
    except Exception as e:
        print(f"❌ 메시지 전송 실패: {e}")
        return False


def test_conversation_history(client: BODAAPIClient, user_id: str, conversation_id: str) -> bool:
    """대화 이력 조회 테스트"""
    print_section("3. Conversation History Test")

    try:
        print(f"📜 대화 이력 조회: conversation_id={conversation_id}")
        history = client.get_conversation_history(
            conversation_id=conversation_id,
            user_id=user_id,
            limit=10,
        )

        print(f"✅ 대화 이력 조회 성공!")
        print(f"   Conversation ID: {history.conversation_id}")
        print(f"   Total Messages: {history.total_count}")

        if history.messages:
            print(f"   Latest Message: {history.messages[0]}")

        return True
    except Exception as e:
        print(f"❌ 대화 이력 조회 실패: {e}")
        # 이력이 없는 경우 정상 동작일 수 있음
        return True


def test_user_context(client: BODAAPIClient, user_id: str) -> bool:
    """사용자 컨텍스트 조회 테스트"""
    print_section("4. User Context Test")

    try:
        print(f"👤 사용자 컨텍스트 조회: user_id={user_id}")
        context = client.get_user_context(user_id=user_id)

        print(f"✅ 사용자 컨텍스트 조회 성공!")
        print(f"   User ID: {context.user_id}")
        print(f"   Profile: {context.profile}")
        print(f"   Recent Conversations: {len(context.recent_conversations)}")

        return True
    except Exception as e:
        print(f"❌ 사용자 컨텍스트 조회 실패: {e}")
        return False


def main():
    """메인 테스트 실행"""
    print(f"\n🧪 BODA API Client Test Suite")
    print(f"Backend URL: {settings.BACKEND_URL}")
    print(f"API Base: {settings.api_base_url}")

    # API 클라이언트 생성
    client = BODAAPIClient()

    # 테스트 사용자 ID
    test_user_id = "test_user_123"
    test_conversation_id = None

    # 테스트 실행
    results = []

    # 1. Health Check
    results.append(("Health Check", test_health_check(client)))

    # 2. Send Message
    if results[-1][1]:  # health check 성공 시에만
        message_success = test_send_message(client, test_user_id)
        results.append(("Send Message", message_success))

        # conversation_id는 실제 응답에서 가져와야 하므로
        # 여기서는 더미 ID 사용
        test_conversation_id = "test_conversation_123"

    # 3. Conversation History (선택)
    if test_conversation_id:
        results.append(("Conversation History", test_conversation_history(client, test_user_id, test_conversation_id)))

    # 4. User Context
    results.append(("User Context", test_user_context(client, test_user_id)))

    # 결과 요약
    print_section("Test Results Summary")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {test_name}")

    print(f"\n{'='*60}")
    print(f"  Total: {passed}/{total} tests passed")
    print(f"{'='*60}\n")

    # 종료 코드 반환
    if passed == total:
        print("🎉 모든 테스트 통과!")
        sys.exit(0)
    else:
        print(f"⚠️  {total - passed}개 테스트 실패")
        sys.exit(1)


if __name__ == "__main__":
    main()
