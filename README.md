# 부동산 AI 챗봇 (BoodongSan)

한국 부동산 시장을 위한 AI 기반 개인맞춤형 부동산 추천 챗봇

## 🎯 프로젝트 개요

부동산 AI 챗봇은 사용자의 개인 정보(나이, 연봉, 선호도 등)를 기반으로 정부 지원 정책과 매칭하여 최적의 부동산을 추천하는 시스템입니다.

### 주요 기능
- 🏠 개인맞춤형 부동산 추천
- 🏛️ 정부 지원 정책 매칭 (청년전세임대, LH청약플러스, HUG 전세보증보험 등)
- 💬 자연어 기반 대화형 인터페이스
- 📊 실시간 부동산 시장 분석
- 🔍 지역별/조건별 맞춤 검색

## 🏗️ 기술 스택

### Backend
- **언어**: Python 3.11
- **프레임워크**: FastAPI
- **AI/ML**: AWS Bedrock (Claude-3), LangChain
- **데이터베이스**: PostgreSQL (RDS), DynamoDB
- **벡터 DB**: Pinecone
- **캐시**: Redis (ElastiCache)

### Frontend
- **Web**: React + Next.js
- **Mobile**: React Native
- **UI/UX**: Tailwind CSS, Shadcn/ui

### Infrastructure (AWS)
- **컴퓨팅**: Lambda, ECS, EC2
- **스토리지**: S3, RDS, DynamoDB
- **네트워킹**: API Gateway, CloudFront
- **보안**: IAM, Cognito, WAF
- **모니터링**: CloudWatch, X-Ray

## 📋 프로젝트 구조

```
boodongsan/
├── backend/
│   ├── api/              # FastAPI 애플리케이션
│   ├── ai/              # AI 파이프라인 (Bedrock + LangChain)
│   ├── database/        # 데이터베이스 모델 및 마이그레이션
│   ├── services/        # 비즈니스 로직
│   └── utils/           # 유틸리티 함수
├── frontend/
│   ├── web/             # React + Next.js 웹 앱
│   └── mobile/          # React Native 모바일 앱
├── infrastructure/      # AWS CDK/Terraform 설정
├── data/               # 부동산 데이터 및 정책 데이터
└── docs/               # 문서
```

  ┌─────────────────────────────────────────────────────────────┐
  │                     Frontend Layer                          │
  ├─────────────────────────────────────────────────────────────┤
  │  React/Next.js Web App  │  React Native Mobile App          │
  └─────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
  ┌─────────────────────────────────────────────────────────────┐
  │                    API Gateway Layer                        │
  ├─────────────────────────────────────────────────────────────┤
  │           AWS API Gateway + CloudFront CDN                  │
  │               (Rate Limiting, CORS, SSL)                    │
  └─────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
  ┌─────────────────────────────────────────────────────────────┐
  │                  Application Layer                          │
  ├─────────────────────────────────────────────────────────────┤
  │  Lambda Function (Python 3.11)  │  FastAPI + EC2/ECS        │
  │         (Serverless)            │      (Container)          │
  └─────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
  ┌─────────────────────────────────────────────────────────────┐
  │                     AI/ML Layer                             │
  ├─────────────────────────────────────────────────────────────┤
  │  AWS Bedrock (Claude/GPT)  │  LangChain Framework           │
  │  Custom Embedding Models   │  Vector Database (Pinecone)    │
  └─────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
  ┌─────────────────────────────────────────────────────────────┐
  │                    Data Layer                               │
  ├─────────────────────────────────────────────────────────────┤
  │  RDS (PostgreSQL)  │  DynamoDB  │  S3 Bucket  │  ElastiCache│
  │   (Structured)     │  (NoSQL)   │ (Files/Docs)│   (Cache)   │
  └─────────────────────────────────────────────────────────────┘

  핵심 데이터 플로우

  사용자 질문 → API Gateway → Lambda/FastAPI
       ↓
  사용자 프로파일링 → 정부 정책 매칭 → 부동산 데이터 검색
       ↓
  AWS Bedrock + LangChain → 맞춤형 추천 생성
       ↓
  응답 반환 → 사용자 인터페이스

## 🚀 시작하기

### 사전 요구사항
- Python 3.11+
- Node.js 18+
- AWS CLI 설정
- Docker & Docker Compose

### 개발 환경 설정

```bash
# 프로젝트 클론
git clone https://github.com/username/boodongsan.git
cd boodongsan

# 백엔드 설정
cd backend
pip install -r requirements.txt
python -m uvicorn api.main:app --reload

# 프론트엔드 설정
cd frontend/web
npm install
npm run dev
```

## 📊 데이터베이스 스키마

### PostgreSQL (구조적 데이터)
- `users`: 사용자 기본 정보
- `user_preferences`: 사용자 부동산 선호도
- `properties`: 부동산 매물 정보
- `government_policies`: 정부 지원 정책
- `policy_conditions`: 정책별 세부 조건

### DynamoDB (대화 이력)
- 사용자 채팅 기록
- AI 추천 이력
- 사용자 프로파일 캐시

### Pinecone (벡터 검색)
- 부동산 매물 임베딩
- 정부 정책 임베딩
- 유사도 기반 검색

## 🤖 AI 파이프라인

### 1. 의도 분류 (Intent Classification)
- 부동산 검색, 정책 문의, 일반 상담 등

### 2. 개체 추출 (Entity Extraction)
- 나이, 연봉, 지역, 가격대, 매물 유형 등

### 3. 사용자 프로파일링
- 개인 정보 기반 프로파일 생성
- 선호도 학습 및 업데이트

### 4. 정책 매칭
- 자격 조건 검사
- 적용 가능한 정책 필터링

### 5. 부동산 추천
- 벡터 유사도 기반 검색
- 다중 조건 필터링
- 개인화된 순위 결정

## 🏛️ 지원 정부 정책

- **청년전세임대주택**: 청년층 전세자금 지원
- **LH청약플러스**: LH 청약 가점 우대
- **HUG 전세보증보험**: 전세보증금 반환보증
- **신혼부부 특별공급**: 신혼부부 주택 특별공급
- **다자녀 가구 특별공급**: 다자녀 가구 주택 우대
- **생애최초 특별공급**: 무주택자 주택 구입 지원

## 📈 개발 로드맵

### Phase 1: 기본 시스템 구축 (4주)
- [x] 프로젝트 아키텍처 설계
- [x] 데이터베이스 스키마 설계
- [ ] AI 파이프라인 구현
- [ ] 기본 API 개발

### Phase 2: 코어 기능 개발 (6주)
- [ ] 사용자 프로파일링 시스템
- [ ] 정부 정책 매칭 엔진
- [ ] 부동산 추천 알고리즘
- [ ] 채팅 인터페이스

### Phase 3: 고도화 및 최적화 (4주)
- [ ] 성능 최적화
- [ ] 보안 강화
- [ ] 모니터링 시스템
- [ ] 테스트 자동화

### Phase 4: 배포 및 운영 (2주)
- [ ] AWS 인프라 구축
- [ ] CI/CD 파이프라인
- [ ] 운영 모니터링
- [ ] 사용자 피드백

## 📝 라이선스

MIT License

## 👥 기여자

- 개발자: [이름]
- 아키텍트: Claude (Anthropic)

## 📞 문의

프로젝트 관련 문의사항이 있으시면 이슈를 등록해주세요.