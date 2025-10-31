# BODA - Korean Real Estate RAG AI Chatbot

부동산 매물 추천 및 정부 지원 정책 매칭 AI 챗봇

## 프로젝트 개요

- **RAG**: LightRAG (지식 그래프 기반 RAG)
- **벡터 DB**: NanoVectorDB (LightRAG 기본 내장, 외부 서비스 불필요)
- **지식 그래프**: NetworkX (LightRAG 기본 내장)
- **문서 상태**: JSON (LightRAG 기본 내장)
- **캐시**: Redis
- **AI**: AWS Bedrock (Claude + Titan Embeddings)
- **프론트엔드**: Streamlit
- **OpenAPI**: 국토교통부 (MOLIT), Seoul Open Data

## 빠른 시작

```bash
# 백엔드 설정
cd backend
cp .env.example .env
# .env 파일 편집 (API 키 입력)

# 의존성 설치
uv sync

# 외부 서비스 시작 (Redis only - LightRAG uses embedded storage)
docker-compose up -d redis

# 백엔드 실행
uv run uvicorn api.main:app --reload

# 프론트엔드 실행 (별도 터미널)
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

## 필수 환경 변수

```bash
# LightRAG (uses default NanoVectorDB, NetworkX, JSON)
LIGHTRAG_WORKING_DIR=./lightrag_storage
LIGHTRAG_WORKSPACE=BODA

# AWS Bedrock (AI)
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=ap-northeast-2

# OpenAPI
MOLIT_API_KEY=your_key

# Note: No OpenSearch configuration needed - LightRAG uses embedded storage!
```

## 주요 명령어

```bash
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

- **AIService**: AWS Bedrock (Claude + Titan Embeddings)
- **LightRAGService**: LightRAG 통합 서비스 (NanoVectorDB + NetworkX + JSON)
- **DataService**: 매물/정책 데이터 관리
- **UserService**: 사용자 프로필 및 대화 이력 (JSON 스토리지)
- **RAGService**: RAG 파이프라인 오케스트레이션

### LightRAG 기본 설정

- **Vector DB**: NanoVectorDB (embedded, 외부 서비스 불필요)
- **Graph Storage**: NetworkX (local graph storage)
- **Document Status**: JSON files (local storage)
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

## 문제 해결

### AWS Bedrock 연결 오류
```bash
# AWS 자격증명 확인
aws sts get-caller-identity
```

### LightRAG 오류
```bash
# 작업 디렉토리 초기화
rm -rf ./lightrag_storage
```

### 마이그레이션 노트

이 프로젝트는 OpenSearch에서 LightRAG로 마이그레이션되었습니다:
- **이전**: OpenSearch (외부 벡터 DB) + LightRAG (지식 그래프)
- **현재**: LightRAG만 사용 (NanoVectorDB 내장)
- **장점**:
  - 외부 벡터 DB 서비스 불필요
  - 설정 및 배포 단순화
  - 지식 그래프와 벡터 검색 통합
  - 기본 설정으로 최적화된 성능

## 참고

- Backend API Docs: http://localhost:8000/docs
- Frontend: http://localhost:8501
