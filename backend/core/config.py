"""
Simplified application configuration for the Korean Real Estate RAG AI Chatbot.
"""

from typing import Any

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Minimal settings without additional validation or fallbacks."""

    # Application
    APP_NAME: str = "Korean Real Estate RAG AI Chatbot"
    APP_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "dev-secret"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1
    RELOAD: bool = True
    LOG_LEVEL: str = "INFO"
    ASGI_SERVER: str = "uvicorn"

    # HTTP
    BACKEND_CORS_ORIGINS: list[str] = []
    ALLOWED_HOSTS: list[str] = []

    # Cache
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: str | None = None
    CACHE_TTL: int = 3600

    # RAG
    MAX_SEARCH_RESULTS: int = 10
    RESPONSE_MAX_TOKENS: int = 1000

    # AI
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-northeast-2"
    # Claude Sonnet 4.5 (released September 2025)
    # Regional endpoint for APAC region (recommended for ap-northeast-2)
    BEDROCK_MODEL_ID: str = "anthropic.claude-sonnet-4-5-20250929-v1:0"
    # Alternative global endpoint: "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
    # Alternative APAC-specific: "apac.anthropic.claude-sonnet-4-5-20250929-v1:0"
    BEDROCK_EMBEDDING_MODEL_ID: str = "amazon.titan-embed-text-v1"

    # External APIs
    MOLIT_API_KEY: str = ""
    HUG_API_KEY: str | None = None
    HF_API_KEY: str | None = None
    SEOUL_OPEN_API_KEY: str | None = None

    # LightRAG - Knowledge Graph RAG with Default Settings
    # Uses NanoVectorDB (embedded), NetworkX (graph), JSON (doc status)
    LIGHTRAG_WORKING_DIR: str = "./lightrag_storage"
    LIGHTRAG_WORKSPACE: str = "BODA"
    LIGHTRAG_EMBEDDING_DIM: int = 1536

    # LightRAG uses default settings:
    # - Vector DB: NanoVectorDB (embedded, no external service)
    # - Graph Storage: NetworkX (local graph storage)
    # - Document Status: JSON files (local storage)
    # - Chunk size: 1200 tokens
    # - Embedding batch size: 32

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"

    def get_secret_value(self, field_name: str) -> str:
        value = getattr(self, field_name, "")
        if value is None:
            return ""
        return str(value)


settings = Settings()


def get_settings() -> Settings:
    return settings


def get_environment_config() -> dict[str, Any]:
    return {
        "reload": settings.RELOAD,
        "debug": settings.DEBUG,
        "log_level": settings.LOG_LEVEL.lower(),
        "workers": settings.WORKERS,
        "host": settings.HOST,
        "port": settings.PORT,
    }
