"""
Core configuration module for Korean Real Estate RAG AI Chatbot
Environment variables and application settings management
"""

import os
import secrets
from enum import Enum
from typing import Any
from urllib.parse import urlparse

from pydantic import AnyHttpUrl, Field, HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
        default="Korean Real Estate RAG AI Chatbot", description="Application name"
    )
    APP_VERSION: str = Field(
        default="1.0.0", pattern=r"^\d+\.\d+\.\d+$", description="Semantic version"
    )
    API_V1_STR: str = Field(
        default="/api/v1", pattern=r"^/api/v\d+$", description="API version prefix"
    )
    SECRET_KEY: SecretStr = Field(
        default_factory=lambda: SecretStr(secrets.token_urlsafe(32)),
        min_length=32,
        description="Application secret key",
    )
    ENVIRONMENT: Environment = Field(
        default=Environment.DEVELOPMENT, description="Runtime environment"
    )
    DEBUG: bool = Field(default=False, description="Debug mode flag")

    # Server - Uvicorn Configuration
    HOST: str = Field(default="0.0.0.0", description="Server host address")
    PORT: int = Field(default=8000, ge=1, le=65535, description="Server port")
    WORKERS: int = Field(default=1, ge=1, le=32, description="Number of worker processes")
    LOG_LEVEL: LogLevel = LogLevel.INFO
    RELOAD: bool = Field(default=False, description="Enable auto-reload for development")

    # ASGI Server Selection
    ASGI_SERVER: str = Field(
        default="uvicorn", description="ASGI server to use (uvicorn recommended per architecture)"
    )

    # Security
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30  # 30 days
    ALGORITHM: str = "HS256"
    JWT_SECRET_KEY: str = Field(
        default_factory=lambda: os.getenv("JWT_SECRET_KEY") or secrets.token_urlsafe(32),
        min_length=32,
        description="JWT signing key - must be consistent across restarts",
    )
    JWT_REFRESH_SECRET_KEY: str = Field(
        default_factory=lambda: os.getenv("JWT_REFRESH_SECRET_KEY") or secrets.token_urlsafe(32),
        min_length=32,
        description="JWT refresh signing key - must be consistent across restarts",
    )

    # Production security
    ALLOWED_HOSTS: list[str] = Field(
        default_factory=list, description="Allowed hosts for TrustedHostMiddleware"
    )

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def assemble_allowed_hosts(cls, v: Any) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        return []

    # CORS
    BACKEND_CORS_ORIGINS: list[AnyHttpUrl] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> list[str]:
        if v is None or v == "":
            return []
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return []

    # Database - Supabase PostgreSQL
    SUPABASE_URL: HttpUrl = Field(..., description="Supabase project URL")
    SUPABASE_ANON_KEY: SecretStr = Field(..., min_length=20, description="Supabase anonymous key")
    SUPABASE_SERVICE_ROLE_KEY: SecretStr = Field(
        ..., min_length=20, description="Supabase service role key"
    )
    SUPABASE_DB_PASSWORD: SecretStr | None = Field(
        default=None, description="Supabase Postgres DB password (not the service key)"
    )
    DATABASE_URL: str | None = Field(default=None, description="Direct PostgreSQL connection URL")
    
    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: str | None, info) -> str:
        values = info.data if hasattr(info, "data") else {}
        if isinstance(v, str) and v:
            return v

        # Construct from Supabase credentials
        supabase_url = values.get("SUPABASE_URL")
        service_key = values.get("SUPABASE_SERVICE_ROLE_KEY")
        db_password = values.get("SUPABASE_DB_PASSWORD")

        # Prefer DB password if available, fallback to service key
        if supabase_url and (db_password or service_key):
            # Derive db.<project-ref>.supabase.co from SUPABASE_URL
            parsed = urlparse(str(supabase_url))
            hostname = parsed.hostname or str(supabase_url).replace("https://", "").replace("http://", "")
            host = hostname if hostname.startswith("db.") else f"db.{hostname}"

            # Use DB password if available, otherwise use service key
            if db_password:
                pw_value = (
                    db_password.get_secret_value()
                    if hasattr(db_password, "get_secret_value")
                    else str(db_password)
                )
            else:
                pw_value = (
                    service_key.get_secret_value()
                    if hasattr(service_key, "get_secret_value")
                    else str(service_key)
                )

            # Build asyncpg URL; SSL is enforced via connect_args in engine creation
            return f"postgresql+asyncpg://postgres:{pw_value}@{host}:5432/postgres"
        
        # Fallback for development
        return "postgresql+asyncpg://postgres:password@localhost:5432/boodongsan"

    # Redis Cache
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: str | None = None
    CACHE_TTL: int = 3600  # 1 hour

    # Vector Database - Chromadb (Primary) & Qdrant (Legacy)
    # Chromadb Configuration
    CHROMADB_HOST: str = Field(default="localhost", description="Chromadb server host")
    CHROMADB_PORT: int = Field(default=8000, ge=1, le=65535, description="Chromadb server port")
    CHROMADB_COLLECTION_NAME: str = Field(
        default="korean_real_estate",
        pattern=r"^[a-zA-Z0-9_]+$",
        description="Chromadb collection name",
    )

    # Qdrant Configuration (Legacy support)
    QDRANT_URL: HttpUrl | None = Field(
        default=None, description="Qdrant server URL (optional for legacy support)"
    )
    QDRANT_API_KEY: SecretStr | None = Field(
        default=None, description="Qdrant API key (optional for legacy support)"
    )
    QDRANT_COLLECTION_NAME: str = Field(
        default="korean_real_estate", pattern=r"^[a-z0-9_]+$", description="Qdrant collection name"
    )
    VECTOR_SIZE: int = Field(default=768, ge=128, le=4096, description="Vector embedding size")

    # AI Services - AWS Bedrock
    AWS_ACCESS_KEY_ID: str = Field(
        ..., min_length=16, max_length=32, description="AWS access key ID"
    )
    AWS_SECRET_ACCESS_KEY: SecretStr = Field(
        ..., min_length=32, description="AWS secret access key"
    )
    AWS_REGION: str = Field(
        default="ap-northeast-2", pattern=r"^[a-z]{2}-[a-z]+-\d{1}$", description="AWS region"
    )
    BEDROCK_MODEL_ID: str = Field(
        default="anthropic.claude-3-sonnet-20240229-v1:0", description="AWS Bedrock model ID"
    )
    BEDROCK_EMBEDDING_MODEL_ID: str = Field(
        default="amazon.titan-embed-text-v1", description="AWS Bedrock embedding model ID"
    )

    # AI Services - Cloudflare Workers AI
    CLOUDFLARE_ACCOUNT_ID: str = Field(
        ..., min_length=32, max_length=32, description="Cloudflare account ID"
    )
    CLOUDFLARE_API_TOKEN: SecretStr = Field(..., min_length=20, description="Cloudflare API token")
    CLOUDFLARE_MODEL_NAME: str = Field(
        default="@cf/meta/llama-2-7b-chat-int8", description="Cloudflare Workers AI model name"
    )

    # Korean Real Estate APIs
    MOLIT_API_KEY: str  # 국토교통부 API
    HUG_API_KEY: str | None = None  # 주택도시보증공사 API
    HF_API_KEY: str | None = None  # 주택금융공사 API

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
    MAX_WORKERS: int = Field(default=4, ge=1, le=32, description="Maximum worker processes")
    WORKER_TIMEOUT: int = Field(
        default=120, ge=30, le=3600, description="Worker timeout in seconds"
    )
    DB_POOL_SIZE: int = Field(default=10, ge=5, le=50, description="Database connection pool size")
    DB_MAX_OVERFLOW: int = Field(
        default=20, ge=0, le=100, description="Database connection pool overflow"
    )

    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    LOG_FILE_PATH: str | None = None

    # File Storage
    UPLOAD_MAX_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_FILE_TYPES: list[str] = ["csv", "xlsx", "json"]

    @field_validator("ALLOWED_FILE_TYPES", mode="before")
    @classmethod
    def assemble_file_types(cls, v: Any) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        return ["csv", "xlsx", "json"]

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v: Any) -> bool:
        """Parse debug flag from various input types"""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on")
        return bool(v)

    @field_validator("*", mode="before")
    @classmethod
    def validate_required_in_production(cls, v: Any, info) -> Any:
        field = info.field_name if hasattr(info, "field_name") else None
        values = info.data if hasattr(info, "data") else {}
        """Ensure required fields are set in production"""
        env = values.get("ENVIRONMENT", Environment.DEVELOPMENT)

        # Critical fields that must be set in production
        production_required = {
            "SUPABASE_URL",
            "SUPABASE_ANON_KEY",
            "SUPABASE_SERVICE_ROLE_KEY",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "CLOUDFLARE_ACCOUNT_ID",
            "CLOUDFLARE_API_TOKEN",
            "MOLIT_API_KEY",
        }

        if (
            env == Environment.PRODUCTION
            and field in production_required
            and (v is None or v == "")
        ):
            raise ValueError(f"{field} is required in production environment")

        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        validate_assignment=True,
        extra="forbid",
        env_parse_none_str="",  # Treat empty strings as None
        json_schema_extra={"additionalProperties": False}
    )

    def get_secret_value(self, field_name: str) -> str:
        """Safely get secret value from SecretStr fields"""
        value = getattr(self, field_name)
        if hasattr(value, "get_secret_value"):
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


def get_environment_config() -> dict[str, Any]:
    """Get environment-specific configuration"""
    base_config = {
        "reload": settings.RELOAD,
        "debug": settings.DEBUG,
        "log_level": settings.LOG_LEVEL.value.lower(),
        "workers": settings.WORKERS,
        "host": settings.HOST,
        "port": settings.PORT,
    }

    # Environment-specific overrides
    if settings.ENVIRONMENT == Environment.DEVELOPMENT:
        base_config.update({"reload": True, "debug": True, "log_level": "debug"})
    elif settings.ENVIRONMENT == Environment.STAGING:
        base_config.update({"reload": False, "debug": False, "log_level": "info"})
    elif settings.ENVIRONMENT == Environment.PRODUCTION:
        base_config.update({"reload": False, "debug": False, "log_level": "warning"})

    return base_config


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
