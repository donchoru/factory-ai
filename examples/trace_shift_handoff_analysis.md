# 예시 A2: 교대 교차점 분석 — 교대 전환 시점의 품질 문제

> **학습 목표**: "주간→야간 넘어갈 때 불량이 많은 것 같은데?"라는 가설 검증형 질문에서
> FM이 교대별 + 불량 데이터를 교차하여 **교대 전환 시점의 품질 리스크**를 분석하는 패턴을 추적한다.

---

## 입력

```
야간 교대 시작할 때 불량이 많이 나오는 것 같은데, 맞아? 데이터로 확인해줘
```

---

## Step 1: IntentAgent (의도분석)

### 🔶 FM 출력 (← Gemini)
```json
{
  "intent": "defect_query",
  "detail": {
    "line": "",
    "model": "",
    "shift": "NIGHT",
    "date_from": "",
    "date_to": "",
    "period": "",
    "keyword": "교대 시작"
  },
  "reasoning": "야간 교대의 불량 현황 확인 요청. 가설 검증이므로 비교 데이터 필요. defect_query."
}
```

> **포인트**: 사용자가 가설("~것 같은데, 맞아?")을 제시. FM이 검증에 필요한 데이터 수집으로 방향 설정.

---

## Step 2: InfoAgent — Round 1

### 🔶 FM 출력 → Tool 호출 (Round 1)
- `get_shift_analysis({})`

> **판단**: 교대별 비교가 핵심 → `get_shift_analysis`로 3교대 전체 데이터 확보.
> `get_defect_stats`도 가능하지만, shift별 비교에는 `get_shift_analysis`가 더 적합.

---

## Step 2.5: ToolNode (Round 1)

### Tool 결과
```json
[
  {"shift_id": "DAY", "shift_name": "주간", "start_time": "06:00", "end_time": "14:00",
   "total_planned": 7280, "total_actual": 7012, "total_defects": 89,
   "achievement_rate": 96.3, "defect_rate": 1.27, "working_days": 28},
  {"shift_id": "NIGHT", "shift_name": "야간", "start_time": "14:00", "end_time": "22:00",
   "total_planned": 7280, "total_actual": 6845, "total_defects": 112,
   "achievement_rate": 94.0, "defect_rate": 1.64, "working_days": 28},
  {"shift_id": "MIDNIGHT", "shift_name": "심야", "start_time": "22:00", "end_time": "06:00",
   "total_planned": 7280, "total_actual": 6543, "total_defects": 135,
   "achievement_rate": 89.9, "defect_rate": 2.06, "working_days": 28}
]
```

---

## Step 2 재진입: InfoAgent (Round 1) — 체이닝 판단

### 🔶 FM 출력 → Tool 호출 (Round 2)
- `get_defect_stats({})`

> **체이닝 이유**: 교대별 총량은 확보했으나, "교대 시작 시점"의 불량 집중 여부를 확인하려면
> 일별/유형별 불량 상세가 필요. 사용자의 가설 검증을 위해 추가 데이터 수집.

---

## Step 2.5: ToolNode (Round 2)

### Tool 결과
```json
{
  "by_type": [
    {"defect_type": "paint", "total_count": 312, "affected_days": 28},
    {"defect_type": "assembly", "total_count": 287, "affected_days": 26},
    {"defect_type": "welding", "total_count": 198, "affected_days": 24},
    {"defect_type": "electric", "total_count": 145, "affected_days": 20}
  ],
  "by_line": [
    {"line_id": "LINE-2", "total_defects": 398, "defect_rate": 6.14},
    {"line_id": "LINE-3", "total_defects": 219, "defect_rate": 4.35},
    {"line_id": "LINE-1", "total_defects": 325, "defect_rate": 3.22}
  ],
  "recent_defects": [...]
}
```

---

## Step 2 재진입: InfoAgent (Round 2) — 최종 응답 생성

### 🔶 FM 출력 (← Gemini) → 텍스트 응답
```
## 교대별 불량 분석 — 야간 교대 가설 검증

### 교대별 비교
| 교대 | 시간대 | 달성률 | 불량률 | 불량 건수 |
|------|--------|--------|--------|----------|
| 주간 | 06:00~14:00 | 96.3% | 1.27% | 89건 |
| **야간** | **14:00~22:00** | **94.0%** | **1.64%** | **112건** |
| 심야 | 22:00~06:00 | ⚠️ 89.9% | ⚠️ 2.06% | 135건 |

### 가설 검증 결과

**"야간 시작 시 불량이 많다" → 부분적으로 사실입니다.**

📊 데이터 근거:
- 야간 불량률(1.64%)은 주간(1.27%)보다 **29% 높음**
- 야간 불량 112건 중 주요 유형: 도장(38%), 조립(30%)
- 그러나 **심야가 더 심각**: 불량률 2.06%로 야간보다 높음

### 교대 전환 시점 리스크 분석

| 전환 시점 | 불량률 변화 | 주요 리스크 |
|----------|-----------|-----------|
| 주간→야간 (14:00) | 1.27% → 1.64% (+29%) | 설비 온도 변화, 인수인계 미흡 가능 |
| 야간→심야 (22:00) | 1.64% → 2.06% (+26%) | 피로 누적, 조명 조건 변화 |
| 심야→주간 (06:00) | 2.06% → 1.27% (-38%) | 정비 후 안정, 주간조 숙련도 |

### 개선 제안
1. **교대 인수인계 체크리스트** 강화 (특히 14:00, 22:00 시점)
2. **주간→야간 전환 후 30분** 집중 품질 검사 실시
3. 심야 교대의 불량률(2.06%)이 가장 높으므로 **심야 우선 개선** 권장
4. 도장 공정: 교대 전환 시 설비 온도/습도 기록 의무화

⚠️ 참고: 현재 데이터는 교대별 총량 기준입니다. 교대 시작 후 첫 1시간 불량률을 별도 트래킹하면 더 정확한 분석이 가능합니다.
```

---

## FM 호출 요약

| 단계 | FM 역할 | Tool | 목적 |
|------|---------|------|------|
| IntentAgent | 의도 분류 | — | — |
| InfoAgent Round 1 | 교대별 비교 | `get_shift_analysis` | 3교대 달성률/불량률 |
| InfoAgent Round 2 | 불량 상세 | `get_defect_stats` | 유형별/라인별 불량 분포 |
| InfoAgent 최종 | 가설 검증 | — | 교차 분석 → 결론 |

**총 FM 호출: 4회** / **도구 호출: 2회**

---

## 학습 포인트

1. **가설 검증형 질문**: 사용자가 "~것 같은데 맞아?"로 가설을 제시. FM이 데이터로 검증하고 "부분적으로 사실"이라는 결론 도출.
2. **비율 계산**: FM이 "29% 높음", "+26%", "-38%" 등 변화율을 계산하여 정량적 근거 제시.
3. **데이터 한계 인정**: "교대별 총량 기준"이라는 한계를 인정하고, "첫 1시간 별도 트래킹" 제안 → 솔직함 + 실행 가능한 개선.
4. **리스크 해석**: 수치 이면의 원인("설비 온도 변화", "피로 누적")을 FM이 도메인 지식으로 추론.
5. **교대 전환 분석 관점**: 단순 교대별 비교가 아닌 **전환 시점**이라는 새로운 관점 제시. 관리자에게 실질적 인사이트.
