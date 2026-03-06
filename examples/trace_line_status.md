# 예시 3: 라인 현황 조회 — 단일 Tool 패턴

> **학습 목표**: `line_status` 의도에서 `get_line_status` Tool 하나로 충분한 정보를 가져와
> 달성률과 불량률을 기반으로 주의 사항을 표시하는 패턴을 추적한다.

---

## 입력

```
지금 라인별 현황 어때?
```

---

## Step 1: IntentAgent (의도분석)

### 🔶 FM 출력 (← Gemini)
```json
{
  "intent": "line_status",
  "detail": {
    "line": "",
    "model": "",
    "shift": "",
    "date_from": "",
    "date_to": "",
    "period": "",
    "keyword": ""
  },
  "reasoning": "전체 라인의 현재 현황/가동 상태를 묻고 있으므로 line_status"
}
```

---

## Step 2: InfoAgent (정보조회, 첫 호출)

### 🔶 FM 출력 (← Gemini) → Tool 호출 요청
- `get_line_status({})`

> **포인트**: `line` 파라미터가 비어있으므로 전체 라인 조회.

---

## Step 2.5: ToolNode (SQL 실행)

```sql
SELECT pl.line_id, pl.line_name, pl.vehicle_type, pl.capacity_per_shift, pl.status,
       (SELECT ROUND(AVG(achievement_rate), 1) FROM daily_production
        WHERE line_id = pl.line_id AND production_date >= '2026-02-22') as recent_achievement,
       (SELECT SUM(actual_qty) FROM daily_production
        WHERE line_id = pl.line_id AND production_date = '2026-02-28') as today_actual,
       (SELECT SUM(planned_qty) FROM daily_production
        WHERE line_id = pl.line_id AND production_date = '2026-02-28') as today_planned,
       (SELECT COUNT(*) FROM downtime
        WHERE line_id = pl.line_id AND start_datetime >= '2026-02-22') as recent_downtime_count,
       (SELECT ROUND(SUM(defect_qty) * 100.0 / NULLIF(SUM(actual_qty), 0), 2)
        FROM daily_production
        WHERE line_id = pl.line_id AND production_date >= '2026-02-22') as recent_defect_rate
FROM production_lines pl
ORDER BY pl.line_id
```

### Tool 결과
```json
[
  {"line_id": "LINE-1", "line_name": "1라인 (세단)", "vehicle_type": "SEDAN", "capacity_per_shift": 120, "status": "ACTIVE",
   "recent_achievement": 96.2, "today_actual": 347, "today_planned": 360, "recent_downtime_count": 2, "recent_defect_rate": 1.42},
  {"line_id": "LINE-2", "line_name": "2라인 (SUV)", "vehicle_type": "SUV", "capacity_per_shift": 80, "status": "ACTIVE",
   "recent_achievement": 91.5, "today_actual": 228, "today_planned": 240, "recent_downtime_count": 5, "recent_defect_rate": 3.18},
  {"line_id": "LINE-3", "line_name": "3라인 (EV)", "vehicle_type": "EV", "capacity_per_shift": 60, "status": "ACTIVE",
   "recent_achievement": 88.7, "today_actual": 170, "today_planned": 180, "recent_downtime_count": 3, "recent_defect_rate": 2.51}
]
```

---

## Step 2 재진입: InfoAgent (Tool 결과 수신)

### 🔶 FM 출력 (← Gemini) → 텍스트 응답
```
## 라인별 현황 (2026-02-28 기준)

| 라인 | 차종 | 상태 | 오늘 실적 | 최근 달성률 | 불량률 | 정지 횟수 |
|------|------|------|----------|-----------|--------|----------|
| LINE-1 (세단) | SEDAN | ✅ ACTIVE | 347/360대 | 96.2% | 1.42% | 2회 |
| LINE-2 (SUV) | SUV | ✅ ACTIVE | 228/240대 | 91.5% | ⚠️ 3.18% | 5회 |
| LINE-3 (EV) | EV | ✅ ACTIVE | 170/180대 | ⚠️ 88.7% | ⚠️ 2.51% | 3회 |

### 주의 사항
- **LINE-3**: 달성률 88.7%로 90% 미만 ⚠️ — 정지 3회 영향 가능
- **LINE-2**: 불량률 3.18%로 기준(2%) 초과 ⚠️ — 정지 5회로 가장 잦음
```

> **포인트**: FM이 응답 규칙 2가지를 동시 적용:
> - 달성률 90% 미만 → ⚠️ (LINE-3)
> - 불량률 2% 이상 → ⚠️ (LINE-2, LINE-3)

---

## FM 호출 요약

| 단계 | FM 역할 | 입력 | 출력 |
|------|---------|------|------|
| IntentAgent | 의도 분류 | "지금 라인별 현황 어때?" | `line_status` |
| InfoAgent 1차 | Tool 선택 | 질문+의도+상세 | tool_call: `get_line_status` |
| InfoAgent 재진입 | 응답 생성 | Messages(AI+Tool결과) | 라인별 현황 표 + 주의사항 |

**총 FM 호출: 3회**

---

## 학습 포인트

1. **단일 Tool로 충분**: `get_line_status`가 달성률, 불량률, 정지 횟수까지 서브쿼리로 한번에 조회. 체이닝 불필요.
2. **다중 경고 규칙**: FM이 달성률(<90%)과 불량률(>2%) 두 가지 규칙을 동시에 적용.
3. **데이터 기반 인사이트**: FM이 "정지 3회 영향 가능"처럼 다른 지표와의 상관관계를 추론.
