"""
Core configuration module for Korean Real Estate RAG AI Chatbot
Environment variables and application settings management
"""

import os
import secrets
from typing import List, Optional, Any, Dict, Union
from pydantic import BaseSettings, validator, AnyHttpUrl, Field, SecretStr, HttpUrl
from pydantic.env_settings import SettingsSourceCallable
from enum import Enum
import logging


class Environment(str, Enum):
    """Application environment"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Logging levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """Application settings with comprehensive validation"""
    
    # Application
    APP_NAME: str = Field(
        default="Korean Real Estate RAG AI Chatbot",
        description="Application name"
    )
    APP_VERSION: str = Field(
        default="1.0.0",
        regex=r'^\d+\.\d+\.\d+$',
        description="Semantic version"
    )
    API_V1_STR: str = Field(
        default="/api/v1",
        regex=r'^/api/v\d+$',
        description="API version prefix"
    )
    SECRET_KEY: SecretStr = Field(
        default_factory=lambda: SecretStr(secrets.token_urlsafe(32)),
        min_length=32,
        description="Application secret key"
    )
    ENVIRONMENT: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Runtime environment"
    )
    DEBUG: bool = Field(
        default=False,
        description="Debug mode flag"
    )
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1
    LOG_LEVEL: LogLevel = LogLevel.INFO
    
    # Security
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30  # 30 days
    ALGORITHM: str = "HS256"
    JWT_SECRET_KEY: str = secrets.token_urlsafe(32)
    JWT_REFRESH_SECRET_KEY: str = secrets.token_urlsafe(32)
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []
    
    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    # Database - Supabase PostgreSQL
    SUPABASE_URL: HttpUrl = Field(
        ...,
        description="Supabase project URL"
    )
    SUPABASE_ANON_KEY: SecretStr = Field(
        ...,
        min_length=20,
        description="Supabase anonymous key"
    )
    SUPABASE_SERVICE_ROLE_KEY: SecretStr = Field(
        ...,
        min_length=20,
        description="Supabase service role key"
    )
    DATABASE_URL: Optional[str] = Field(
        default=None,
        description="Direct PostgreSQL connection URL"
    )
    
    @validator("DATABASE_URL", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        if isinstance(v, str) and v:
            return v
        
        # Construct from Supabase credentials
        supabase_url = values.get("SUPABASE_URL")
        service_key = values.get("SUPABASE_SERVICE_ROLE_KEY")
        
        if supabase_url and service_key:
            # Extract host from Supabase URL
            if isinstance(supabase_url, str):
                host = supabase_url.replace("https://", "").replace("http://", "")
            else:
                host = str(supabase_url).replace("https://", "").replace("http://", "")
            
            # Get secret value if it's SecretStr
            key_value = service_key.get_secret_value() if hasattr(service_key, 'get_secret_value') else service_key
            
            return f"postgresql+asyncpg://postgres:{key_value}@db.{host}:5432/postgres"
        
        # Fallback for development
        return "postgresql+asyncpg://postgres:password@localhost:5432/boodongsan"
    
    # Redis Cache
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: Optional[str] = None
    CACHE_TTL: int = 3600  # 1 hour
    
    # Vector Database - Qdrant
    QDRANT_URL: HttpUrl = Field(
        ...,
        description="Qdrant server URL"
    )
    QDRANT_API_KEY: SecretStr = Field(
        ...,
        min_length=10,
        description="Qdrant API key"
    )
    QDRANT_COLLECTION_NAME: str = Field(
        default="korean_real_estate",
        regex=r'^[a-z0-9_]+$',
        description="Qdrant collection name"
    )
    VECTOR_SIZE: int = Field(
        default=768,
        ge=128,
        le=4096,
        description="Vector embedding size"
    )
    
    # AI Services - AWS Bedrock
    AWS_ACCESS_KEY_ID: str = Field(
        ...,
        min_length=16,
        max_length=32,
        description="AWS access key ID"
    )
    AWS_SECRET_ACCESS_KEY: SecretStr = Field(
        ...,
        min_length=32,
        description="AWS secret access key"
    )
    AWS_REGION: str = Field(
        default="us-east-1",
        regex=r'^[a-z]{2}-[a-z]+-\d{1}$',
        description="AWS region"
    )
    BEDROCK_MODEL_ID: str = Field(
        default="anthropic.claude-3-sonnet-20240229-v1:0",
        description="AWS Bedrock model ID"
    )
    BEDROCK_EMBEDDING_MODEL_ID: str = Field(
        default="amazon.titan-embed-text-v1",
        description="AWS Bedrock embedding model ID"
    )
    
    # AI Services - Cloudflare Workers AI
    CLOUDFLARE_ACCOUNT_ID: str = Field(
        ...,
        min_length=32,
        max_length=32,
        description="Cloudflare account ID"
    )
    CLOUDFLARE_API_TOKEN: SecretStr = Field(
        ...,
        min_length=20,
        description="Cloudflare API token"
    )
    CLOUDFLARE_MODEL_NAME: str = Field(
        default="@cf/meta/llama-2-7b-chat-int8",
        description="Cloudflare Workers AI model name"
    )
    
    # Korean Real Estate APIs
    MOLIT_API_KEY: str  # 국토교통부 API
    HUG_API_KEY: Optional[str] = None  # 주택도시보증공사 API
    HF_API_KEY: Optional[str] = None  # 주택금융공사 API
    
    # Data Collection
    DATA_UPDATE_INTERVAL_HOURS: int = 24
    MAX_CONCURRENT_REQUESTS: int = 10
    REQUEST_TIMEOUT_SECONDS: int = 30
    
    # RAG Configuration
    MAX_SEARCH_RESULTS: int = 10
    SIMILARITY_THRESHOLD: float = 0.7
    MAX_CONTEXT_LENGTH: int = 4000
    RESPONSE_MAX_TOKENS: int = 1000
    
    # Performance
    MAX_WORKERS: int = Field(
        default=4,
        ge=1,
        le=32,
        description="Maximum worker processes"
    )
    WORKER_TIMEOUT: int = Field(
        default=120,
        ge=30,
        le=3600,
        description="Worker timeout in seconds"
    )
    DB_POOL_SIZE: int = Field(
        default=10,
        ge=5,
        le=50,
        description="Database connection pool size"
    )
    DB_MAX_OVERFLOW: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Database connection pool overflow"
    )
    
    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    LOG_FILE_PATH: Optional[str] = None
    
    # File Storage
    UPLOAD_MAX_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_FILE_TYPES: List[str] = ["csv", "xlsx", "json"]
    
    @validator("DEBUG", pre=True)
    def parse_debug(cls, v: Any) -> bool:
        """Parse debug flag from various input types"""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on")
        return bool(v)
    
    @validator("*", pre=True)
    def validate_required_in_production(cls, v: Any, field: Any, values: Dict[str, Any]) -> Any:
        """Ensure required fields are set in production"""
        env = values.get("ENVIRONMENT", Environment.DEVELOPMENT)
        
        # Critical fields that must be set in production
        production_required = {
            "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY",
            "QDRANT_URL", "QDRANT_API_KEY", "AWS_ACCESS_KEY_ID", 
            "AWS_SECRET_ACCESS_KEY", "CLOUDFLARE_ACCOUNT_ID", 
            "CLOUDFLARE_API_TOKEN", "MOLIT_API_KEY"
        }
        
        if (env == Environment.PRODUCTION and 
            field.name in production_required and 
            (v is None or v == "")):
            raise ValueError(f"{field.name} is required in production environment")
        
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        allow_population_by_field_name = True
        validate_assignment = True
        
        # Custom source for better error messages
        @classmethod
        def customise_sources(
            cls,
            init_settings: SettingsSourceCallable,
            env_settings: SettingsSourceCallable,
            file_secret_settings: SettingsSourceCallable,
        ) -> tuple[SettingsSourceCallable, ...]:
            return (
                init_settings,
                env_settings,
                file_secret_settings,
            )
    
    def get_secret_value(self, field_name: str) -> str:
        """Safely get secret value from SecretStr fields"""
        value = getattr(self, field_name)
        if hasattr(value, 'get_secret_value'):
            return value.get_secret_value()
        return str(value)


class TestSettings(Settings):
    """Test environment settings"""
    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/test_boodongsan"
    REDIS_URL: str = "redis://localhost:6379/1"  # Different Redis DB for tests
    DEBUG: bool = True


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings"""
    return settings


# Environment-specific configurations
ENVIRONMENT_CONFIGS = {
    Environment.DEVELOPMENT: {
        "reload": True,
        "debug": True,
        "log_level": "debug",
    },
    Environment.STAGING: {
        "reload": False,
        "debug": False,
        "log_level": "info",
    },
    Environment.PRODUCTION: {
        "reload": False,
        "debug": False,
        "log_level": "warning",
    },
}


def get_environment_config() -> Dict[str, Any]:
    """Get environment-specific configuration"""
    return ENVIRONMENT_CONFIGS.get(settings.ENVIRONMENT, ENVIRONMENT_CONFIGS[Environment.DEVELOPMENT])


# API Rate Limiting
RATE_LIMIT_CONFIG = {
    "default": "100/minute",
    "chat": "30/minute",
    "search": "50/minute",
    "upload": "5/minute",
}


# Logging configuration
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
        "detailed": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - %(funcName)s - %(message)s",
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "formatter": "detailed",
            "class": "logging.FileHandler",
            "filename": settings.LOG_FILE_PATH or "app.log",
        },
    },
    "root": {
        "level": settings.LOG_LEVEL.value,
        "handlers": ["default"] + (["file"] if settings.LOG_FILE_PATH else []),
    },
}