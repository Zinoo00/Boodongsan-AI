# 🏠 Boodongsan Backend

Korean Real Estate RAG AI Chatbot - Backend API Server

## 🚀 **Quick Start (2분 실행)**

### **Method 1: Docker (권장)**
```bash
# 1. 환경변수 설정
cp .env.example .env
# .env 파일에 필수 API 키들 입력

# 2. Docker로 실행
docker-compose up -d

# 3. 접속 확인  
curl http://localhost:8000/api/v1/health
```

### **Method 2: 로컬 개발**
```bash
# 1. uv 설치 (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 환경변수 및 의존성 설정
cp .env.example .env
# .env 파일에 필수 API 키들 입력
uv sync

# 3. 외부 서비스만 Docker로 시작
docker-compose up -d redis neo4j

# 4. 서버 시작
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

## 🔧 **필수 환경변수 설정**

`.env` 파일에서 다음 항목들을 설정하세요:

### **Required (필수)**
```bash
# AWS Bedrock
AWS_ACCESS_KEY_ID=your_aws_access_key  
AWS_SECRET_ACCESS_KEY=your_aws_secret_key

# Supabase  
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# Cloudflare Workers AI
CLOUDFLARE_ACCOUNT_ID=your_account_id
CLOUDFLARE_API_TOKEN=your_api_token

# 국토교통부 API
MOLIT_API_KEY=your_molit_api_key
```

### **Optional (선택사항)**  
```bash
# Redis (기본값: redis://localhost:6379/0)
REDIS_URL=redis://localhost:6379/0

# AWS OpenSearch
OPENSEARCH_HOST=search-your-domain.ap-northeast-2.es.amazonaws.com
OPENSEARCH_PORT=443
OPENSEARCH_INDEX_NAME=boda_vectors
OPENSEARCH_AUTH_MODE=sigv4

# Seoul Open Data (실시간 도시데이터)
# SEOUL_OPEN_API_KEY=sample

# LightRAG / Neo4j
USE_LIGHTRAG=true
LIGHTRAG_WORKING_DIR=./lightrag_storage
LIGHTRAG_WORKSPACE=boda
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=neo4j
```

## 🆘 **문제 해결**

### **자주 발생하는 문제**

#### **1. 서비스가 시작되지 않을 때**
```bash
# 모든 컨테이너 재시작
docker-compose down && docker-compose up -d

# 로그 확인
docker-compose logs -f backend

# 특정 서비스만 재시작
docker-compose restart redis
```

#### **2. 환경변수 오류**
```bash
# .env 파일 확인
cat .env | grep -v "#" | grep -v "^$"

# 필수 변수가 모두 설정되었는지 확인
python -c "from core.config import settings; print('✅ 설정 완료')"
```

#### **3. 포트 충돌**
```bash
# 포트 사용 확인
lsof -i :8000
netstat -an | grep :8000

# 포트 변경 (docker-compose.yml에서)
# ports: - "8001:8000"
```

#### **4. API 키 오류**
```bash
# AWS 자격증명 테스트
aws sts get-caller-identity

# Supabase 연결 테스트  
curl -H "apikey: YOUR_ANON_KEY" "https://your-project.supabase.co/rest/v1/"
```

---

## 🛠️ **개발 도구**

### **코드 품질 도구**
```bash
# 린트 및 포맷팅
uv run ruff check .
uv run ruff format .

# 타입 체크
uv run mypy .

# 테스트 실행
uv run pytest
```

### **의존성 관리 (uv)**
```bash
# 패키지 추가
uv add fastapi

# 개발 도구 추가
uv add --group dev pytest

# 의존성 업데이트
uv sync --upgrade
```

---

## 🌐 **API Endpoints**

### **Main Endpoints**
- **`GET /`** - API 정보
- **`GET /api/v1/health`** - 헬스체크
- **`GET /api/v1/info`** - 상세 시스템 정보

### **Chat & AI**
- **`POST /api/v1/chat/send`** - 챗봇 대화
- **`GET /api/v1/chat/history/{conversation_id}?user_id=`** - 대화 기록 조회

### **Properties & Policies**  
- **`POST /api/v1/properties/search`** - 부동산 검색
- **`GET /api/v1/properties/{property_id}`** - 매물 상세
- **`POST /api/v1/policies/match`** - 정책 매칭
- **`POST /api/v1/policies/search`** - 정책 검색
- **`GET /api/v1/policies/`** - 정책 목록

### **Users**
- **`GET /api/v1/users/{user_id}/profile`** - 사용자 프로필
- **`GET /api/v1/users/{user_id}/conversations/{conversation_id}`** - 사용자 대화 이력

### **Users**
- **`GET /api/v1/users/{user_id}`** - 사용자 정보
- **`POST /api/v1/users/profile`** - 프로필 생성/수정

### **Documentation**
- **`GET /docs`** - Swagger UI (개발모드)  
- **`GET /redoc`** - ReDoc UI (개발모드)

---

## 🏗️ **Architecture**

```
backend/
├── 📁 ai/               # AI services (AWS Bedrock client)
├── 📁 api/              # FastAPI application & routers  
├── 📁 core/             # Configuration & Supabase/Redis helpers
├── 📁 services/         # Business logic (RAG, LightRAG, DataService 등)
├── 📁 data/             # 데이터 수집 스크립트
├── 📁 docs/             # 백엔드 문서
├── 📁 migrations/       # Supabase / LightRAG SQL 스키마
└── 📄 docker-compose.yml # Multi-service orchestration
```

**Key Services**: FastAPI → Supabase (DB) → Redis (Cache) → AWS OpenSearch (Vectors) → AWS Bedrock (AI) → Seoul City Data (Real-time context)

## 🔧 Configuration

### Environment Variables
Copy `.env.example` to `.env` and configure:

```bash
# Database - Supabase (required)
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_key
SUPABASE_DB_PASSWORD=your_supabase_db_password  # from Supabase Project Settings → Database

# Redis Cache
REDIS_URL=redis://localhost:6379/0

# LightRAG / Neo4j
USE_LIGHTRAG=true
LIGHTRAG_WORKING_DIR=./lightrag_storage
LIGHTRAG_WORKSPACE=boda
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=neo4j

# AWS OpenSearch Vector DB
OPENSEARCH_HOST=search-your-domain.ap-northeast-2.es.amazonaws.com
OPENSEARCH_PORT=443
OPENSEARCH_INDEX_NAME=boda_vectors
OPENSEARCH_AUTH_MODE=sigv4

# AI Services
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
CLOUDFLARE_ACCOUNT_ID=your_cf_account
CLOUDFLARE_API_TOKEN=your_cf_token

# Korean Real Estate APIs
MOLIT_API_KEY=your_molit_key
```

## 🗄️ Database Setup

### Supabase Integration

The application now uses the Supabase Python client library for enhanced database connectivity:

- **Primary Database**: Supabase PostgreSQL via Python client
- **Connection Management**: Automatic retry logic and health monitoring
- **Authentication**: Service role key for server-side operations
- **Real-time capabilities**: Ready for Supabase real-time subscriptions

### uv Configuration Features

The `pyproject.toml` includes comprehensive tool configuration:

- **Ruff**: Fast linting and formatting with Python 3.11+ rules
- **MyPy**: Strict type checking configuration  
- **Pytest**: Async testing setup with coverage
- **Dependency Groups**: Modular installation options

## 🎯 uv Advantages for This Project

1. **⚡ Speed**: 10-100x faster than pip for installation and resolution
2. **🔒 Security**: Built-in lock file ensures reproducible builds  
3. **📦 Modularity**: Dependency groups for feature-based installation
4. **🐍 Python Management**: Built-in Python version management
5. **🔄 Compatibility**: Drop-in replacement for pip/poetry/pipenv
6. **🛠️ Tooling**: Integrated project management commands

## 📊 Performance Optimization

### uv Performance Tips
```bash
# Pre-compiled wheels cache
uv cache clean       # Clear cache if needed
uv cache dir         # Check cache location

# Parallel installations
uv sync --no-cache   # Skip cache for fresh install

# Minimal installs for production
uv sync --no-dev     # Skip development dependencies
```

### Production Deployment
```bash
# Multi-stage Docker builds with uv
FROM python:3.11-slim as builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache

# Runtime stage
FROM python:3.11-slim
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
```

## 🧪 Testing

```bash
# Run all tests
uv run pytest

# With coverage reporting
uv run pytest --cov=backend --cov-report=html

# Run specific test files
uv run pytest tests/test_api.py

# Async test debugging
uv run pytest -v --log-level=DEBUG
```

## 📈 Monitoring

The application includes:
- **Health checks**: `/api/v1/health` with Supabase and Redis status
- **Metrics**: Prometheus metrics on port 9090 (if enabled)
- **Logging**: Structured logging with configurable levels
- **Database monitoring**: Supabase connection health and cache statistics

### Health Check Response
```json
{
  "supabase": {
    "status": true,
    "latency_ms": 45.2
  },
  "redis": {
    "status": true,
    "latency_ms": 12.3,
    "memory_usage": {
      "used_memory": "2.5MB",
      "used_memory_peak": "5.1MB"
    }
  },
  "cache_stats": {
    "hits": 1250,
    "misses": 89,
    "hit_rate_percent": 93.35
  }
}
```

## 📋 Recent Changes

### v1.1.0 - Supabase Integration (Latest)
- **✅ Migration to Supabase Client**: Replaced SQLAlchemy/asyncpg with Supabase Python client
- **✅ Enhanced Connection Management**: Improved error handling and retry logic
- **✅ Service Layer Updates**: All services now use Supabase client operations
- **✅ LangChain Compatibility**: Fixed deprecated import warnings
- **✅ Performance Improvements**: Streamlined database operations and connection pooling

## 🤝 Contributing

1. Install development environment: `uv sync --group dev`
2. Set up pre-commit: `uv run pre-commit install` (if using)
3. Run tests: `uv run pytest`
4. Check code quality: `uv run ruff check .`
5. Format code: `uv run ruff format .`

## 📝 Migration from pip/poetry

If migrating from existing tools:

```bash
# From requirements.txt
uv add $(cat requirements.txt)

# From poetry
# Export pyproject.toml deps, then import to uv

# From pipenv  
# Export Pipfile deps, then import to uv
```

## 🔗 Useful Links

- [uv Documentation](https://docs.astral.sh/uv/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic V2 Migration](https://docs.pydantic.dev/2.0/migration/)
- [Ruff Configuration](https://docs.astral.sh/ruff/configuration/)

---

**Korean Real Estate RAG AI Backend** - Powered by uv for optimal Python package management
