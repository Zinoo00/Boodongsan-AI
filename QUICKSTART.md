# 🚀 빠른 시작 가이드

부동산 매물 추천 AI 챗봇 (BODA) - 5분 안에 실행하기

---

## ⚡ 즉시 시작 (권장)

### 1단계: 환경 설정 확인

```bash
cd backend

# API 키와 환경 확인
uv run python -m scripts.load_data check
```

**예상 출력:**

```
✅ 국토교통부 API 키: 설정됨
✅ Anthropic API 키: 설정됨
시군구 데이터: 252개 로드됨
```

### 2단계: 샘플 데이터 로딩 (5-10분)

```bash
# 강남3구 샘플 데이터 로딩 (500건)
uv run python -m scripts.load_data load --mode sample
```

**진행 상황:**

```
시군구 행정구역 데이터 로딩 시작...
시군구 데이터 252개 삽입 완료
국토교통부 실거래가 데이터 로딩 시작...
진행 중: 100개 문서 삽입됨
진행 중: 200개 문서 삽입됨
...
✅ 데이터 로딩 성공!
총 752개 문서가 LightRAG에 삽입되었습니다.
```

### 3단계: 백엔드 서버 시작

```bash
# 새 터미널 열기
cd backend
uv run uvicorn api.main:app --reload
```

**확인:**

```
Application services initialized (using LightRAG with NanoVectorDB)
Application startup complete.
Uvicorn running on http://127.0.0.1:8000
```

### 4단계: 프론트엔드 시작

```bash
# 또 다른 터미널 열기
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

### 5단계: 채팅 테스트

브라우저에서 http://localhost:8501 접속 후:

**테스트 질문:**

- "강남구 아파트 시세 알려줘"
- "서초구에 1억대 전세 있어?"
- "송파구 신축 아파트 추천해줘"

---

## 🔧 대체 방법: API를 통한 데이터 로딩

백그라운드 작업으로 데이터를 로딩하고 싶다면:

### 1단계: 서버 먼저 시작

```bash
cd backend
uv run uvicorn api.main:app --reload
```

### 2단계: API로 데이터 로딩

```bash
# 샘플 데이터 로딩 시작
curl -X POST "http://localhost:8000/api/v1/admin/load-data" \
  -H "Content-Type: application/json" \
  -d '{"mode": "sample"}'
```

### 3단계: 진행 상황 확인

```bash
# 상태 확인 (5초마다 실행)
watch -n 5 'curl -s "http://localhost:8000/api/v1/admin/status" | python3 -m json.tool'
```

**완료 확인:**

```json
{
  "is_loading": false,
  "last_load_time": "2024-10-31T14:30:00",
  "last_stats": {
    "districts": 252,
    "properties": 500
  }
}
```

---

## 📊 API 문서 확인

서버 실행 후: http://localhost:8000/docs

**주요 엔드포인트:**

- `POST /api/v1/chat/send` - 채팅 메시지 전송
- `GET /api/v1/admin/stats` - 데이터 통계
- `POST /api/v1/admin/load-data` - 데이터 로딩

---

## 🐛 문제 해결

### 문제 1: "MOLIT API 연결 실패 (401)"

**원인:** API 키가 URL 인코딩되지 않았거나 활용신청 미승인

**해결:**

1. [공공데이터포털](https://www.data.go.kr) 로그인
2. 마이페이지 → 활용신청 현황 확인
3. 승인 대기중이면 1-2시간 대기
4. 승인 완료 후 재시도

### 문제 2: "LightRAG 스토리지가 비어 있습니다"

**원인:** 데이터를 아직 로딩하지 않음

**해결:**

```bash
cd backend
uv run python -m scripts.load_data load --mode sample
```

### 문제 3: "채팅 타임아웃"

**원인:** LightRAG에 데이터가 없음

**해결:**

1. 데이터 로딩 확인:

   ```bash
   ls -la backend/lightrag_storage/BODA/
   ```

2. 파일이 없으면 데이터 로딩:
   ```bash
   cd backend
   uv run python -m scripts.load_data load --mode sample
   ```

### 문제 4: "Anthropic API 오류"

**원인:** API 키 미설정 또는 잘못됨

**해결:**

1. `.env` 파일 확인:

   ```bash
   cat backend/.env | grep ANTHROPIC_API_KEY
   ```

2. [Anthropic Console](https://console.anthropic.com)에서 새 키 발급

3. `.env` 파일 업데이트 후 서버 재시작

---

## 📈 다음 단계

### 전체 데이터 로딩 (선택)

```bash
# 모든 자치구 데이터 (1-3시간 소요)
cd backend
uv run python -m scripts.load_data load --mode full

# 또는 특정 지역만
uv run python -m scripts.load_data load --mode full --districts 강남구,서초구,송파구,마포구
```

### 정기 업데이트 설정

```bash
# Cron job 설정 (매월 1일 새벽 2시)
0 2 1 * * cd /path/to/boodongsan/backend && uv run python -m scripts.load_data load --mode full
```

### 모니터링

```bash
# 데이터 통계 확인
curl "http://localhost:8000/api/v1/admin/stats" | python3 -m json.tool
```

---

## 📚 추가 문서

- [TROUBLESHOOTING_SUMMARY.md](TROUBLESHOOTING_SUMMARY.md) - 상세 문제 해결 가이드
- [backend/scripts/README.md](backend/scripts/README.md) - 데이터 로딩 완벽 가이드
- [CLAUDE.md](CLAUDE.md) - 프로젝트 개요

---

## 🎉 완료!

이제 채팅 서비스가 정상적으로 작동해야 합니다.

**테스트:**

```bash
curl -X POST "http://localhost:8000/api/v1/chat/send" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "강남구 아파트 시세 알려줘",
    "user_id": "test_user"
  }'
```

**성공 시 응답:**

```json
{
  "user_id": "test_user",
  "conversation_id": "...",
  "response": "강남구 아파트 매매 시세는...",
  "processing_time_ms": 1234.56
}
```

즐거운 개발 되세요! 🚀
