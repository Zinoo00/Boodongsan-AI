# BODA - Korean Real Estate RAG AI Chatbot

부동산 매물 추천 및 정부 지원 정책 매칭 AI 챗봇

## 프로젝트 개요

- **RAG**: LightRAG (지식 그래프 기반 RAG)
- **스토리지 백엔드** (설정 가능):
  - **PostgreSQL** (기본값): AWS RDS PostgreSQL + pgvector (프로덕션)
  - **Local**: NanoVectorDB + NetworkX + JSON (개발/테스트)
- **캐시**: Redis
- **AI**: AWS Bedrock (Claude Sonnet 4.5 + Titan Embeddings)
- **프론트엔드**: Streamlit
- **OpenAPI**: 국토교통부 (MOLIT), Seoul Open Data

## 빠른 시작

```bash
# 백엔드 설정
cd backend
cp .env.example .env
# .env 파일 편집 (API 키 및 데이터베이스 설정)

# 의존성 설치
uv sync

# 프로덕션 모드 (PostgreSQL)
# 1. PostgreSQL RDS 인스턴스 생성 및 DATABASE_URL 설정
# 2. 외부 서비스 시작 (Redis)
docker-compose up -d redis

# 3. 데이터베이스 마이그레이션
uv run alembic upgrade head

# 4. 백엔드 실행
uv run uvicorn api.main:app --reload

# 개발 모드 (Local Storage)
# .env에서 STORAGE_BACKEND=local 설정
# 또는 환경 변수로 실행:
STORAGE_BACKEND=local uv run uvicorn api.main:app --reload

# 프론트엔드 실행 (별도 터미널)
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

## Claude Sonnet 4.5 주요 기능

**Inference Profile ID**: `global.anthropic.claude-sonnet-4-5-20250929-v1:0` (권장)

### 핵심 특징

- **최고 성능**: Anthropic의 가장 지능적인 모델 (2025년 9월 출시)
- **코딩 최적화**: 복잡한 에이전트 작업과 코딩에 특화
- **확장된 컨텍스트**:
  - 기본: 200,000 토큰 (~150,000 단어, ~500페이지)
  - 확장: 1,000,000 토큰 (프리뷰, beta 헤더 필요)
- **비용 효율**: 성능과 속도, 비용의 최적 균형
- **장문 작업**: 대규모 코드 분석, 문서 합성, 다단계 워크플로우 지원

### 중요: Inference Profile 사용 필수

Claude Sonnet 4.5는 **직접 모델 ID 호출이 불가능**하며, 반드시 **Inference Profile**을 통해 호출해야 합니다.

**Inference Profile 종류**:

- **Global** (`global.*`): 모든 AWS 상용 리전으로 자동 라우팅 (권장 - 최상의 가용성)
- **APAC** (`apac.*`): Asia-Pacific 지역 내에서만 라우팅
- **US** (`us.*`): 미국 리전으로만 라우팅
- **EU** (`eu.*`): 유럽 리전으로만 라우팅
- **Japan** (`jp.*`): 일본 리전으로만 라우팅
- **Australia** (`au.*`): 호주 리전으로만 라우팅

**Cross-Region Inference 장점**:

- 트래픽 급증 시 자동 부하 분산
- 높은 처리량(throughput) 달성
- 복잡한 로드 밸런싱 불필요
- AWS 보안 네트워크 내 암호화된 데이터 전송

### 주요 활용 사례

- 부동산 매물 데이터 분석 및 추천
- 정부 정책 매칭 및 상담
- 복잡한 사용자 질의 처리
- 대화 이력 기반 컨텍스트 유지
- RAG 기반 지식 그래프 질의

## 필수 환경 변수

```bash
# Storage Backend (선택 가능)
STORAGE_BACKEND=postgresql  # "postgresql" (기본값) 또는 "local"

# PostgreSQL Database (프로덕션 - STORAGE_BACKEND=postgresql인 경우 필수)
DATABASE_URL=postgresql+asyncpg://username:password@host:port/database

# LightRAG Configuration
LIGHTRAG_WORKING_DIR=./lightrag_storage
LIGHTRAG_WORKSPACE=BODA

# AWS Bedrock (AI) - Claude Sonnet 4.5
# IMPORTANT: Use inference profile ID (not direct model ID)
# Global profile recommended for best availability
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=ap-northeast-2
BEDROCK_MODEL_ID=global.anthropic.claude-sonnet-4-5-20250929-v1:0

# OpenAPI
MOLIT_API_KEY=your_key
```

## 주요 명령어

```bash
# 데이터베이스 관리 (PostgreSQL 모드)
uv run python scripts/db_setup.py init      # 데이터베이스 초기화
uv run python scripts/db_setup.py migrate   # 마이그레이션 실행
uv run python scripts/db_setup.py status    # 마이그레이션 상태 확인
uv run python scripts/db_setup.py info      # 데이터베이스 설정 정보
uv run python scripts/db_setup.py reset     # 데이터베이스 리셋 (주의!)

# Alembic 마이그레이션
uv run alembic revision --autogenerate -m "migration message"
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic current

# 코드 품질 검사
uv run ruff check .
uv run ruff format .

# 테스트
uv run pytest

# Docker로 전체 실행
docker-compose up
```

## 아키텍처

### 데이터 흐름

**프로덕션 모드 (PostgreSQL)**:

```
사용자 쿼리
  → Streamlit Frontend
  → FastAPI Backend
  → LightRAG (지식 그래프 + 벡터 검색 통합)
    - AWS RDS PostgreSQL + pgvector (vector search)
    - PostgreSQL JSONB (graph relations)
    - AWS Bedrock (embeddings & LLM)
  → PostgreSQL (대화 이력 저장)
  → 사용자에게 응답 반환
```

**개발 모드 (Local)**:

```
사용자 쿼리
  → Streamlit Frontend
  → FastAPI Backend
  → LightRAG (지식 그래프 + 벡터 검색 통합)
    - NanoVectorDB (embedded vector search)
    - NetworkX (knowledge graph)
    - AWS Bedrock (embeddings & LLM)
  → JSON Storage (대화 이력 저장)
  → 사용자에게 응답 반환
```

### 주요 서비스

- **AIService**: AWS Bedrock (Claude Sonnet 4.5 + Titan Embeddings)
- **LightRAGService**: LightRAG 통합 서비스 (Storage Backend 선택 가능)
- **StorageBackend**: Storage 추상화 레이어
  - **PostgreSQLBackend**: AWS RDS PostgreSQL + pgvector
  - **LocalBackend**: NanoVectorDB + NetworkX + JSON
- **DataService**: 매물/정책 데이터 관리
- **UserService**: 사용자 프로필 및 대화 이력
- **RAGService**: RAG 파이프라인 오케스트레이션

### Storage Backend 설정

**PostgreSQL Backend (기본값, 프로덕션)**:

- **Vector Search**: pgvector extension (cosine similarity)
- **Graph Storage**: PostgreSQL JSONB + recursive queries
- **Document Status**: PostgreSQL tables
- **Scalability**: 수백만 벡터 지원
- **Performance**: 인덱스 최적화, 연결 풀링

**Local Backend (개발/테스트)**:

- **Vector DB**: NanoVectorDB (embedded, 외부 서비스 불필요)
- **Graph Storage**: NetworkX (local graph storage)
- **Document Status**: JSON files (local storage)
- **Simplicity**: 설정 없이 즉시 사용 가능

**공통 설정**:

- **Chunk Size**: 1200 tokens (default)
- **Embedding Batch**: 32 (default)
- **Query Modes**: hybrid, local, global, naive

## 개발 가이드

### 새 기능 추가

1. `backend/services/` - 비즈니스 로직
2. `backend/api/routers/` - API 엔드포인트
3. `frontend/components/` - UI 컴포넌트

### 코드 스타일

- 주석: 한국어
- 함수/변수명: 영어
- Docstring: 한국어
- Emoji 사용 최소화
- 사용자가 요청하지 않는 이상 요약 문서 작업 X

## 문제 해결

### AWS Bedrock 연결 오류

```bash
# AWS 자격증명 확인
aws sts get-caller-identity
```

### PostgreSQL 연결 오류

```bash
# 데이터베이스 연결 확인
psql $DATABASE_URL

# 마이그레이션 상태 확인
uv run alembic current

# 마이그레이션 재실행
uv run alembic upgrade head
```

### Local Storage 초기화

```bash
# 로컬 작업 디렉토리 초기화
rm -rf ./lightrag_storage
```

### Storage Backend 전환

```bash
# PostgreSQL → Local
# .env에서 STORAGE_BACKEND=local 설정 후 재시작

# Local → PostgreSQL
# .env에서 STORAGE_BACKEND=postgresql 설정
# DATABASE_URL 설정 필수
uv run alembic upgrade head  # 마이그레이션 실행
# 재시작
```

### 마이그레이션 노트

이 프로젝트는 다음과 같이 진화했습니다:

- **Phase 1**: OpenSearch (외부 벡터 DB) + LightRAG (지식 그래프)
- **Phase 2**: LightRAG 단독 (NanoVectorDB 내장)
- **Phase 3 (현재)**: Storage Backend 추상화
  - **기본값**: AWS RDS PostgreSQL + pgvector (프로덕션)
  - **개발**: NanoVectorDB + NetworkX + JSON (로컬)
- **장점**:
  - 개발/프로덕션 환경 분리
  - PostgreSQL로 확장성 및 성능 향상
  - Local backend로 빠른 개발 및 테스트
  - 통일된 인터페이스로 쉬운 전환

## Storage Backend 시스템

### 개요

BODA는 유연한 storage backend 시스템을 제공합니다:

- **PostgreSQL** (기본값): AWS RDS PostgreSQL + pgvector

  - 프로덕션 환경 권장
  - 수백만 벡터 지원
  - 고성능 벡터 검색

- **Local**: NanoVectorDB + NetworkX + JSON
  - 개발/테스트 환경
  - 설정 없이 즉시 사용
  - 빠른 프로토타이핑

### 빠른 전환

```bash
# PostgreSQL로 전환
./scripts/switch_storage.sh postgresql

# Local로 전환
./scripts/switch_storage.sh local
```

### 상세 문서

- [Storage Backend 가이드](backend/STORAGE.md) - 전체 가이드
- [구현 요약](backend/IMPLEMENTATION_SUMMARY.md) - 기술 세부사항
- [빠른 참조](backend/QUICK_REFERENCE.md) - 치트시트

### 시스템 요구사항 확인

```bash
# 현재 시스템 요구사항 확인
uv run python scripts/check_requirements.py
```

## 참고

- Backend API Docs: http://localhost:8000/docs
- Frontend: http://localhost:8501
- Storage Documentation: backend/STORAGE.md
