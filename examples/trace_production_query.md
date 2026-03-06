# 예시 1: 생산 실적 조회 — 기본 Tool Loop 패턴

> **학습 목표**: `production_query` 의도에서 FM이 어떤 입력을 받고 어떤 출력을 내는지,
> InfoAgent → ToolNode → InfoAgent 재진입 Tool Loop의 전체 흐름을 FM I/O 관점에서 추적한다.

---

## 입력

```
오늘 소나타 몇 대 만들었어?
```

---

## Step 1: IntentAgent (의도분석)

### 🔷 FM 입력 (→ Gemini gemini-2.0-flash)
- **System**: INTENT_SYSTEM_PROMPT (의도 6개 + JSON형식 + 매핑규칙)
- **Human**:
```
오늘 소나타 몇 대 만들었어?
```

### 🔶 FM 출력 (← Gemini)
```json
{
  "intent": "production_query",
  "detail": {
    "line": "",
    "model": "SONATA",
    "shift": "",
    "date_from": "",
    "date_to": "",
    "period": "today",
    "keyword": ""
  },
  "reasoning": "소나타 모델의 오늘 생산 수량을 묻고 있으므로 production_query"
}
```

### 파싱 결과
- intent: `production_query`
- detail: model=SONATA, period=today
- reasoning: 소나타 모델의 오늘 생산 수량을 묻고 있으므로 production_query

---

## Step 2: InfoAgent (정보조회, 첫 호출)

### 🔷 FM 입력 (→ Gemini gemini-2.0-flash, 첫 호출)
- **System**: INFO_SYSTEM_PROMPT (도구 8개 + 체이닝 규칙)
- **Human**:
```
사용자 질문: 오늘 소나타 몇 대 만들었어?
의도: production_query
상세: {"line": "", "model": "SONATA", "shift": "", "date_from": "", "date_to": "", "period": "today", "keyword": ""}

위 의도에 맞는 도구를 호출하여 정보를 조회하세요.
```

### 🔶 FM 출력 (← Gemini) → Tool 호출 요청
- `get_production_summary({"period": "today"})`

> **포인트**: FM이 `period=today`를 감지하여 `get_daily_production` 대신 `get_production_summary`를 선택.
> 프롬프트의 "기간이 오늘/이번주/이번달 → get_production_summary 우선" 규칙 적용.

---

## Step 2.5: ToolNode (SQL 실행)

```sql
-- 라인별 요약
SELECT p.line_id, pl.line_name,
       SUM(p.planned_qty) as total_planned,
       SUM(p.actual_qty) as total_actual,
       SUM(p.defect_qty) as total_defects,
       ROUND(SUM(p.actual_qty) * 100.0 / NULLIF(SUM(p.planned_qty), 0), 1) as achievement_rate
FROM daily_production p
JOIN production_lines pl ON p.line_id = pl.line_id
WHERE production_date = '2026-02-28'
GROUP BY p.line_id

-- 모델별 요약
SELECT p.model_id, m.model_name, p.line_id,
       SUM(p.planned_qty) as total_planned,
       SUM(p.actual_qty) as total_actual,
       ...
FROM daily_production p JOIN models m ON p.model_id = m.model_id
WHERE production_date = '2026-02-28'
GROUP BY p.model_id
```

### Tool 결과
```json
{
  "period": "today",
  "by_line": [
    {"line_id": "LINE-1", "line_name": "1라인 (세단)", "total_planned": 360, "total_actual": 347, "achievement_rate": 96.4},
    {"line_id": "LINE-2", "line_name": "2라인 (SUV)", "total_planned": 240, "total_actual": 228, "achievement_rate": 95.0},
    {"line_id": "LINE-3", "line_name": "3라인 (EV)", "total_planned": 180, "total_actual": 170, "achievement_rate": 94.4}
  ],
  "by_model": [
    {"model_id": "SONATA", "model_name": "소나타", "total_planned": 360, "total_actual": 347, "achievement_rate": 96.4},
    ...
  ]
}
```

---

## Step 2 재진입: InfoAgent (Tool 결과 수신)

### 🔷 FM 입력 (→ Gemini gemini-2.0-flash, 재진입)
- **System**: INFO_SYSTEM_PROMPT (도구 8개 + 체이닝 규칙)
- **Messages**: 메시지 히스토리 2건 포함
  - `AIMessage`: (tool_calls: get_production_summary)
  - `ToolMessage`: {period, by_line, by_model}

### 🔶 FM 출력 (← Gemini) → 텍스트 응답
```
## 오늘(2026-02-28) 소나타 생산 현황

| 항목 | 수치 |
|------|------|
| 계획 | 360대 |
| 실적 | 347대 |
| 달성률 | 96.4% |
| 불량 | 5대 (1.4%) |

✅ 달성률 96.4%로 양호한 수준입니다.
```

> **포인트**: FM이 전체 데이터 중 SONATA만 필터링하여 사용자 질문에 정확히 대응.
> "수량은 쉼표 구분" 규칙은 소규모 데이터라 미적용.

---

## Step 3: ResponseAgent (응답생성)

최종 응답 추출 (InfoAgent 재진입에서 생성된 텍스트):
```
## 오늘(2026-02-28) 소나타 생산 현황
...
```

---

## FM 호출 요약

| 단계 | FM 역할 | 입력 | 출력 |
|------|---------|------|------|
| IntentAgent | 의도 분류 | System + Human("오늘 소나타 몇 대 만들었어?") | JSON: `production_query` |
| InfoAgent 1차 | Tool 선택 | System + Human(질문+의도+상세) | tool_call: `get_production_summary` |
| InfoAgent 재진입 | 응답 생성 | System + Messages(AI+Tool결과) | 텍스트: 소나타 347대 |

**총 FM 호출: 3회** (IntentAgent 1 + InfoAgent 2)

---

## 학습 포인트

1. **FM은 3번 호출됨**: 의도분류 → Tool 선택 → 응답 생성. 각 호출마다 다른 System 프롬프트와 다른 역할.
2. **Tool Loop 패턴**: InfoAgent가 Tool을 호출하면 ToolNode가 실행하고 다시 InfoAgent로 돌아옴. FM이 Tool 결과를 받아 최종 텍스트 응답을 생성.
3. **도구 선택 규칙**: `period=today`가 있으면 `get_production_summary`가 우선. 특정 날짜 범위면 `get_daily_production`.
4. **결과 필터링**: Tool이 전체 라인/모델 데이터를 반환해도, FM이 사용자 질문(소나타)에 맞게 필요한 부분만 추출하여 응답.
