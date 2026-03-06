# 예시 8: 복합 의도 판단 — 경계선 질문 패턴

> **학습 목표**: "불량률 추이"처럼 여러 의도에 걸치는 질문에서
> FM이 INTENT_SYSTEM_PROMPT의 복합 의도 판단 규칙을 적용하여 분류하는 과정을 추적한다.

---

## 입력

```
불량률 추이가 어떻게 돼?
```

> **경계선**: `defect_query`(불량) vs `trend_analysis`(추이) — 어느 쪽?

---

## Step 1: IntentAgent (의도분석)

### 🔷 FM 입력 (→ Gemini gemini-2.0-flash)
- **System**: INTENT_SYSTEM_PROMPT (의도 6개 + 복합 의도 판단 규칙)
- **Human**:
```
불량률 추이가 어떻게 돼?
```

### 🔶 FM 출력 (← Gemini)
```json
{
  "intent": "trend_analysis",
  "detail": {
    "line": "",
    "model": "",
    "shift": "",
    "date_from": "",
    "date_to": "",
    "period": "",
    "keyword": "불량률 추이"
  },
  "reasoning": "복합 의도 규칙 적용: '불량률 추이' → trend_analysis (추이가 핵심)"
}
```

> **핵심**: INTENT_SYSTEM_PROMPT의 복합 의도 규칙:
> ```
> - "불량률 추이" → trend_analysis (추이가 핵심)
> ```
> FM이 이 규칙을 정확히 인용하여 trend_analysis로 분류.

---

## Step 2: InfoAgent → Tool 호출

### 🔶 FM 출력 → Tool 호출
- `get_production_trend({"days": 28})`

> **포인트**: `trend_analysis` 의도 → `get_production_trend` 선택.
> 이 Tool은 일별 달성률과 **불량률**을 모두 반환하므로 불량률 추이도 추출 가능.

---

## Step 2.5: ToolNode (SQL 실행)

### Tool 결과 (일부)
```json
[
  {"production_date": "2026-02-01", "actual": 745, "defects": 9, "defect_rate": 1.21},
  {"production_date": "2026-02-07", "actual": 738, "defects": 12, "defect_rate": 1.63},
  {"production_date": "2026-02-14", "actual": 732, "defects": 15, "defect_rate": 2.05},
  {"production_date": "2026-02-21", "actual": 740, "defects": 11, "defect_rate": 1.49},
  {"production_date": "2026-02-28", "actual": 745, "defects": 10, "defect_rate": 1.34}
]
```

---

## Step 2 재진입: InfoAgent (Tool 결과 수신)

### 🔶 FM 출력 (← Gemini) → 텍스트 응답
```
## 2월 전체 불량률 추이

| 주차 | 불량률 | 추세 |
|------|--------|------|
| 1주 (2/1~2/7) | 1.21% | 기준선 |
| 2주 (2/8~2/14) | 1.63% | ↑ 상승 |
| 3주 (2/15~2/21) | ⚠️ 2.05% | ↑↑ 기준(2%) 초과 |
| 4주 (2/22~2/28) | 1.49% | ↓ 개선 |

📉 3주차에 2.05%로 기준 초과했으나 4주차에 1.49%로 개선되었습니다.
전반적으로 안정적이나, 3주차 상승 원인(특정 라인/모델 집중 여부)을 확인하시는 것을 권장합니다.
```

---

## 학습 포인트

1. **복합 의도 규칙**: "불량률 추이"는 defect_query + trend_analysis 양쪽. INTENT_SYSTEM_PROMPT에 명시된 규칙("추이가 핵심")이 판단의 근거.
2. **Tool의 다목적성**: `get_production_trend`가 달성률뿐 아니라 불량률도 반환. 하나의 Tool로 여러 관점의 추이 분석 가능.
3. **추세 표시**: FM이 "↑ 상승", "↓ 개선" 같은 방향성 마커를 자동 추가하여 시각적 이해도 향상.
4. **유사 질문 비교**:
   - "불량률 추이" → `trend_analysis` (추이가 핵심)
   - "이번 달 불량 현황" → `defect_query` (현황이 핵심)
   - "라인 정지 왜 자주 돼?" → `downtime_query` (정지가 핵심)
