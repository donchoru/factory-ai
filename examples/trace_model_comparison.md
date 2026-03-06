# 예시 8: 차종별 비교 — trend_analysis에서 2개 Tool 활용 패턴

> **학습 목표**: `trend_analysis` 의도에서 FM이 프롬프트 규칙("trend_analysis → get_production_trend + 필요시 get_model_comparison")에 따라
> `get_model_comparison` Tool을 선택하는 과정을 추적한다.

---

## 입력

```
이번 달 어떤 차종이 제일 잘 나가?
```

---

## Step 1: IntentAgent (의도분석)

### 🔶 FM 출력 (← Gemini)
```json
{
  "intent": "trend_analysis",
  "detail": {
    "line": "",
    "model": "",
    "shift": "",
    "date_from": "2026-02-01",
    "date_to": "2026-02-28",
    "period": "this_month",
    "keyword": "비교"
  },
  "reasoning": "차종 간 생산 비교 분석을 요청하므로 trend_analysis"
}
```

> **포인트**: "어떤 차종이 제일 잘 나가?" → trend_analysis.
> "어떤 라인이 제일 잘 돌아가?" → line_status 와 대비됨 (복합 의도 판단 규칙).

---

## Step 2: InfoAgent → Tool 호출

### 🔶 FM 출력 → Tool 호출
- `get_model_comparison({"date_from": "2026-02-01", "date_to": "2026-02-28"})`

---

## Step 2.5: ToolNode (SQL 실행)

### Tool 결과
```json
[
  {"model_id": "SONATA", "model_name": "소나타", "line_id": "LINE-1",
   "working_days": 28, "total_planned": 10080, "total_actual": 9656,
   "total_defects": 135, "achievement_rate": 95.8, "defect_rate": 1.40, "daily_avg": 345},
  {"model_id": "TUCSON", "model_name": "투싼", "line_id": "LINE-2",
   "working_days": 28, "total_planned": 3780, "total_actual": 3542,
   "total_defects": 98, "achievement_rate": 93.7, "defect_rate": 2.77, "daily_avg": 127},
  {"model_id": "GV70", "model_name": "GV70", "line_id": "LINE-2",
   "working_days": 28, "total_planned": 2940, "total_actual": 2788,
   "total_defects": 67, "achievement_rate": 94.8, "defect_rate": 2.40, "daily_avg": 100},
  {"model_id": "IONIQ6", "model_name": "아이오닉6", "line_id": "LINE-3",
   "working_days": 28, "total_planned": 5040, "total_actual": 4720,
   "total_defects": 142, "achievement_rate": 93.7, "defect_rate": 3.01, "daily_avg": 169}
]
```

---

## Step 2 재진입: InfoAgent (Tool 결과 수신)

### 🔶 FM 출력 (← Gemini) → 텍스트 응답
```
## 2월 차종별 생산 비교

| 순위 | 차종 | 라인 | 총 생산 | 달성률 | 불량률 | 일 평균 |
|------|------|------|---------|--------|--------|---------|
| 1 | 소나타 | LINE-1 | 9,656대 | 95.8% | 1.40% | 345대/일 |
| 2 | 아이오닉6 | LINE-3 | 4,720대 | 93.7% | ⚠️ 3.01% | 169대/일 |
| 3 | 투싼 | LINE-2 | 3,542대 | 93.7% | ⚠️ 2.77% | 127대/일 |
| 4 | GV70 | LINE-2 | 2,788대 | 94.8% | ⚠️ 2.40% | 100대/일 |

### 핵심 분석
- **생산량 1위**: 소나타 (9,656대) — 달성률도 최고(95.8%)로 가장 안정적
- **불량률 주의**: 아이오닉6(3.01%)가 가장 높음 ⚠️ — EV 라인 품질 관리 필요
- **LINE-2 공유**: 투싼+GV70이 같은 라인 공유, 합산 달성률 94.2%
```

---

## 학습 포인트

1. **도구 선택 가이드의 "필요시"**: `trend_analysis → get_production_trend + 필요시 get_model_comparison`. FM이 "차종 비교"라는 맥락에서 get_model_comparison이 더 적합하다고 판단.
2. **순위 표시**: FM이 생산량 기준으로 자동 순위를 매겨서 "어떤 차종이 제일 잘 나가?"에 직접적으로 답변.
3. **LINE-2 공유 인사이트**: 같은 라인에서 2개 모델을 생산하는 구조적 정보를 FM이 자동 파악.
