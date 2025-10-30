# BODA - Korean Real Estate RAG AI Chatbot

부동산 매물 추천 및 정부 지원 정책 매칭 AI 챗봇

## 프로젝트 개요

- **벡터 DB**: OpenSearch (k-NN 검색)
- **지식 그래프/사용자 데이터**: LightRAG 로컬 스토리지 (NetworkX + JSON)
- **캐시**: Redis
- **AI**: AWS Bedrock (Claude)
- **RAG**: LightRAG (지식 그래프 기반)
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

# 외부 서비스 시작 (Redis, OpenSearch)
docker-compose up -d redis opensearch

# 백엔드 실행
uv run uvicorn api.main:app --reload

# 프론트엔드 실행 (별도 터미널)
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

## 필수 환경 변수

```bash
# LightRAG storage
LIGHTRAG_WORKING_DIR=./lightrag_storage
LIGHTRAG_WORKSPACE=BODA

# OpenSearch (로컬 Docker)
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200
OPENSEARCH_AUTH_MODE=none

# AWS Bedrock (AI)
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=ap-northeast-2

# OpenAPI
MOLIT_API_KEY=your_key
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
  → LightRAG (로컬 지식 그래프 + NanoVectorDB)
  → OpenSearch (벡터 유사도 검색)
  → AWS Bedrock (응답 생성)
  → JSON Storage (대화 이력 저장)
  → 사용자에게 응답 반환
```

### 주요 서비스

- **AIService**: AWS Bedrock (Claude)
- **LightRAGService**: LightRAG 기본 스토리지 (NetworkX/NanoVectorDB)
- **OpenSearchVectorService**: 벡터 검색
- **DataService**: 매물/정책 데이터 관리
- **UserService**: 사용자 프로필 및 대화 이력 (JSON 스토리지)
- **RAGService**: RAG 파이프라인 오케스트레이션

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

### OpenSearch 연결 오류
```bash
# AWS 자격증명 확인
aws sts get-caller-identity
```

### LightRAG 오류
```bash
# 작업 디렉토리 초기화
rm -rf ./lightrag_storage
```

## 참고

- Backend API Docs: http://localhost:8000/docs
- Frontend: http://localhost:8501
