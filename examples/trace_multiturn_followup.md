# 예시 10: 멀티턴 연속 대화 — 같은 주제 심화 (전체 → 특정 라인 → 불량 원인)

> **학습 목표**: 3턴에 걸쳐 같은 주제를 점점 좁혀가는 멀티턴 대화 패턴.
> `conversation_history`가 FM의 입력에 포함되어 문맥을 유지하는 FM I/O를 추적한다.

---

## 대화 흐름

```
Turn 1: "오늘 생산 현황 알려줘"
Turn 2: "2라인만 자세히 보여줘"           ← "2라인만" = Turn 1 결과에서 범위 축소
Turn 3: "거기 불량이 왜 높은 거야?"       ← "거기" = Turn 2의 LINE-2 참조
```

---

## Turn 1: 오늘 생산 현황 알려줘

### IntentAgent
- conversation_history: 0턴 → 이력 없이 질문만 전달
- 🔶 FM 출력: `production_query`, period=today

### InfoAgent → Tool
- `get_production_summary({"period": "today"})`

### 응답
```
## 오늘(2026-02-28) 생산 현황

| 라인 | 계획 | 실적 | 달성률 | 불량률 |
|------|------|------|--------|--------|
| LINE-1 (세단) | 360대 | 347대 | 96.4% | 1.42% |
| LINE-2 (SUV) | 240대 | 228대 | 95.0% | ⚠️ 3.18% |
| LINE-3 (EV) | 180대 | 170대 | 94.4% | ⚠️ 2.51% |
```

### 대화 이력 저장
```python
conversation_history = [
    {"user": "오늘 생산 현황 알려줘", "intent": "production_query",
     "answer": "오늘(2026-02-28) 생산 현황...LINE-1 347대, LINE-2 228대, LINE-3 170대..."}
]
```

---

## Turn 2: 2라인만 자세히 보여줘

### IntentAgent

#### 🔷 FM 입력 (→ Gemini gemini-2.0-flash)
- **System**: INTENT_SYSTEM_PROMPT
- **Human** (`_build_context` 적용):
```
[이전 대화 이력]
사용자: 오늘 생산 현황 알려줘
의도: production_query
응답 요약: 오늘(2026-02-28) 생산 현황...LINE-1 347대, LINE-2 228대, LINE-3 170대...

[현재 질문]
2라인만 자세히 보여줘

위 대화 이력을 참고하여 현재 질문의 의도를 분석하세요.
'그럼', '거기', '그 라인' 등 대명사는 이전 대화에서 언급된 대상을 참조합니다.
```

> **핵심**: `_build_context()`가 이전 대화 이력을 FM 입력에 주입.
> "2라인만 자세히" → 이전 턴의 전체 라인 결과에서 LINE-2로 범위 축소.

#### 🔶 FM 출력 (← Gemini)
```json
{
  "intent": "line_status",
  "detail": {"line": "LINE-2", ...},
  "reasoning": "2라인의 상세 현황을 요청. 이전 대화에서 생산 현황을 확인한 후 특정 라인 심화 조회."
}
```

### InfoAgent → Tool
- `get_line_status({"line": "LINE-2"})`

### 응답
```
## LINE-2 (SUV라인) 상세 현황

| 항목 | 수치 |
|------|------|
| 오늘 실적 | 228/240대 (95.0%) |
| 최근 7일 달성률 | 91.5% |
| 불량률 | ⚠️ 3.18% |
| 최근 정지 | 5회 |
```

### 대화 이력 (2턴)
```python
conversation_history = [
    {"user": "오늘 생산 현황 알려줘", "intent": "production_query", "answer": "..."},
    {"user": "2라인만 자세히 보여줘", "intent": "line_status", "answer": "LINE-2 상세...불량률 3.18%...정지 5회..."}
]
```

---

## Turn 3: 거기 불량이 왜 높은 거야?

### IntentAgent

#### 🔷 FM 입력 (→ Gemini gemini-2.0-flash)
- **Human** (`_build_context` 적용):
```
[이전 대화 이력]
사용자: 오늘 생산 현황 알려줘
의도: production_query
응답 요약: 오늘(2026-02-28) 생산 현황...

사용자: 2라인만 자세히 보여줘
의도: line_status
응답 요약: LINE-2 상세...불량률 3.18%...정지 5회...

[현재 질문]
거기 불량이 왜 높은 거야?

위 대화 이력을 참고하여 현재 질문의 의도를 분석하세요.
'그럼', '거기', '그 라인' 등 대명사는 이전 대화에서 언급된 대상을 참조합니다.
```

> **핵심 — 대명사 해소**: "거기" → 이전 대화에서 LINE-2를 참조.
> FM이 이력을 보고 "거기 = LINE-2"로 해소.

#### 🔶 FM 출력 (← Gemini)
```json
{
  "intent": "defect_query",
  "detail": {"line": "LINE-2", ...},
  "reasoning": "'거기'는 이전 대화의 LINE-2를 가리킴. 불량 원인 분석 요청이므로 defect_query."
}
```

### InfoAgent → Tool (체이닝)
- Round 1: `get_defect_stats({"line": "LINE-2"})`
- Round 2: `get_downtime_history({"line": "LINE-2"})` ← 불량 원인 파악을 위해 체이닝

### 최종 응답
```
## LINE-2 불량 원인 분석

### 불량 유형별
| 유형 | 건수 | 비중 |
|------|------|------|
| 도장 | 168건 | 42% |
| 조립 | 122건 | 31% |
| 용접 | 72건 | 18% |
| 전장 | 36건 | 9% |

### 설비 정지와의 관계
최근 정지 5회 중 3회가 설비 고장(도장 부스 필터, 용접 로봇 암 등).
도장 불량(42%)이 최다인 점과 도장 부스 관련 정지가 반복되는 점을 고려하면,
**도장 공정의 설비 노후화**가 LINE-2 높은 불량률의 주요 원인으로 추정됩니다.
```

---

## FM 호출 요약 (3턴 합계)

| Turn | 질문 | FM 호출 |
|------|------|---------|
| 1 | "오늘 생산 현황 알려줘" | 3회 (IntentAgent + InfoAgent 2) |
| 2 | "2라인만 자세히 보여줘" | 3회 |
| 3 | "거기 불량이 왜 높은 거야?" | 4회 (체이닝) |

**총 FM 호출: 10회** (3턴, 도구 4개)

---

## 학습 포인트

1. **문맥 축소**: Turn 1(전체 라인) → Turn 2(LINE-2) → Turn 3(LINE-2 불량) — 점점 좁혀가는 대화.
2. **대명사 해소**: "거기" → `_build_context()`가 이전 이력을 FM에 주입 → FM이 LINE-2로 해소.
3. **자동 의도 전환**: production_query → line_status → defect_query. 대화 흐름에 따라 의도가 자연스럽게 전환.
4. **Turn 3 체이닝**: "왜?"라는 원인 분석 요청에 FM이 불량 통계 + 정지 이력을 교차 분석.
5. **conversation_history 누적**: 매 턴마다 이력이 쌓여 다음 턴의 문맥이 풍부해짐.
