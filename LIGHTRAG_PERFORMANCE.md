# LightRAG 성능 특성 및 최적화 가이드

## 📊 요약

**LightRAG는 의도적으로 느립니다.** 이는 버그가 아니라 깊은 지식 그래프 분석을 위한 설계상의 특징입니다.

### 실제 성능 데이터

| 문서 수 | 예상 시간 | 실제 속도 |
|---------|-----------|-----------|
| 10개 | 2-3분 | 분당 4-6개 |
| 100개 | 20-25분 | 분당 4-6개 |
| 500개 | 1.5-2시간 | 분당 4-6개 |
| 1,000개 | 3-4시간 | 분당 4-6개 |
| 10,000개 | 1-2일 | 분당 4-6개 |

---

## 🔍 왜 느린가?

### 처리 파이프라인

각 문서마다 다음 단계를 거칩니다:

```
문서 → 청킹 → 엔티티 추출 (LLM) → 관계 추출 (LLM) 
     → 엔티티 병합 (LLM) → 그래프 업데이트 → 디스크 저장
```

### 병목 지점

1. **LLM API 호출**
   - 각 문서당 2-3회 Anthropic Claude API 호출
   - 각 호출당 1-3초 소요
   - Rate limiting으로 재시도 발생 (0.5-1초 추가)

2. **순차 처리**
   - 문서를 하나씩 처리 (배치 없음)
   - 병렬 처리 제한적 (내부 async: 8)

3. **디스크 I/O**
   - 각 문서 처리 후 전체 그래프 저장
   - 그래프가 클수록 저장 시간 증가

4. **중복 제거**
   - 새 엔티티와 기존 엔티티 비교
   - LLM을 사용한 semantic 병합

---

## 🚀 최적화 방법

### 1. 소량 테스트 (필수)

실제 로딩 전 반드시 소량으로 테스트:

```bash
# 10개 문서로 테스트 (2-3분)
uv run python -m scripts.load_data load \
  --mode full \
  --districts 강남구 \
  --limit 10
```

### 2. 제한적 수집

전체 데이터 대신 필요한 부분만:

```bash
# 강남구 100개만
uv run python -m scripts.load_data load \
  --mode full \
  --districts 강남구 \
  --year-month 202410 \
  --limit 100
```

### 3. 백그라운드 실행

장시간 작업은 백그라운드에서:

```bash
# nohup으로 백그라운드 실행
nohup uv run python -m scripts.load_data load \
  --mode full \
  --districts 강남구 \
  --limit 1000 \
  > load.log 2>&1 &

# 진행상황 모니터링
tail -f load.log
```

### 4. 진행률 확인

개선된 스크립트는 진행률을 실시간으로 표시:

```
진행 중: 10개 삽입 완료 | 처리 속도: 5.2개/분
진행 중: 20개 삽입 완료 | 처리 속도: 4.8개/분
진행 중: 30개 삽입 완료 | 처리 속도: 5.1개/분
```

---

## 🎯 권장 사용 패턴

### 개발/테스트

```bash
# 단계 1: 극소량 테스트 (10개)
uv run python -m scripts.load_data load --mode full --districts 강남구 --limit 10

# 단계 2: 시스템 확인 완료 후 소량 수집 (100개)
uv run python -m scripts.load_data load --mode full --districts 강남구 --limit 100
```

### 프로덕션

```bash
# 단계 1: 주요 자치구만 선택적 수집
uv run python -m scripts.load_data load --mode full --districts 강남구,서초구 --limit 1000

# 단계 2: 백그라운드로 전체 수집 (선택사항)
nohup uv run python -m scripts.load_data load --mode full > load.log 2>&1 &
```

---

## ⚠️ 주의사항

### API Rate Limits

Anthropic API에는 다음 제한이 있습니다:

| Tier | 요청/분 | 토큰/분 |
|------|---------|---------|
| Free | 5 | 50,000 |
| Tier 1 | 50 | 100,000 |
| Tier 2 | 1,000 | 400,000 |

**영향:**
- Free tier: 분당 2-3개 문서 처리 가능
- Tier 1+: 분당 4-6개 문서 처리 가능

### 비용 추정

Claude API 호출 비용 (haiku 기준):
- 입력: $0.25 / 1M tokens
- 출력: $1.25 / 1M tokens

**예상 비용:**
- 100개 문서: 약 $0.10-0.20
- 1,000개 문서: 약 $1-2
- 10,000개 문서: 약 $10-20

---

## 🔄 대안 검토

LightRAG가 너무 느리다면 다음 대안을 고려:

### 1. Simple Vector Database

**장점:**
- 매우 빠름 (초당 수백-수천 개)
- 구현 간단

**단점:**
- 관계 정보 없음
- 컨텍스트 이해 제한적

**예:** ChromaDB, Pinecone, Weaviate

### 2. Hybrid Approach

**방법:**
- 벡터 DB로 1차 검색 (빠름)
- LightRAG로 심화 분석 (느리지만 정확)

### 3. Pre-built Index

**방법:**
- 오프라인에서 미리 인덱스 구축
- 읽기 전용으로 서비스 제공

---

## 📈 성능 모니터링

### 로그 확인

```bash
# 실시간 로그
tail -f load.log

# 에러만 확인
grep ERROR load.log

# 진행률 확인
grep "진행 중" load.log
```

### 그래프 통계

로딩 완료 후 그래프 통계:

```python
# 저장된 파일 확인
ls -lh backend/lightrag_storage/BODA/

# 그래프 크기 확인
cat backend/lightrag_storage/BODA/graph_chunk_entity_relation.graphml
```

---

## 💡 FAQ

### Q: 왜 이렇게 느린가요?
**A:** LightRAG는 단순 검색이 아닌 지식 그래프를 구축합니다. 각 문서마다 엔티티와 관계를 추출하고 기존 지식과 병합하는 과정이 필요합니다.

### Q: 더 빠르게 할 수 없나요?
**A:** 근본적으로는 어렵습니다. API 호출과 LLM 처리가 병목이기 때문입니다. `--limit`로 데이터를 제한하는 것이 가장 실용적입니다.

### Q: 배치 처리는 안 되나요?
**A:** 현재 LightRAG는 순차 처리 구조입니다. 향후 개선 가능성은 있지만 본질적인 속도 향상은 제한적입니다.

### Q: 다른 사람들도 이렇게 느린가요?
**A:** 네, LightRAG 사용자들은 모두 비슷한 성능을 경험합니다. 이는 정상적인 동작입니다.

### Q: 프로덕션에 적합한가요?
**A:** 소규모 데이터셋(수백~수천 개)에는 적합합니다. 대규모 데이터(수만 개 이상)는 오프라인 배치 처리 후 서빙하는 것을 권장합니다.

---

## 📚 참고 자료

- [LightRAG GitHub](https://github.com/HKUDS/LightRAG)
- [Anthropic API Limits](https://docs.anthropic.com/en/api/rate-limits)
- [프로젝트 README](README.md)
- [데이터 로딩 가이드](backend/scripts/README.md)

