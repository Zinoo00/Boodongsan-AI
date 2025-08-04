"""
FastAPI 메인 애플리케이션
부동산 AI 챗봇 API 엔드포인트
"""

import logging
import uvicorn
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi

# 로컬 임포트
from .routers import chat, health, policies, properties, users
from ..database.connection import initialize_database, cleanup_connections, health_check
from ..ai.bedrock_client import initialize_bedrock
from ..ai.langchain_pipeline import initialize_agent
from ..database.policy_seed_data import seed_government_policies

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    # 시작 시
    logger.info("부동산 AI 챗봇 애플리케이션 시작")
    
    try:
        # 데이터베이스 초기화
        await initialize_database()
        
        # AWS Bedrock 초기화
        await initialize_bedrock()
        
        # AI 에이전트 초기화
        await initialize_agent()
        
        # 정부 정책 시드 데이터 추가
        await seed_government_policies()
        
        logger.info("모든 서비스 초기화 완료")
        
    except Exception as e:
        logger.error(f"서비스 초기화 실패: {str(e)}")
        raise
    
    yield
    
    # 종료 시
    logger.info("애플리케이션 종료 중...")
    await cleanup_connections()
    logger.info("애플리케이션 종료 완료")

# FastAPI 앱 생성
app = FastAPI(
    title="부동산 AI 챗봇 API",
    description="한국 부동산 시장을 위한 AI 기반 개인맞춤형 부동산 추천 챗봇",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인만 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 신뢰할 수 있는 호스트 미들웨어
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # 프로덕션에서는 특정 호스트만 허용
)

# 라우터 등록
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(health.router, prefix="/api/v1/health", tags=["Health"])
app.include_router(policies.router, prefix="/api/v1/policies", tags=["Policies"])
app.include_router(properties.router, prefix="/api/v1/properties", tags=["Properties"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])

@app.get("/", response_model=Dict[str, Any])
async def root():
    """API 루트 엔드포인트"""
    return {
        "message": "부동산 AI 챗봇 API에 오신 것을 환영합니다!",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health"
    }

@app.get("/api/v1/info", response_model=Dict[str, Any])
async def api_info():
    """API 정보"""
    return {
        "name": "부동산 AI 챗봇 API",
        "version": "1.0.0",
        "description": "한국 부동산 시장을 위한 AI 기반 개인맞춤형 부동산 추천 챗봇",
        "features": [
            "자연어 기반 부동산 상담",
            "개인맞춤형 매물 추천",
            "정부 지원 정책 매칭",
            "실시간 시장 정보 제공",
            "채팅 기록 관리"
        ],
        "endpoints": {
            "chat": "/api/v1/chat",
            "policies": "/api/v1/policies", 
            "properties": "/api/v1/properties",
            "users": "/api/v1/users",
            "health": "/api/v1/health"
        }
    }

# 전역 예외 처리기
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """전역 예외 처리"""
    logger.error(f"전역 예외 발생: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "서버에서 오류가 발생했습니다.",
            "detail": str(exc) if app.debug else None
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTP 예외 처리"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )

# 사용자 정의 OpenAPI 스키마
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="부동산 AI 챗봇 API",
        version="1.0.0",
        description="한국 부동산 시장을 위한 AI 기반 개인맞춤형 부동산 추천 챗봇 API",
        routes=app.routes,
    )
    
    # API 키 보안 스키마 추가
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key"
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

if __name__ == "__main__":
    # 개발 서버 실행
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )