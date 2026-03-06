# 예시 6: 생산 추이 분석 — 시계열 데이터 패턴

> **학습 목표**: `trend_analysis` 의도에서 `get_production_trend` Tool이 시계열 데이터를 반환하고,
> FM이 이를 분석하여 추세/변곡점을 파악하는 패턴을 추적한다.

---

## 입력

```
소나타 이번 달 생산 추이 보여줘
```

---

## Step 1: IntentAgent (의도분석)

### 🔶 FM 출력 (← Gemini)
```json
{
  "intent": "trend_analysis",
  "detail": {
    "line": "",
    "model": "SONATA",
    "shift": "",
    "date_from": "2026-02-01",
    "date_to": "2026-02-28",
    "period": "this_month",
    "keyword": "추이"
  },
  "reasoning": "소나타의 이번 달 생산 추이를 묻고 있으므로 trend_analysis. 복합 의도 규칙: '추이'가 핵심이므로 trend_analysis."
}
```

> **포인트**: "불량률 추이" → `trend_analysis` (추이가 핵심) 복합 의도 판단 규칙 적용.

---

## Step 2: InfoAgent → Tool 호출

### 🔶 FM 출력 → Tool 호출
- `get_production_trend({"model": "SONATA", "days": 28})`

> **포인트**: FM이 `trend_analysis` 의도 → `get_production_trend` 도구 선택 가이드를 따름.

---

## Step 2.5: ToolNode (SQL 실행)

```sql
SELECT production_date,
       SUM(planned_qty) as planned,
       SUM(actual_qty) as actual,
       SUM(defect_qty) as defects,
       ROUND(SUM(actual_qty) * 100.0 / NULLIF(SUM(planned_qty), 0), 1) as achievement_rate,
       ROUND(SUM(defect_qty) * 100.0 / NULLIF(SUM(actual_qty), 0), 2) as defect_rate
FROM daily_production
WHERE model_id = 'SONATA'
GROUP BY production_date
ORDER BY production_date DESC
LIMIT 28
```

### Tool 결과 (일부)
```json
[
  {"production_date": "2026-02-01", "planned": 360, "actual": 342, "defects": 4, "achievement_rate": 95.0, "defect_rate": 1.17},
  {"production_date": "2026-02-02", "planned": 360, "actual": 348, "defects": 5, "achievement_rate": 96.7, "defect_rate": 1.44},
  ...
  {"production_date": "2026-02-15", "planned": 360, "actual": 338, "defects": 8, "achievement_rate": 93.9, "defect_rate": 2.37},
  ...
  {"production_date": "2026-02-28", "planned": 360, "actual": 347, "defects": 5, "achievement_rate": 96.4, "defect_rate": 1.44}
]
```

---

## Step 2 재진입: InfoAgent (Tool 결과 수신)

### 🔶 FM 출력 (← Gemini) → 텍스트 응답
```
## 소나타 2월 생산 추이 (LINE-1)

### 주간별 요약
| 주차 | 평균 달성률 | 평균 불량률 | 특이사항 |
|------|-----------|-----------|---------|
| 1주 (2/1~2/7) | 95.8% | 1.3% | 안정적 |
| 2주 (2/8~2/14) | 94.2% | 1.8% | 소폭 하락 |
| 3주 (2/15~2/21) | 93.1% | ⚠️ 2.4% | 불량률 상승 |
| 4주 (2/22~2/28) | 96.0% | 1.5% | 회복세 |

### 추세 분석
- **달성률**: 1~2주 소폭 하락 후 4주차 회복 (V자 반등)
- **불량률**: 3주차 일시 상승(2.4%) 후 4주차 정상화(1.5%)
- **일 평균 생산**: 345.2대/일 (계획 360대 대비 95.9%)

📈 4주차에 회복세를 보이고 있어 전반적으로 안정적입니다.
3주차 불량률 상승 원인을 확인해 보시는 것을 권장합니다.
```

> **포인트**: FM이 28일치 시계열 데이터를 주간 단위로 집계하여 추세를 분석.
> 단순 데이터 나열이 아닌 "V자 반등", "일시 상승 후 정상화" 등 패턴 해석 제공.

---

## 학습 포인트

1. **시계열 요약**: FM이 28일치 일별 데이터를 주간 단위로 재집계. Raw 데이터를 사용자가 이해하기 쉬운 형태로 변환.
2. **추세 해석**: 수치만이 아닌 "V자 반등", "회복세" 같은 정성적 분석 제공.
3. **후속 조치 제안**: "3주차 원인 확인 권장" — FM이 이상 구간을 감지하고 다음 행동을 유도.
4. **복합 의도 우선순위**: "소나타 생산 추이"는 production_query로도 볼 수 있지만, "추이"가 핵심이므로 trend_analysis로 분류.
