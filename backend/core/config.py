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

    # Vector / RAG
    OPENSEARCH_HOST: str = "localhost"
    OPENSEARCH_PORT: int = 9200
    OPENSEARCH_USE_SSL: bool = False
    OPENSEARCH_VERIFY_CERTS: bool = False
    OPENSEARCH_AUTH_MODE: str = "none"
    OPENSEARCH_USERNAME: str | None = None
    OPENSEARCH_PASSWORD: str | None = None
    OPENSEARCH_INDEX_NAME: str = "boda_vectors"
    OPENSEARCH_TEXT_FIELD: str = "text"
    OPENSEARCH_VECTOR_FIELD: str = "embedding"
    OPENSEARCH_METADATA_FIELD: str = "metadata"
    OPENSEARCH_SHARDS: int = 1
    OPENSEARCH_REPLICAS: int = 0
    OPENSEARCH_KNN_ENGINE: str = "faiss"
    OPENSEARCH_KNN_SPACE_TYPE: str = "cosinesimil"
    VECTOR_SIZE: int = 1536
    MAX_SEARCH_RESULTS: int = 10
    RESPONSE_MAX_TOKENS: int = 1000

    # AI
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-northeast-2"
    BEDROCK_MODEL_ID: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    BEDROCK_EMBEDDING_MODEL_ID: str = "amazon.titan-embed-text-v1"

    # External APIs
    MOLIT_API_KEY: str = ""
    HUG_API_KEY: str | None = None
    HF_API_KEY: str | None = None
    SEOUL_OPEN_API_KEY: str | None = None

    # LightRAG / Storage
    USE_LIGHTRAG: bool = False
    LIGHTRAG_WORKING_DIR: str = "./lightrag_storage"
    LIGHTRAG_WORKSPACE: str = "boda"

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
