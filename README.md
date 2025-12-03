# BODA - Korean Real Estate RAG AI Chatbot

부동산 매물 추천 및 정부 지원 정책 매칭 AI 챗봇

## 기술 스택

- **Backend**: FastAPI, Uvicorn
- **AI**: AWS Bedrock (Claude Sonnet 4.5 + Titan Embed v2)
- **RAG**: LightRAG (Knowledge Graph RAG)
- **Storage**:
  - **PostgreSQL** (기본값): AWS RDS PostgreSQL + pgvector
  - **Local**: NanoVectorDB + NetworkX + JSON
- **Cache**: Redis
- **Frontend**: Streamlit
- **Data**: 국토교통부 (MOLIT), Seoul Open Data

## 빠른 시작

```bash
# 1. 백엔드 설정
cd backend
cp .env.example .env
# .env 파일 편집 (API 키 입력)

# 2. 의존성 설치
uv sync

# 3. Redis 시작
docker-compose up -d redis

# 4. 백엔드 실행
uv run uvicorn api.main:app --reload

# 5. 프론트엔드 실행 (별도 터미널)
cd frontend
uv sync
uv run streamlit run app.py
```

## 환경 변수

```bash
# Storage Backend
STORAGE_BACKEND=postgresql  # "postgresql" 또는 "local"

# PostgreSQL (프로덕션)
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/db

# AWS Bedrock
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=ap-northeast-2
BEDROCK_MODEL_ID=global.anthropic.claude-sonnet-4-5-20250929-v1:0

# OpenAPI
MOLIT_API_KEY=your_key
```

## 프로젝트 구조

```
boodongsan/
├── backend/
│   ├── api/routers/      # API 엔드포인트
│   ├── services/         # 비즈니스 로직
│   ├── core/             # 설정
│   └── database/         # 모델
├── frontend/
│   ├── app.py            # 메인 앱
│   └── components/       # UI 컴포넌트
└── docker-compose.yml
```

## 명령어

```bash
# 데이터베이스 마이그레이션
uv run alembic upgrade head

# 코드 품질
uv run ruff check .
uv run ruff format .

# 테스트
uv run pytest
```

## 접속

- Frontend: http://localhost:8501
- Backend API: http://localhost:8000/docs

## 라이선스

MIT License
