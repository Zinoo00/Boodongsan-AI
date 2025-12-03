# BODA Frontend

Streamlit 기반 부동산 AI 챗봇 프론트엔드

## 설치 및 실행

```bash
# 의존성 설치
uv sync

# 환경 변수 설정
cp .env.example .env

# 실행
uv run streamlit run app.py
```

## 패키지 관리

```bash
# 패키지 추가
uv add <package-name>

# 개발 패키지 추가
uv add --dev <package-name>
```

## 주요 기능

- 대화형 부동산 상담
- 매물 추천 및 정책 매칭
- 대화 이력 관리

## 구조

```
frontend/
├── app.py              # 메인 앱
├── api_client.py       # 백엔드 API 클라이언트
├── config.py           # 설정
└── components/         # UI 컴포넌트
```

## 환경 변수

```bash
BACKEND_URL=http://localhost:8000
```

## 접속

http://localhost:8501
