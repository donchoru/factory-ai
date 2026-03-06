# 예시 9: 빈 결과 처리 — 데이터 없음 패턴

> **학습 목표**: Tool이 빈 결과를 반환했을 때 FM이 "데이터가 없으면 솔직하게 안내" 규칙에 따라
> 사용자 친화적 메시지를 생성하는 패턴을 추적한다.

---

## 입력

```
3월 소나타 생산 실적 보여줘
```

---

## Step 1: IntentAgent (의도분석)

### 🔶 FM 출력 (← Gemini)
```json
{
  "intent": "production_query",
  "detail": {
    "line": "",
    "model": "SONATA",
    "shift": "",
    "date_from": "2026-03-01",
    "date_to": "2026-03-31",
    "period": "",
    "keyword": ""
  },
  "reasoning": "3월 소나타 생산 실적 조회 요청이므로 production_query"
}
```

---

## Step 2: InfoAgent → Tool 호출

### 🔶 FM 출력 → Tool 호출
- `get_daily_production({"model": "SONATA", "date_from": "2026-03-01", "date_to": "2026-03-31"})`

> **포인트**: `period`가 아닌 특정 날짜 범위 → `get_daily_production` 선택 (가이드 규칙).

---

## Step 2.5: ToolNode (SQL 실행)

```sql
SELECT * FROM daily_production
WHERE model_id = 'SONATA'
  AND production_date >= '2026-03-01'
  AND production_date <= '2026-03-31'
ORDER BY production_date, line_id, shift_id
```

### Tool 결과
```
ToolMessage (get_daily_production): []   ← 3월 데이터 없음
```

> **원인**: 시드 데이터는 2026년 2월만 포함. 3월 데이터는 아직 없음.

---

## Step 2 재진입: InfoAgent (Tool 결과 수신)

### 🔶 FM 출력 (← Gemini) → 텍스트 응답
```
3월(2026-03-01 ~ 2026-03-31) 소나타 생산 실적 데이터가 없습니다.

현재 시스템에 등록된 데이터는 **2026년 2월**(2/1~2/28) 기간입니다.
2월 소나타 실적을 확인하시려면 "이번 달 소나타 생산 현황"으로 질문해주세요.
```

> **포인트**: FM이 빈 배열 `[]`을 받고:
> 1. "데이터가 없으면 솔직하게 안내" 규칙 적용
> 2. 데이터 기준일(2026년 2월) 명시 — 응답 규칙
> 3. 대안 질문 제안 — 사용자를 유효한 데이터로 유도

---

## FM 호출 요약

| 단계 | FM 역할 | 출력 |
|------|---------|------|
| IntentAgent | 의도 분류 | `production_query`, date_from=3/1 |
| InfoAgent 1차 | Tool 선택 | `get_daily_production` |
| InfoAgent 재진입 | **빈 결과 처리** | "데이터 없음" + 대안 안내 |

**총 FM 호출: 3회**

---

## 학습 포인트

1. **빈 결과의 솔직한 안내**: FM이 `[]`을 받으면 억지로 데이터를 만들지 않고 솔직하게 "없다"고 안내.
2. **데이터 기준일 명시**: "현재 데이터는 2026년 2월" — 사용자가 왜 빈 결과인지 이해 가능.
3. **대안 질문 제안**: "2월 실적을 보시려면..."으로 유효한 경로로 유도. 사용자 경험 개선.
4. **날짜 범위 Tool 선택**: `period` 없이 `date_from/date_to`가 있으면 `get_daily_production` 선택.
