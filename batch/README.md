# 부동산 데이터 수집기

공공데이터포털 API를 사용하여 아파트, 연립다세대, 오피스텔의 전월세 및 매매 데이터를 수집하고 OpenSearch 벡터 데이터베이스에 저장하는 Python 프로젝트입니다.

## ✨ 주요 기능

- 🏠 **다양한 부동산 데이터 수집**: 아파트, 연립다세대, 오피스텔의 전월세 및 매매 데이터
- 🔍 **벡터 검색**: OpenSearch를 활용한 의미 기반 검색
- 🤖 **AI 임베딩**: sentence-transformers를 사용한 한국어 텍스트 임베딩
- 📊 **스케줄링**: 5년간 전체 데이터 수집 스케줄 (API 제한 고려)
- 🗺️ **법정동 코드 관리**: OpenSearch 기반 동적 법정동 코드 관리
- ⚡ **고성능**: Python 3.11 + uv 패키지 매니저

## 🚀 빠른 시작

### Docker Desktop 환경

```bash
# 환경 변수 설정
cp env_example.txt .env
# .env 파일에서 SERVICE_KEY 설정 (OpenSearch는 기본값 사용)

# 서비스 시작
./scripts/start.sh

# 즉시 데이터 수집
./scripts/immediate-collect.sh

# 서비스 중지
docker-compose down
```

### Rancher Desktop 환경 (권장)

Docker Desktop의 유료화로 인해 무료 대안인 Rancher Desktop을 사용할 수 있습니다.

```bash
# 환경 변수 설정
cp env_example.txt .env
# .env 파일에서 SERVICE_KEY 설정 (OpenSearch는 기본값 사용)

# 서비스 시작
./scripts/start-rancher.sh

# 즉시 데이터 수집
./scripts/immediate-collect-rancher.sh

# 서비스 중지
./scripts/stop-rancher.sh
```

### 로컬 환경

```bash
# uv 설치 (권장)
pip install uv

# 의존성 설치 및 가상환경 자동 생성 (uv가 자동으로 .venv 생성)
uv sync --native-tls

# ONNX 모델 다운로드 (선택사항)
mkdir -p model && \
curl -k -L -o model/all-MiniLM-L6-v2-onnx.tar.gz \
  "https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz" && \
tar -xzf model/all-MiniLM-L6-v2-onnx.tar.gz -C model && \
rm model/all-MiniLM-L6-v2-onnx.tar.gz

# 환경 변수 설정
cp env_example.txt .env
# .env 파일에서 SERVICE_KEY 설정 (OpenSearch는 기본값 사용)

# 스케줄러 실행 (uv가 자동으로 가상환경 사용)
uv run python main.py --schedule --schedule_time 02:00 --data_type all --regions 41480 11680 41135

# 즉시 수집
uv run python collect_now.py --data_type all --recent
```

## 📊 수집 데이터

- **아파트**: 전월세, 매매 실거래가
- **연립다세대**: 전월세, 매매 실거래가  
- **오피스텔**: 전월세, 매매 실거래가

## 🔧 사용법

### 법정동 코드 관리

```bash
# 법정동 코드 조회
python main.py --get_lawd_codes

# 법정동 코드 재수집
python main.py --reload_lawd_codes
```

### 데이터 수집

```bash
# 이번달 데이터 수집 (간편)
python main.py --collect_data --lawd_cd 41480

# 특정 월 데이터 수집
python main.py --collect_data --lawd_cd 41480 --deal_ym 202412

# 특정 데이터 타입만 수집
python main.py --collect_data --data_type apt_rent --lawd_cd 41480

# 모든 데이터 타입 수집
python main.py --collect_data --lawd_cd 41480 --deal_ym 202412
```

### 5년간 전체 데이터 수집 스케줄

```bash
# 현재 요일 데이터 수집
python main.py --schedule_collect

# 특정 요일 데이터 수집
python main.py --schedule_collect --weekday 0  # 월요일
python main.py --schedule_collect --weekday 1  # 화요일
python main.py --schedule_collect --weekday 6  # 일요일
```

### 스케줄링 정보

- **총 요청 수**: 280개 법정동 × 60개월 × 6개 API = 100,800회
- **일일 제한**: 1,000회 (공공데이터포털 제한)
- **요일별 분할**: 7일로 나누어 체계적 수집
- **예상 소요 시간**: 약 101일

## 📁 프로젝트 구조

```
batch/
├── main.py                           # 메인 실행 스크립트
├── src/                              # 소스 코드
│   ├── services/                     # 서비스 모듈
│   │   ├── lawd_service.py           # 법정동 코드 서비스
│   │   ├── data_service.py           # 데이터 처리 서비스
│   │   └── vector_service.py         # 벡터 서비스
│   ├── database/                     # 데이터베이스 모듈
│   │   └── opensearch_client.py      # OpenSearch 클라이언트
│   ├── config/                       # 설정 모듈
│   │   ├── constants.py              # 상수 정의
│   │   └── settings.py               # 설정 파일
│   └── utils/                        # 유틸리티 모듈
│       ├── logger.py                 # 로깅 설정
│       └── helpers.py                # 헬퍼 함수
├── collectors/                       # 데이터 수집기 모듈
│   ├── apartment_collector.py        # 아파트 수집기
│   ├── rh_collector.py              # 연립다세대 수집기
│   ├── offi_collector.py            # 오피스텔 수집기
│   └── base_collector.py            # 기본 수집기
├── tests/                           # 테스트 파일
│   ├── test_lawd_service.py         # 법정동 서비스 테스트
│   └── test_data_service.py         # 데이터 서비스 테스트
├── logs/                           # 로그 파일들
├── model/                          # ONNX 모델 파일
├── scripts/                        # 관리 스크립트
├── Dockerfile                      # Docker 설정
├── docker-compose.yml              # Docker Compose 설정
├── requirements.txt                # Python 의존성
├── pyproject.toml                  # uv 프로젝트 설정
├── uv.lock                         # uv 의존성 잠금 파일
└── README.md                       # 이 파일
```

## ⚙️ 설정

### Rancher Desktop 설치

1. **다운로드**: [Rancher Desktop 공식 사이트](https://rancherdesktop.io/)에서 다운로드
2. **설치**: 다운로드한 파일 실행하여 설치
3. **실행**: Rancher Desktop 앱 실행
4. **설정**: 
   - Preferences → Container Engine → Docker 선택
   - Kubernetes 비활성화 (선택사항)
5. **확인**: 터미널에서 `nerdctl --version` 실행하여 확인

**참고**: Rancher Desktop은 `nerdctl` 명령어를 사용합니다. 이는 Docker CLI와 호환되지만 더 가볍고 효율적입니다.

### 환경 변수 설정

`.env` 파일 생성:
```env
# 공공데이터포털 API 키
SERVICE_KEY=your_actual_api_key_here

# 무료 OpenSearch 설정 (Docker 컨테이너 사용)
OPENSEARCH_ENDPOINT=http://localhost:9200
OPENSEARCH_USERNAME=admin
OPENSEARCH_PASSWORD=admin

# 로그 설정
LOG_DIR=logs
MODEL_DIR=model
```

### 기본 설정

- **법정동 코드**: OpenSearch에서 동적 관리 (280개)
- **거래 년월**: 현재 월 자동 설정 또는 수동 지정
- **API 키**: 환경 변수에서 설정

## 📝 법정동 코드 관리

### 동적 법정동 코드 관리

법정동 코드는 OpenSearch에서 동적으로 관리됩니다:

```bash
# 모든 법정동 코드 조회
python main.py --get_lawd_codes

# 법정동 코드 재수집 (최신 데이터)
python main.py --reload_lawd_codes
```

### 주요 법정동 코드 예시

| 지역          | 코드 | level_1 | level_2 | level_3 |
| ------------- | ---- | ------- | ------- | ------- |
| 서울시 강남구 | 11680 | 서울특별시 | 강남구 | - |
| 경기도 성남시 | 41135 | 경기도 | 성남시 | - |
| 경기도 분당구 | 41480 | 경기도 | 분당구 | - |
| 경기도 하남시 | 41280 | 경기도 | 하남시 | - |
| 경기도 용인시 | 41290 | 경기도 | 용인시 | - |

## 🔧 OpenSearch 설정

### 1. Docker로 OpenSearch 실행

```bash
# OpenSearch 컨테이너 시작
docker-compose up -d opensearch

# OpenSearch 상태 확인
curl http://localhost:9200/_cluster/health

# OpenSearch 대시보드 접속
# http://localhost:9200/_plugin/dashboards/
```

### 2. OpenSearch 기능

- **k-NN 벡터 검색**: 내장 지원
- **REST API**: 표준 Elasticsearch API 호환
- **대시보드**: Kibana 호환 대시보드 제공
- **법정동 코드 관리**: 동적 법정동 코드 저장 및 검색

### 3. 법정동 코드 인덱스 구조

```json
{
  "mappings": {
    "properties": {
      "lawd_code": {"type": "keyword"},
      "level_1": {"type": "text", "analyzer": "korean"},
      "level_2": {"type": "text", "analyzer": "korean"},
      "level_3": {"type": "text", "analyzer": "korean"},
      "exists": {"type": "boolean"}
    }
  }
}
```

### 4. 벡터 검색 설정

부동산 데이터 벡터 검색을 위한 인덱스 매핑:

```json
{
  "mappings": {
    "properties": {
      "vector": {
        "type": "knn_vector",
        "dimension": 384,
        "method": {
          "name": "hnsw",
          "space_type": "cosinesimil",
          "engine": "nmslib"
        }
      }
    }
  }
}
```

## ⚠️ 주의사항

1. **API 호출 제한**: 공공데이터포털 API 일일 1,000회 제한 확인
2. **스케줄링**: 5년간 전체 데이터 수집 시 약 101일 소요
3. **법정동 코드**: OpenSearch에서 동적 관리, 주기적 업데이트 권장
4. **로그 관리**: `logs/collect.log`, `logs/scheduler.log` 파일 주기적 확인
5. **가상환경**: 모든 Python 명령어는 `.venv` 가상환경에서 실행
6. **메모리 사용량**: OpenSearch 컨테이너는 최소 2GB RAM 권장

## 🐛 문제 해결

### OpenSearch 연결 오류

```bash
# OpenSearch 컨테이너 상태 확인
docker ps | grep opensearch

# OpenSearch 엔드포인트 확인
curl http://localhost:9200/_cluster/health

# OpenSearch 연결 테스트
python -c "from src.database.opensearch_client import opensearch_client; print('OpenSearch 연결 성공:', opensearch_client.client.info())"
```

### 법정동 코드 문제 해결

```bash
# 법정동 코드 조회 테스트
python main.py --get_lawd_codes

# 법정동 코드 재수집
python main.py --reload_lawd_codes

# 법정동 코드 서비스 테스트
python -c "from src.services.lawd_service import LawdService; service = LawdService(); print('법정동 코드 수:', len(service.get_lawd_codes()))"
```

### 데이터 수집 문제 해결

```bash
# 간단한 데이터 수집 테스트
python main.py --collect_data --lawd_cd 41480

# 특정 데이터 타입만 수집
python main.py --collect_data --data_type apt_rent --lawd_cd 41480

# 스케줄링 테스트
python main.py --schedule_collect --weekday 0
```

### 가상환경 문제 해결

```bash
# 가상환경 재생성 (uv 사용)
rm -rf .venv
uv sync

# uv 가상환경 확인
uv run which python
uv run pip list

# 또는 수동으로 가상환경 활성화 (선택사항)
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate  # Windows
```

### Rancher Desktop 문제 해결

```bash
# Rancher Desktop 상태 확인
nerdctl info

# 컨테이너 로그 확인
nerdctl compose -f docker-compose.yml logs

# 리소스 사용량 확인
nerdctl stats

# 컨테이너 재시작
nerdctl compose -f docker-compose.yml restart
```

## 🔗 연관 프로젝트

- **Backend Service**: OpenSearch 데이터베이스와 법정동코드 API 제공
- **Frontend**: 부동산 데이터 시각화 및 분석 (계획)

## 📄 라이선스

MIT 라이선스

---

**참고**: [공공데이터포털](https://www.data.go.kr/) API 사용
