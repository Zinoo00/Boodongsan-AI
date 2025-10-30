# 🏠 BODA - Korean Real Estate RAG AI Chatbot

부동산 매물 추천 및 정부 지원 정책 매칭 AI 챗봇

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116-green.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.38-red.svg)](https://streamlit.io/)

## ✨ 주요 기능

- 🤖 **AI 기반 대화형 부동산 상담**
- 🏘️ **맞춤형 매물 추천** (벡터 유사도 검색)
- 📋 **정부 지원 정책 매칭** (자격 조건 자동 분석)
- 🔍 **실시간 시장 정보** (국토교통부 OpenAPI)
- 💬 **대화 이력 관리** (경량 JSON 스토리지)

## 🏗️ 기술 스택

### Backend
- **Framework**: FastAPI, Uvicorn
- **AI**: AWS Bedrock (Claude)
- **RAG**: LightRAG (지식 그래프 기반)
- **Vector DB**: NanoVectorDB (LightRAG) + OpenSearch
- **Cache**: Redis
- **OpenAPI**: 국토교통부 (MOLIT), Seoul Open Data

### Frontend
- **Framework**: Streamlit
- **UI Components**: Custom Streamlit components

## 🚀 빠른 시작

### 필수 요구사항

- Python 3.11
- uv (패키지 매니저)
- Docker & Docker Compose
- AWS 계정 (Bedrock)

### 설치 및 실행

```bash
# 1. 저장소 클론
git clone https://github.com/yourusername/boodongsan.git
cd boodongsan

# 2. 백엔드 설정
cd backend
cp .env.example .env
# .env 파일 편집 (API 키 입력 필요)

# 3. 의존성 설치
uv sync

# 4. 외부 서비스 시작
docker-compose up -d redis opensearch

# 5. 백엔드 실행
uv run uvicorn api.main:app --reload

# 6. 프론트엔드 실행 (새 터미널)
cd ../frontend
pip install -r requirements.txt
streamlit run app.py
```

### 접속

- 프론트엔드: http://localhost:8501
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## 📁 프로젝트 구조

```
boodongsan/
├── backend/              # FastAPI 백엔드
│   ├── api/             # API 엔드포인트
│   ├── core/            # 핵심 설정 (config, database)
│   ├── services/        # 비즈니스 로직
│   └── tests/           # 테스트
├── frontend/            # Streamlit 프론트엔드
│   ├── components/      # UI 컴포넌트
│   └── app.py          # 메인 앱
└── docker-compose.yml   # Docker 설정
```

## 🔧 개발

### 코드 품질

```bash
# Lint 검사
uv run ruff check .

# 코드 포맷팅
uv run ruff format .

# 타입 검사
uv run mypy .
```

### 테스트

```bash
# 전체 테스트
uv run pytest

# 커버리지 포함
uv run pytest --cov
```

## 🌐 환경 변수

핵심 환경 변수 (.env 파일):

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
MOLIT_API_KEY=your_molit_key
```

전체 설정은 `backend/.env.example` 참고

## 📊 아키텍처

```
사용자
  ↓
Streamlit Frontend (Port 8501)
  ↓
FastAPI Backend (Port 8000)
  ↓
├─ LightRAG (NetworkXStorage + NanoVectorDB)
├─ OpenSearch (벡터 검색)
├─ AWS Bedrock (AI 응답)
└─ Redis (캐싱)
```

## 📝 라이선스

MIT License

## 🤝 기여

Issues와 Pull Requests를 환영합니다!

## 📞 문의

프로젝트 관련 문의사항은 Issues를 통해 남겨주세요.
