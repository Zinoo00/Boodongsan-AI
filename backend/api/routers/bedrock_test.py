from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.bedrock_service import BedrockService

router = APIRouter()

# 요청 모델
class TestMessage(BaseModel):
    message: str

# Bedrock 서비스 인스턴스
bedrock_service = BedrockService()

@router.get("/test")
async def test_connection():
    """Bedrock 연결 테스트"""
    try:
        is_connected = bedrock_service.test_connection()
        if is_connected:
            return {"status": "success", "message": "Bedrock 연결 성공!"}
        else:
            return {"status": "error", "message": "Bedrock 연결 실패"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"연결 테스트 중 오류: {str(e)}")

@router.post("/chat")
async def simple_chat(request: TestMessage):
    """간단한 채팅 테스트"""
    try:
        response = bedrock_service.send_message(request.message)
        return {
            "status": "success",
            "user_message": request.message,
            "ai_response": response
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"채팅 처리 중 오류: {str(e)}") 