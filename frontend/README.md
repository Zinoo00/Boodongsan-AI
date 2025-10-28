# 🏠 부동산 데이터 AI 어시스턴트

AWS Knowledge Base와 연결된 Streamlit 기반의 대화형 부동산 데이터 인터페이스입니다.

## ✨ 주요 기능

- 🤖 **AI 채팅**: AWS Bedrock Claude 모델과 대화형 인터페이스
- 📊 **데이터 분석**: 부동산 데이터 시각화 및 통계 분석
- 🔍 **지능형 검색**: AWS Knowledge Base를 활용한 벡터 검색
- 📈 **실시간 차트**: Plotly를 사용한 인터랙티브 차트
- 🏘️ **다양한 데이터**: 아파트, 연립다세대, 오피스텔 데이터 지원

## 🚀 빠른 시작

### 1. 가상 환경 설정

```bash
# 가상 환경 삭제
rm -rf .venv

# 가상 환경 생성
python -m venv .venv

# 가상 환경 활성화 (macOS/Linux)
source .venv/bin/activate

# 가상 환경 활성화 (Windows)
# .venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp env_example.txt .env
# .env 파일에서 AWS 자격 증명 및 Knowledge Base ID 설정
```

### 2. 환경변수 설정

`.env` 파일을 생성하고 다음 내용을 설정하세요:

```env
# AWS 설정
AWS_REGION=ap-northeast-2
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key

# AWS Bedrock 설정
KNOWLEDGE_BASE_ID=your_knowledge_base_id
BEDROCK_MODEL_ID=anthropic.claude-haiku-4-5-20251001-v1:0

# S3 설정 (데이터 소스)
S3_BUCKET_NAME=bds-collect
S3_REGION_NAME=ap-northeast-2
```

### 3. 앱 실행

#### 방법 1: Streamlit 직접 실행
```bash
streamlit run app.py
```

#### 방법 2: Python 스크립트 사용 (권장)
```bash
# 기본 실행
python run.py

# 포트 변경
python run.py --port 8080

# 자동 재로드 활성화
python run.py --reload

# 호스트 변경
python run.py --host 127.0.0.1
```

#### 방법 3: Docker 실행
```bash
# Docker Compose 사용
docker-compose up -d

# 또는 Docker 직접 실행
docker build -t boodongsan-frontend .
docker run -p 8501:8501 boodongsan-frontend
```

### 4. 브라우저에서 접속

```
http://localhost:8501
```

## 📁 프로젝트 구조

```
frontend/
├── app.py                    # 메인 Streamlit 앱
├── run.py                    # 실행 스크립트
├── requirements.txt          # Python 의존성
├── env_example.txt          # 환경변수 예시
├── README.md                # 이 파일
└── src/                     # 소스 코드
    ├── __init__.py
    ├── main.py              # 메인 앱 로직
    ├── config/              # 설정 관리
    │   ├── __init__.py
    │   └── settings.py      # 환경변수, 설정
    ├── models/              # 데이터 모델
    │   ├── __init__.py
    │   └── assistant.py     # RealEstateAssistant 클래스
    ├── charts/              # 시각화
    │   ├── __init__.py
    │   └── visualization.py # 차트 생성 함수들
    ├── ui/                  # UI 컴포넌트
    │   ├── __init__.py
    │   ├── sidebar.py       # 사이드바 UI
    │   ├── chat.py          # 채팅 UI
    │   ├── data_analysis.py # 데이터 분석 UI
    │   └── data_search.py   # 데이터 검색 UI
    └── utils/               # 유틸리티 모듈
        ├── __init__.py
        ├── aws_knowledge_base.py # AWS Knowledge Base 연결
        └── data_loader.py        # S3 데이터 로더
```

## 🔧 사용법

### 실행 옵션

#### 기본 실행
```bash
# Python 스크립트 사용 (권장)
python run.py

# Streamlit 직접 실행
streamlit run app.py

# 자동 재로드 활성화
python run.py --reload

# 포트 변경
python run.py --port 8080

# 호스트 변경
python run.py --host 127.0.0.1
```

#### 고급 실행 옵션
```bash
# 개발 모드 (자동 재로드)
streamlit run app.py --server.runOnSave true

# 특정 포트로 실행
streamlit run app.py --server.port 8080

# 특정 호스트로 실행
streamlit run app.py --server.address 127.0.0.1
```

### AI 채팅

1. **사이드바에서 설정**:
   - AWS 리전 선택
   - Knowledge Base ID 입력
   - 검색 결과 수 설정

2. **질문하기**:
   - "분당구 아파트 전세 시세는 어떻게 되나요?"
   - "강남구 오피스텔 월세 추이를 알려주세요"
   - "최근 부동산 시장 동향은 어떤가요?"

### 데이터 분석

- **메트릭**: 총 거래 건수, 평균 보증금, 평균 면적 등
- **차트**: 가격 추이, 면적 분포 등
- **필터**: 지역, 날짜 범위 선택

### 데이터 검색

- **벡터 검색**: 자연어로 부동산 데이터 검색
- **신뢰도 점수**: 검색 결과의 정확도 표시
- **출처 정보**: 데이터의 원본 위치 표시

## 🛠️ 기술 스택

- **Frontend**: Streamlit
- **AI/ML**: AWS Bedrock (Claude 3 Sonnet)
- **Vector Search**: AWS Knowledge Base
- **Data Storage**: Amazon S3
- **Visualization**: Plotly
- **Language**: Python 3.8+

## 📊 지원하는 데이터 타입

- **아파트**: 전월세, 매매 실거래가
- **연립다세대**: 전월세, 매매 실거래가
- **오피스텔**: 전월세, 매매 실거래가

## 🔐 AWS 권한 설정

다음 AWS 서비스에 대한 권한이 필요합니다:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:Retrieve",
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": "*"
        }
    ]
}
```

## 🐛 문제 해결

### 가상 환경 문제

```bash
# 가상 환경이 활성화되지 않은 경우
source .venv/bin/activate  # macOS/Linux
# 또는
.venv\Scripts\activate     # Windows

# 가상 환경 재생성
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### AWS 자격 증명 오류

```bash
# AWS CLI 설정
aws configure

# 또는 환경변수 설정
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
```

### Streamlit 실행 오류

```bash
# Streamlit이 설치되지 않은 경우
pip install streamlit

# 포트가 이미 사용 중인 경우
python run.py --port 8080

# 권한 오류 (Linux/macOS)
sudo python run.py --port 80
```

### 데이터 로드 오류

1. S3 버킷 이름 확인
2. S3 접근 권한 확인
3. 데이터 파일 경로 확인


## 📝 라이선스

MIT 라이선스

---

**참고**: 이 애플리케이션은 batch 서비스에서 수집된 부동산 데이터를 활용합니다.
