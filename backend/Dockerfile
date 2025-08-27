FROM ghcr.io/astral-sh/uv:python3.11-bookworm

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 메타데이터만 먼저 복사 (캐시 최적화)
COPY pyproject.toml ./

# 프로덕션 의존성 설치 (격리된 .venv에 설치)
RUN uv sync --frozen --no-dev

# 애플리케이션 코드 복사
COPY . .

# 포트 노출
EXPOSE 8000

# 애플리케이션 실행 (uv 런타임 사용)
CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]