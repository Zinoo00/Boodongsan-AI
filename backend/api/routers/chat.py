"""
채팅 API 라우터
자연어 기반 부동산 상담 엔드포인트
"""

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from ...ai.langchain_pipeline import ConversationContext, get_real_estate_agent
from ...database.connection import cache_manager, get_db_session
from ...database.models import ConversationHistory
from ...services.user_profiling_service import UserProfilingService

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic 모델들
class ChatMessage(BaseModel):
    """채팅 메시지 모델"""

    message: str = Field(..., description="사용자 메시지", min_length=1, max_length=1000)
    user_id: str | None = Field(None, description="사용자 ID")
    session_id: str | None = Field(None, description="세션 ID")


class ChatResponse(BaseModel):
    """채팅 응답 모델"""

    response: str = Field(..., description="AI 응답")
    session_id: str = Field(..., description="세션 ID")
    user_id: str | None = Field(None, description="사용자 ID")
    extracted_entities: dict[str, Any] | None = Field(None, description="추출된 개체 정보")
    detected_intent: str | None = Field(None, description="감지된 의도")
    recommended_policies: list[str] | None = Field(None, description="추천 정책 ID 목록")
    recommended_properties: list[str] | None = Field(None, description="추천 매물 ID 목록")
    conversation_context: dict[str, Any] | None = Field(None, description="대화 컨텍스트")
    processing_time_ms: int | None = Field(None, description="처리 시간(밀리초)")


class ConversationHistoryResponse(BaseModel):
    """대화 이력 응답 모델"""

    conversations: list[dict[str, Any]] = Field(..., description="대화 이력 목록")
    total_count: int = Field(..., description="전체 대화 수")
    session_id: str = Field(..., description="세션 ID")


class UserContextResponse(BaseModel):
    """사용자 컨텍스트 응답 모델"""

    user_profile: dict[str, Any] | None = Field(None, description="사용자 프로필")
    conversation_patterns: dict[str, Any] | None = Field(None, description="대화 패턴 분석")
    missing_info_suggestions: list[str] | None = Field(None, description="부족한 정보 제안")


@router.post("/send", response_model=ChatResponse)
async def send_message(chat_message: ChatMessage, background_tasks: BackgroundTasks):
    """메시지 전송 및 AI 응답 생성"""
    start_time = datetime.utcnow()

    try:
        # 세션 ID 생성 또는 기존 사용
        session_id = chat_message.session_id or str(uuid.uuid4())
        user_id = chat_message.user_id

        # 사용자 프로파일링 서비스 초기화
        profiling_service = UserProfilingService()

        # 기존 대화 컨텍스트 로드
        context = await _load_conversation_context(user_id, session_id)

        # AI 에이전트로 메시지 처리
        agent = get_real_estate_agent()
        response, updated_context = await agent.process_message(chat_message.message, context)

        # 처리 시간 계산
        processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        # 사용자 프로파일 업데이트 (백그라운드)
        if updated_context.extracted_entities and user_id:
            background_tasks.add_task(
                _update_user_profile_async, user_id, updated_context.extracted_entities, session_id
            )

        # 대화 기록 저장 (백그라운드)
        background_tasks.add_task(
            _save_conversation_async,
            user_id,
            session_id,
            chat_message.message,
            response,
            updated_context,
            processing_time,
        )

        # 컨텍스트 캐시 업데이트
        await _save_conversation_context(user_id, session_id, updated_context)

        return ChatResponse(
            response=response,
            session_id=session_id,
            user_id=user_id,
            extracted_entities=updated_context.extracted_entities,
            detected_intent=updated_context.current_intent,
            recommended_policies=getattr(updated_context, "recommended_policies", None),
            recommended_properties=getattr(updated_context, "recommended_properties", None),
            conversation_context={
                "completeness": getattr(updated_context, "profile_completeness", 0.0),
                "total_messages": len(updated_context.conversation_history or []),
            },
            processing_time_ms=processing_time,
        )

    except Exception as e:
        logger.error(f"메시지 처리 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"메시지 처리 중 오류가 발생했습니다: {str(e)}")


@router.get("/history/{session_id}", response_model=ConversationHistoryResponse)
async def get_conversation_history(
    session_id: str, user_id: str | None = None, limit: int = 50, offset: int = 0
):
    """대화 이력 조회"""
    try:
        async with get_db_session() as db:
            query = db.query(ConversationHistory).filter(
                ConversationHistory.session_id == session_id
            )

            if user_id:
                query = query.filter(ConversationHistory.user_id == user_id)

            # 최신 순으로 정렬
            conversations = (
                query.order_by(ConversationHistory.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )

            total_count = query.count()

            # 대화 이력 포맷팅
            formatted_conversations = []
            for conv in conversations:
                formatted_conversations.append(
                    {
                        "id": str(conv.id),
                        "user_message": conv.user_message,
                        "ai_response": conv.ai_response,
                        "extracted_entities": conv.extracted_entities,
                        "detected_intent": conv.detected_intent,
                        "recommended_policies": conv.recommended_policies,
                        "recommended_properties": conv.recommended_properties,
                        "processing_time": conv.processing_time,
                        "confidence_score": float(conv.confidence_score)
                        if conv.confidence_score
                        else None,
                        "created_at": conv.created_at.isoformat(),
                    }
                )

            return ConversationHistoryResponse(
                conversations=formatted_conversations,
                total_count=total_count,
                session_id=session_id,
            )

    except Exception as e:
        logger.error(f"대화 이력 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="대화 이력을 불러오는 중 오류가 발생했습니다.")


@router.get("/context/{user_id}", response_model=UserContextResponse)
async def get_user_context(user_id: str):
    """사용자 컨텍스트 및 프로필 정보 조회"""
    try:
        profiling_service = UserProfilingService()

        # 사용자 프로필 조회
        user_profile = await profiling_service.get_user_profile(user_id)

        # 대화 패턴 분석
        conversation_patterns = await profiling_service.analyze_conversation_patterns(user_id)

        # 부족한 정보 제안
        missing_info = await profiling_service.suggest_missing_info(user_id)

        return UserContextResponse(
            user_profile=user_profile,
            conversation_patterns=conversation_patterns,
            missing_info_suggestions=missing_info,
        )

    except Exception as e:
        logger.error(f"사용자 컨텍스트 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500, detail="사용자 정보를 불러오는 중 오류가 발생했습니다."
        )


@router.delete("/session/{session_id}")
async def clear_session(session_id: str, user_id: str | None = None):
    """세션 클리어"""
    try:
        # 캐시에서 컨텍스트 삭제
        cache_key = f"conversation_context:{user_id or 'anonymous'}:{session_id}"
        await cache_manager.delete(cache_key)

        # 선택적으로 데이터베이스에서도 삭제 (개인정보 보호)
        if user_id:
            async with get_db_session() as db:
                conversations = (
                    db.query(ConversationHistory)
                    .filter(
                        ConversationHistory.session_id == session_id,
                        ConversationHistory.user_id == user_id,
                    )
                    .all()
                )

                for conv in conversations:
                    db.delete(conv)

                await db.commit()

        return {"message": "세션이 성공적으로 클리어되었습니다."}

    except Exception as e:
        logger.error(f"세션 클리어 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="세션 클리어 중 오류가 발생했습니다.")


@router.post("/feedback")
async def submit_feedback(feedback_data: dict[str, Any]):
    """사용자 피드백 제출"""
    try:
        # 피드백 데이터 검증
        required_fields = ["session_id", "rating", "comment"]
        for field in required_fields:
            if field not in feedback_data:
                raise HTTPException(status_code=400, detail=f"필수 필드가 누락되었습니다: {field}")

        # 피드백 저장 (실제로는 별도 테이블에 저장)
        feedback_key = f"feedback:{feedback_data['session_id']}:{uuid.uuid4()}"
        feedback_data["timestamp"] = datetime.utcnow().isoformat()

        await cache_manager.set_json(feedback_key, feedback_data, ttl=86400 * 30)  # 30일

        logger.info(f"피드백 제출됨: {feedback_data['session_id']}")

        return {"message": "피드백이 성공적으로 제출되었습니다.", "feedback_id": feedback_key}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"피드백 제출 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="피드백 제출 중 오류가 발생했습니다.")


# 헬퍼 함수들


async def _load_conversation_context(user_id: str, session_id: str) -> ConversationContext:
    """대화 컨텍스트 로드"""
    try:
        # 캐시에서 컨텍스트 조회
        cache_key = f"conversation_context:{user_id or 'anonymous'}:{session_id}"
        cached_context = await cache_manager.get_json(cache_key)

        if cached_context:
            context = ConversationContext(
                user_id=user_id or cached_context.get("user_id"), session_id=session_id
            )
            context.user_profile = cached_context.get("user_profile")
            context.conversation_history = cached_context.get("conversation_history", [])
            context.extracted_entities = cached_context.get("extracted_entities", {})
            context.current_intent = cached_context.get("current_intent", "GENERAL_CHAT")

            return context

        # 새 컨텍스트 생성
        return ConversationContext(
            user_id=user_id,
            session_id=session_id,
            conversation_history=[],
            extracted_entities={},
            current_intent="GENERAL_CHAT",
        )

    except Exception as e:
        logger.error(f"컨텍스트 로드 실패: {str(e)}")
        return ConversationContext(user_id=user_id, session_id=session_id)


async def _save_conversation_context(user_id: str, session_id: str, context: ConversationContext):
    """대화 컨텍스트 저장"""
    try:
        cache_key = f"conversation_context:{user_id or 'anonymous'}:{session_id}"

        context_data = {
            "user_id": context.user_id,
            "session_id": context.session_id,
            "user_profile": context.user_profile,
            "conversation_history": context.conversation_history[-20:],  # 최근 20개만 유지
            "extracted_entities": context.extracted_entities,
            "current_intent": context.current_intent,
            "updated_at": datetime.utcnow().isoformat(),
        }

        await cache_manager.set_json(cache_key, context_data, ttl=3600 * 24)  # 24시간

    except Exception as e:
        logger.error(f"컨텍스트 저장 실패: {str(e)}")


async def _update_user_profile_async(
    user_id: str, extracted_entities: dict[str, Any], session_id: str
):
    """사용자 프로필 비동기 업데이트"""
    try:
        profiling_service = UserProfilingService()
        await profiling_service.create_or_update_profile(user_id, extracted_entities, session_id)
        logger.info(f"사용자 프로필 업데이트 완료: {user_id}")

    except Exception as e:
        logger.error(f"사용자 프로필 업데이트 실패: {str(e)}")


async def _save_conversation_async(
    user_id: str,
    session_id: str,
    user_message: str,
    ai_response: str,
    context: ConversationContext,
    processing_time: int,
):
    """대화 기록 비동기 저장"""
    try:
        async with get_db_session() as db:
            conversation = ConversationHistory(
                user_id=user_id,
                session_id=session_id,
                user_message=user_message,
                ai_response=ai_response,
                extracted_entities=context.extracted_entities,
                detected_intent=context.current_intent,
                recommended_policies=getattr(context, "recommended_policies", None),
                recommended_properties=getattr(context, "recommended_properties", None),
                processing_time=processing_time,
            )

            db.add(conversation)
            await db.commit()

        logger.info(f"대화 기록 저장 완료: {session_id}")

    except Exception as e:
        logger.error(f"대화 기록 저장 실패: {str(e)}")
