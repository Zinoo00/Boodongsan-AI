# 부동산 AI 챗봇 배포 가이드

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 프로젝트 클론
git clone <repository-url>
cd boodongsan

# 환경 변수 설정
cp .env.example .env
# .env 파일에서 AWS 키 설정 필수!
```

### 2. 원클릭 설정 및 실행

```bash
# 모든 설정 자동화
./scripts/setup.sh
```

이 스크립트는 다음을 자동으로 수행합니다:
- 필요한 프로그램 확인 (Docker, Python)
- Docker 이미지 빌드
- 데이터베이스 초기화
- 정부 정책 시드 데이터 추가
- 애플리케이션 시작

### 3. 서비스 접속

- **API 서버**: http://localhost:8000
- **API 문서**: http://localhost:8000/docs
- **헬스체크**: http://localhost:8000/api/v1/health

## 🔧 수동 설정 (고급 사용자)

### 1. Docker Compose로 인프라 시작

```bash
# 데이터베이스 서비스 시작
docker-compose up -d postgres redis

# 전체 서비스 시작
docker-compose up -d
```

### 2. 로컬 개발 환경

```bash
# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
cd backend
pip install -r requirements.txt

# 환경변수 설정 후 서버 실행
uvicorn api.main:app --reload
```

## 📋 필수 환경변수

```env
# AWS Bedrock 필수 설정
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key_id
AWS_SECRET_ACCESS_KEY=your_secret_access_key

# 데이터베이스 (기본값 사용 가능)
POSTGRES_HOST=localhost
POSTGRES_DB=boodongsan
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password

# Redis (기본값 사용 가능)
REDIS_HOST=localhost
REDIS_PORT=6379
```

## 🎯 API 테스트

### 1. 헬스체크

```bash
curl http://localhost:8000/api/v1/health
```

### 2. 채팅 테스트

```bash
curl -X POST "http://localhost:8000/api/v1/chat/send" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "30대 연봉 5천만원인데 서울에서 전세 가능한 곳 추천해주세요",
    "user_id": "test_user_123"
  }'
```

### 3. 정책 검색

```bash
curl -X POST "http://localhost:8000/api/v1/policies/search" \
  -H "Content-Type: application/json" \
  -d '{
    "user_profile": {
      "age": 30,
      "annual_income": 50000000,
      "region_preference": "서울"
    }
  }'
```

## 🏗️ AWS 배포

### 1. ECS + Fargate 배포

```bash
# AWS CLI 설정
aws configure

# ECR 레포지토리 생성
aws ecr create-repository --repository-name boodongsan-backend

# Docker 이미지 빌드 및 푸시
docker build -t boodongsan-backend ./backend
docker tag boodongsan-backend:latest [ACCOUNT].dkr.ecr.us-east-1.amazonaws.com/boodongsan-backend:latest
docker push [ACCOUNT].dkr.ecr.us-east-1.amazonaws.com/boodongsan-backend:latest
```

### 2. 인프라 구성

**필요한 AWS 서비스:**
- ECS Cluster (Fargate)
- RDS PostgreSQL
- ElastiCache Redis  
- Application Load Balancer
- API Gateway (옵션)
- CloudWatch (로깅)

### 3. 환경별 설정

**개발환경 (dev):**
- t3.small 인스턴스
- 단일 가용영역
- 기본 보안 설정

**프로덕션 (prod):**
- 멀티 AZ 배포
- Auto Scaling 설정
- WAF 및 보안 강화
- 백업 및 모니터링

## 🔍 모니터링 및 로깅

### 1. 로그 확인

```bash
# 전체 서비스 로그
docker-compose logs -f

# 특정 서비스 로그
docker-compose logs -f backend
```

### 2. 메트릭스 확인

```bash
curl http://localhost:8000/api/v1/health/metrics
```

### 3. 데이터베이스 상태

```bash
curl http://localhost:8000/api/v1/health/database
```

## 🛠️ 트러블슈팅

### 일반적인 문제들

**1. AWS Bedrock 연결 실패**
```
해결: AWS 자격증명과 리전 설정 확인
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY  
- AWS_REGION=us-east-1
```

**2. 데이터베이스 연결 실패**
```bash
# PostgreSQL 컨테이너 상태 확인
docker-compose ps postgres

# 로그 확인
docker-compose logs postgres
```

**3. 포트 충돌**
```bash
# 사용중인 포트 확인
netstat -an | grep :8000
lsof -i :8000

# 포트 변경
# docker-compose.yml에서 ports 수정
```

**4. 메모리 부족**
```bash
# Docker 메모리 사용량 확인
docker stats

# 불필요한 컨테이너 정리
docker system prune
```

## 📊 성능 최적화

### 1. 데이터베이스 최적화

```sql
-- 인덱스 확인
SELECT * FROM pg_indexes WHERE tablename = 'properties';

-- 쿼리 성능 분석
EXPLAIN ANALYZE SELECT * FROM properties WHERE district = '강남구';
```

### 2. Redis 캐싱 활용

```python
# 사용자 프로필 캐싱
await cache_manager.set_json(f"user_profile:{user_id}", profile, ttl=3600)

# 정책 검색 결과 캐싱  
await cache_manager.set_json(f"policies:{criteria_hash}", policies, ttl=1800)
```

### 3. AI 응답 최적화

- 응답 캐싱으로 중복 요청 처리 시간 단축
- 사용자 컨텍스트 압축으로 토큰 사용량 최적화
- 병렬 처리로 정책 매칭 속도 향상

## 🔒 보안 고려사항

### 1. 환경변수 보안

```bash
# 민감 정보는 환경변수나 시크릿 매니저 사용
# .env 파일은 git에 커밋하지 않음
echo ".env" >> .gitignore
```

### 2. API 보안

```python
# Rate limiting
# API 키 인증
# HTTPS 강제
# CORS 설정
```

### 3. 데이터베이스 보안

```sql
-- 사용자별 권한 분리
-- 민감 데이터 암호화
-- 정기적 백업
```

## 📞 지원 및 문의

문제가 발생하면 다음을 확인해주세요:

1. **로그 파일**: `docker-compose logs -f`
2. **헬스체크**: `curl http://localhost:8000/api/v1/health`
3. **환경변수**: `.env` 파일 설정 확인
4. **AWS 권한**: Bedrock 서비스 접근 권한 확인

추가 지원이 필요하면 GitHub Issues에 문의해주세요.