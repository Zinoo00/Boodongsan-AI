"""
헬스체크 API 라우터
시스템 상태 확인 엔드포인트
"""

import logging
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...database.connection import health_check as db_health_check
from ...ai.bedrock_client import get_bedrock_client

logger = logging.getLogger(__name__)

router = APIRouter()

class HealthResponse(BaseModel):
    """헬스체크 응답 모델"""
    status: str
    timestamp: str
    services: Dict[str, Any]
    version: str = "1.0.0"

class ServiceStatus(BaseModel):
    """서비스 상태 모델"""
    status: str
    response_time_ms: int
    message: str = None

@router.get("/", response_model=HealthResponse)
async def health_check():
    """전체 시스템 헬스체크"""
    start_time = datetime.utcnow()
    
    try:
        services_status = {}
        overall_status = "healthy"
        
        # 데이터베이스 상태 확인
        try:
            db_start = datetime.utcnow()
            db_status = await db_health_check()
            db_time = int((datetime.utcnow() - db_start).total_seconds() * 1000)
            
            if db_status["postgres"] and db_status["redis"]:
                services_status["database"] = ServiceStatus(
                    status="healthy",
                    response_time_ms=db_time,
                    message="PostgreSQL and Redis connections OK"
                )
            else:
                services_status["database"] = ServiceStatus(
                    status="unhealthy",
                    response_time_ms=db_time,
                    message=f"PostgreSQL: {'OK' if db_status['postgres'] else 'FAIL'}, Redis: {'OK' if db_status['redis'] else 'FAIL'}"
                )
                overall_status = "unhealthy"
                
        except Exception as e:
            services_status["database"] = ServiceStatus(
                status="unhealthy",
                response_time_ms=0,
                message=f"Database check failed: {str(e)}"
            )
            overall_status = "unhealthy"
        
        # AWS Bedrock 상태 확인
        try:
            bedrock_start = datetime.utcnow()
            bedrock_client = get_bedrock_client()
            bedrock_healthy = await bedrock_client.health_check()
            bedrock_time = int((datetime.utcnow() - bedrock_start).total_seconds() * 1000)
            
            if bedrock_healthy:
                services_status["ai_service"] = ServiceStatus(
                    status="healthy",
                    response_time_ms=bedrock_time,
                    message="AWS Bedrock connection OK"
                )
            else:
                services_status["ai_service"] = ServiceStatus(
                    status="unhealthy",
                    response_time_ms=bedrock_time,
                    message="AWS Bedrock connection failed"
                )
                overall_status = "degraded"  # AI 서비스는 중요하지만 전체 서비스는 동작 가능
                
        except Exception as e:
            services_status["ai_service"] = ServiceStatus(
                status="unhealthy",
                response_time_ms=0,
                message=f"AI service check failed: {str(e)}"
            )
            overall_status = "degraded"
        
        return HealthResponse(
            status=overall_status,
            timestamp=datetime.utcnow().isoformat(),
            services=services_status
        )
        
    except Exception as e:
        logger.error(f"헬스체크 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="헬스체크 실행 중 오류가 발생했습니다."
        )

@router.get("/database", response_model=Dict[str, Any])
async def database_health():
    """데이터베이스 상태 확인"""
    try:
        start_time = datetime.utcnow()
        db_status = await db_health_check()
        response_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        return {
            "status": "healthy" if db_status["postgres"] and db_status["redis"] else "unhealthy",
            "response_time_ms": response_time,
            "postgres": db_status["postgres"],
            "redis": db_status["redis"],
            "timestamp": db_status["timestamp"]
        }
        
    except Exception as e:
        logger.error(f"데이터베이스 헬스체크 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="데이터베이스 헬스체크 실행 중 오류가 발생했습니다."
        )

@router.get("/ai", response_model=Dict[str, Any])
async def ai_service_health():
    """AI 서비스 상태 확인"""
    try:
        start_time = datetime.utcnow()
        bedrock_client = get_bedrock_client()
        is_healthy = await bedrock_client.health_check()
        response_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "response_time_ms": response_time,
            "service": "AWS Bedrock",
            "model": bedrock_client.config.model_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"AI 서비스 헬스체크 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="AI 서비스 헬스체크 실행 중 오류가 발생했습니다."
        )

@router.get("/metrics", response_model=Dict[str, Any])
async def system_metrics():
    """시스템 메트릭스"""
    try:
        import psutil
        import os
        
        # CPU 사용률
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # 메모리 사용률
        memory = psutil.virtual_memory()
        
        # 디스크 사용률
        disk = psutil.disk_usage('/')
        
        # 프로세스 정보
        process = psutil.Process(os.getpid())
        
        return {
            "system": {
                "cpu_percent": cpu_percent,
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                    "used": memory.used
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": (disk.used / disk.total) * 100
                }
            },
            "process": {
                "pid": process.pid,
                "memory_info": process.memory_info()._asdict(),
                "cpu_percent": process.cpu_percent(),
                "create_time": process.create_time(),
                "num_threads": process.num_threads()
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except ImportError:
        return {
            "error": "psutil not installed",
            "message": "시스템 메트릭스를 가져올 수 없습니다.",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"시스템 메트릭스 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="시스템 메트릭스 조회 중 오류가 발생했습니다."
        )

@router.get("/version", response_model=Dict[str, str])
async def get_version():
    """API 버전 정보"""
    return {
        "version": "1.0.0",
        "api_name": "부동산 AI 챗봇 API",
        "build_date": "2024-01-15",
        "python_version": "3.11",
        "fastapi_version": "0.104.1"
    }