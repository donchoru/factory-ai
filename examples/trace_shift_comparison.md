# 예시 7: 교대별 비교 — 동일 의도, 다른 Tool 선택 패턴

> **학습 목표**: 같은 `production_query` 의도라도 질문의 뉘앙스("교대별 비교")에 따라
> FM이 `get_shift_analysis`를 선택하는 과정을 추적한다. 의도는 같아도 Tool이 달라질 수 있음.

---

## 입력

```
주간이랑 야간 생산량 비교해줘
```

---

## Step 1: IntentAgent (의도분석)

### 🔶 FM 출력 (← Gemini)
```json
{
  "intent": "production_query",
  "detail": {
    "line": "",
    "model": "",
    "shift": "",
    "date_from": "",
    "date_to": "",
    "period": "",
    "keyword": "비교"
  },
  "reasoning": "주간/야간 교대 간 생산량 비교를 요청하므로 production_query"
}
```

> **포인트**: "비교"는 trend_analysis로 갈 수도 있지만, "추이/트렌드"가 아닌 교대 간 비교이므로 production_query.
> keyword에 "비교"가 추출됨.

---

## Step 2: InfoAgent (정보조회, 첫 호출)

### 🔷 FM 입력 (→ Gemini gemini-2.0-flash, 첫 호출)
- **System**: INFO_SYSTEM_PROMPT (도구 8개 + 체이닝 규칙)
- **Human**:
```
사용자 질문: 주간이랑 야간 생산량 비교해줘
의도: production_query
상세: {"line": "", "model": "", "shift": "", "date_from": "", "date_to": "", "period": "", "keyword": "비교"}
```

### 🔶 FM 출력 (← Gemini) → Tool 호출
- `get_shift_analysis({})`

> **핵심**: `production_query` 의도인데 `get_shift_analysis`를 선택.
> INFO_SYSTEM_PROMPT에 "교대별 생산 분석 → get_shift_analysis" 도구 설명이 있고,
> "주간이랑 야간 비교"라는 질문 맥락에서 FM이 적절한 Tool을 선택.

---

## Step 2.5: ToolNode (SQL 실행)

### Tool 결과
```json
[
  {"shift_id": "DAY", "shift_name": "주간", "start_time": "06:00", "end_time": "14:00",
   "total_planned": 7280, "total_actual": 7012, "total_defects": 89, "achievement_rate": 96.3, "defect_rate": 1.27, "working_days": 28},
  {"shift_id": "NIGHT", "shift_name": "야간", "start_time": "14:00", "end_time": "22:00",
   "total_planned": 7280, "total_actual": 6845, "total_defects": 112, "achievement_rate": 94.0, "defect_rate": 1.64, "working_days": 28},
  {"shift_id": "MIDNIGHT", "shift_name": "심야", "start_time": "22:00", "end_time": "06:00",
   "total_planned": 7280, "total_actual": 6543, "total_defects": 135, "achievement_rate": 89.9, "defect_rate": 2.06, "working_days": 28}
]
```

---

## Step 2 재진입: InfoAgent (Tool 결과 수신)

### 🔶 FM 출력 (← Gemini) → 텍스트 응답
```
## 교대별 생산 비교 (2026년 2월)

| 교대 | 시간대 | 생산량 | 달성률 | 불량률 |
|------|--------|--------|--------|--------|
| 주간 | 06:00~14:00 | 7,012대 | 96.3% | 1.27% |
| 야간 | 14:00~22:00 | 6,845대 | 94.0% | 1.64% |
| 심야 | 22:00~06:00 | 6,543대 | ⚠️ 89.9% | ⚠️ 2.06% |

### 비교 분석
- **주간 vs 야간**: 주간이 167대(+2.4%) 더 생산. 불량률도 주간이 0.37%p 낮음.
- **심야 주의**: 달성률 89.9%로 90% 미만 ⚠️, 불량률 2.06%로 기준(2%) 초과 ⚠️

심야 교대의 달성률과 불량률 개선이 전체 생산성 향상의 핵심입니다.
```

---

## 학습 포인트

1. **의도와 Tool의 다대다 관계**: `production_query` 의도인데 `get_shift_analysis`를 선택. 의도 1개에 여러 Tool이 대응할 수 있고, FM이 질문 맥락으로 최적 Tool을 판단.
2. **비교 분석**: FM이 단순 표 뿐만 아니라 "주간 vs 야간" 직접 비교 수치를 계산 (167대, +2.4%).
3. **3교대 포함**: 사용자가 주간/야간만 물었지만, 심야도 포함하여 전체 교대 비교 제공. FM이 맥락 확장.
