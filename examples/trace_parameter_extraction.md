# 예시 10: 복합 파라미터 추출 — 한국어 → ID 매핑 패턴

> **학습 목표**: "1라인 주간 투싼"처럼 여러 파라미터가 동시에 포함된 질문에서
> FM이 한국어 → ID 매핑 규칙을 정확히 적용하는 과정을 추적한다.

---

## 입력

```
1라인 주간 소나타 어제 몇 대 나왔어?
```

---

## Step 1: IntentAgent (의도분석)

### 🔷 FM 입력 (→ Gemini gemini-2.0-flash)
- **System**: INTENT_SYSTEM_PROMPT (의도 6개 + **한국어 → ID 매핑 규칙**)
- **Human**:
```
1라인 주간 소나타 어제 몇 대 나왔어?
```

### 🔶 FM 출력 (← Gemini)
```json
{
  "intent": "production_query",
  "detail": {
    "line": "LINE-1",
    "model": "SONATA",
    "shift": "DAY",
    "date_from": "2026-02-27",
    "date_to": "2026-02-27",
    "period": "",
    "keyword": ""
  },
  "reasoning": "1라인→LINE-1, 주간→DAY, 소나타→SONATA, 어제→2026-02-27. 특정 날짜의 생산 수량 조회."
}
```

> **포인트**: FM이 4개 파라미터를 동시에 매핑:
> | 한국어 | 매핑 규칙 | 결과 |
> |--------|----------|------|
> | 1라인 | "1라인, 세단라인 → LINE-1" | LINE-1 |
> | 주간 | "주간, 낮 → DAY" | DAY |
> | 소나타 | "소나타 → SONATA" | SONATA |
> | 어제 | (현재 날짜 2026-02-28 기준) | 2026-02-27 |

---

## Step 2: InfoAgent → Tool 호출

### 🔶 FM 출력 → Tool 호출
- `get_daily_production({"line": "LINE-1", "model": "SONATA", "shift": "DAY", "date_from": "2026-02-27", "date_to": "2026-02-27"})`

> **포인트**: 5개 파라미터 모두 전달. 특정 날짜 + 복합 필터 → `get_daily_production` 선택.

---

## Step 2.5: ToolNode (SQL 실행)

```sql
SELECT * FROM daily_production
WHERE line_id = 'LINE-1'
  AND model_id = 'SONATA'
  AND shift_id = 'DAY'
  AND production_date >= '2026-02-27'
  AND production_date <= '2026-02-27'
ORDER BY production_date, line_id, shift_id
```

### Tool 결과
```json
[
  {"id": 289, "production_date": "2026-02-27", "line_id": "LINE-1", "model_id": "SONATA",
   "shift_id": "DAY", "planned_qty": 120, "actual_qty": 115, "defect_qty": 2,
   "achievement_rate": 95.8, "note": null}
]
```

---

## Step 2 재진입: InfoAgent (Tool 결과 수신)

### 🔶 FM 출력 (← Gemini) → 텍스트 응답
```
## 어제(2/27) 1라인 주간 소나타 생산 실적

| 항목 | 수치 |
|------|------|
| 계획 | 120대 |
| 실적 | 115대 |
| 달성률 | 95.8% |
| 불량 | 2대 (1.7%) |

✅ 달성률 95.8%로 양호합니다.
```

---

## 학습 포인트

1. **복합 파라미터 추출**: 하나의 문장에서 라인/모델/교대/날짜 4개 파라미터를 동시에 추출하고 매핑.
2. **한국어 → ID 매핑**: INTENT_SYSTEM_PROMPT에 정의된 매핑 규칙이 FM의 파라미터 변환을 가이드.
3. **상대 날짜 해석**: "어제" → 현재 날짜(2026-02-28) 기준으로 2026-02-27 계산. FM이 날짜 추론 수행.
4. **정확한 필터링**: 5개 파라미터가 모두 SQL WHERE 조건에 반영되어 정확히 1건만 반환.
5. **단일 레코드 응답**: 결과가 1건이면 테이블보다 항목별 나열이 더 깔끔. FM이 자동으로 형식 전환.
