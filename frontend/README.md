# BODA - 부동산 AI 챗봇 (Streamlit Frontend)

한국 부동산 매물 추천 및 정부 정책 매칭을 위한 AI 챗봇 프론트엔드

## 📋 목차

- [개요](#개요)
- [주요 기능](#주요-기능)
- [설치 및 실행](#설치-및-실행)
- [프로젝트 구조](#프로젝트-구조)
- [사용 방법](#사용-방법)
- [설정](#설정)
- [개발 가이드](#개발-가이드)
- [문제 해결](#문제-해결)

## 개요

BODA는 LightRAG 기반 지식 그래프를 활용한 한국 부동산 AI 챗봇입니다. Streamlit을 사용하여 직관적이고 사용하기 쉬운 웹 인터페이스를 제공합니다.

### 기술 스택

- **Frontend Framework**: Streamlit 1.31+
- **HTTP Client**: httpx (FastAPI 백엔드 통신)
- **Data Validation**: Pydantic 2.6+
- **Python Version**: 3.11+

## 주요 기능

### 🏠 부동산 매물 추천
- 아파트, 빌라, 오피스텔 등 다양한 매물 유형 지원
- 지역, 가격, 면적, 거래 유형 기반 필터링
- 실시간 매물 정보 카드 표시

### 📋 정부 주택 정책 매칭
- 사용자 프로필 기반 자격 판정
- 청년, 신혼부부, 생애최초 등 다양한 정책 지원
- 정책 상세 정보 및 신청 링크 제공

### 💬 대화형 인터페이스
- 자연어 기반 질의응답
- 대화 이력 관리
- 세션 기반 컨텍스트 유지

### 🔍 LightRAG 지식 그래프
- 엔티티 기반 지능형 검색
- Naive, Local, Global, Hybrid 검색 모드
- 캐시 기반 고속 응답

## 설치 및 실행

### 사전 요구사항

1. **Python 3.11 이상** 설치
2. **FastAPI 백엔드** 실행 중 (기본: `http://localhost:8000`)

### 설치 단계

```bash
# 1. frontend 디렉토리로 이동
cd frontend

# 2. 가상 환경 생성 (선택)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 환경 변수 설정
cp .env.example .env
# .env 파일을 열어 BACKEND_URL 등 설정 확인

# 5. Streamlit secrets 설정 (선택)
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# secrets.toml 파일 수정 (필요시)
```

### 실행

```bash
# Streamlit 앱 실행
streamlit run app.py

# 브라우저에서 자동으로 열림 (기본: http://localhost:8501)
```

### Docker 실행 (선택)

```bash
# Dockerfile 생성 후
docker build -t boda-frontend .
docker run -p 8501:8501 -e BACKEND_URL=http://host.docker.internal:8000 boda-frontend
```

## 프로젝트 구조

```
frontend/
├── app.py                          # 메인 Streamlit 애플리케이션
├── api_client.py                   # FastAPI 백엔드 클라이언트
├── config.py                       # 설정 관리 (Pydantic)
│
├── components/                     # UI 컴포넌트
│   ├── __init__.py
│   ├── property_card.py           # 매물 카드 컴포넌트
│   ├── policy_card.py             # 정책 카드 컴포넌트
│   └── chat_interface.py          # 채팅 인터페이스 헬퍼
│
├── .streamlit/                     # Streamlit 설정
│   ├── config.toml                # 앱 설정
│   └── secrets.toml.example       # 시크릿 템플릿
│
├── requirements.txt               # Python 의존성
├── .env.example                   # 환경 변수 템플릿
├── .gitignore                     # Git ignore 규칙
└── README.md                      # 이 문서
```

### 주요 파일 설명

#### `app.py`
메인 Streamlit 애플리케이션. 채팅 인터페이스, 세션 관리, UI 렌더링을 담당합니다.

**주요 기능:**
- 세션 상태 초기화 (`initialize_session_state`)
- 사이드바 렌더링 (`render_sidebar`)
- 채팅 응답 처리 (`process_chat_response`)
- 메인 로직 (`main`)

#### `api_client.py`
FastAPI 백엔드와 통신하는 HTTP 클라이언트.

**제공 메서드:**
- `send_message()`: 채팅 메시지 전송
- `get_conversation_history()`: 대화 이력 조회
- `get_user_context()`: 사용자 컨텍스트 조회
- `health_check()`: 백엔드 상태 확인

#### `config.py`
Pydantic Settings를 사용한 환경 변수 관리.

**주요 설정:**
- `BACKEND_URL`: 백엔드 API URL
- `MAX_MESSAGE_LENGTH`: 최대 메시지 길이
- `ENABLE_*`: 기능 플래그

#### `components/`
재사용 가능한 UI 컴포넌트 모음.

- `property_card.py`: 부동산 매물 카드 렌더링
- `policy_card.py`: 정부 정책 카드 렌더링
- `chat_interface.py`: 채팅 메시지 표시 헬퍼

## 사용 방법

### 기본 대화

1. 앱 실행 후 메시지 입력창에 질문 입력
2. AI가 자동으로 매물 추천 및 정책 매칭 수행
3. 결과를 카드 형태로 확인

### 예시 질문

```
강남구 아파트 전세 5억 이하 추천해줘
```
→ 강남구 지역의 전세 아파트 매물을 추천받습니다.

```
청년 대상 주택 지원 정책 알려줘
```
→ 청년층에게 해당하는 정부 주택 정책을 확인합니다.

```
역삼동 오피스텔 월세 매물 찾아줘
```
→ 역삼동의 오피스텔 월세 매물을 검색합니다.

### 사이드바 기능

#### 사용자 정보
- 자동 생성된 사용자 ID 표시
- 현재 대화 ID 표시 (대화 시작 후)

#### 대화 관리
- **새 대화**: 현재 대화 이력을 초기화하고 새 대화 시작
- **이력** (구현 예정): 과거 대화 불러오기

#### 시스템 상태
- **상태 확인**: 백엔드 API 연결 상태 체크
- 연결 상태 표시 (정상/오류/미확인)

#### 설정
- **디버그 정보 표시**: RAG 컨텍스트, 처리 시간 등 상세 정보 표시

## 설정

### 환경 변수 (`.env`)

```bash
# 백엔드 API 설정
BACKEND_URL=http://localhost:8000
API_V1_STR=/api/v1
API_TIMEOUT=30

# 채팅 설정
MAX_MESSAGE_LENGTH=2000
DEFAULT_MESSAGE_LIMIT=20
ENABLE_STREAMING=true

# 기능 플래그
ENABLE_CONVERSATION_HISTORY=true
ENABLE_USER_PROFILE=true
ENABLE_PROPERTY_CARDS=true
ENABLE_POLICY_CARDS=true

# 디버그 모드
DEBUG=false
```

### Streamlit 설정 (`.streamlit/config.toml`)

테마, 서버 포트, CORS 등을 설정할 수 있습니다.

```toml
[theme]
primaryColor = "#FF4B4B"
backgroundColor = "#FFFFFF"

[server]
port = 8501
enableCORS = true
```

## 개발 가이드

### 새로운 UI 컴포넌트 추가

1. `components/` 디렉토리에 새 파일 생성
2. 컴포넌트 함수 구현
3. `components/__init__.py`에서 export

예시:
```python
# components/custom_card.py
import streamlit as st

def render_custom_card(data: dict):
    with st.container():
        st.markdown(f"### {data['title']}")
        st.write(data['content'])
```

### API 클라이언트 확장

`api_client.py`의 `BODAAPIClient` 클래스에 새 메서드 추가:

```python
def get_new_endpoint(self, param: str) -> dict:
    response = self.client.get(f"{self.base_url}/new-endpoint/{param}")
    response.raise_for_status()
    return response.json()
```

### 세션 상태 관리

Streamlit의 `st.session_state`를 사용하여 상태 관리:

```python
# 초기화
if "my_state" not in st.session_state:
    st.session_state.my_state = initial_value

# 읽기
value = st.session_state.my_state

# 쓰기
st.session_state.my_state = new_value
```

## 문제 해결

### 백엔드 연결 실패

**증상**: "❌ 연결 실패" 에러 메시지

**해결 방법**:
1. FastAPI 백엔드가 실행 중인지 확인
   ```bash
   curl http://localhost:8000/api/v1/health
   ```
2. `.env` 파일의 `BACKEND_URL` 확인
3. 방화벽/네트워크 설정 확인

### 매물/정책 카드가 표시되지 않음

**증상**: AI 응답은 받지만 카드가 보이지 않음

**해결 방법**:
1. `.env`에서 기능 플래그 확인
   ```bash
   ENABLE_PROPERTY_CARDS=true
   ENABLE_POLICY_CARDS=true
   ```
2. 백엔드 응답에 `vector_results` 데이터가 포함되어 있는지 확인 (디버그 모드)

### Streamlit 앱이 느림

**해결 방법**:
1. 대화 이력이 너무 길지 않은지 확인 (새 대화 시작)
2. 백엔드 API 타임아웃 증가
   ```bash
   API_TIMEOUT=60
   ```
3. 디버그 정보 표시 끄기

### Import 에러

**증상**: `ModuleNotFoundError: No module named 'streamlit'`

**해결 방법**:
```bash
# 의존성 재설치
pip install -r requirements.txt

# 또는 개별 설치
pip install streamlit httpx pydantic pydantic-settings
```

## 라이선스 및 기여

이 프로젝트는 BODA 부동산 AI 챗봇의 일부입니다.

### 기여 방법
1. Fork this repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 참고 자료

- [Streamlit Documentation](https://docs.streamlit.io/)
- [Streamlit Chat Elements](https://docs.streamlit.io/library/api-reference/chat)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [httpx Documentation](https://www.python-httpx.org/)

## 문의

이슈나 질문이 있으시면 GitHub Issues를 통해 문의해주세요.

---

**Version**: 1.0.0
**Last Updated**: 2025-01-15
