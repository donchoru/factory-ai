# 예시 4: 설비 정지 이력 — 사유별 분류 패턴

> **학습 목표**: `downtime_query` 의도에서 `get_downtime_history` Tool이 사유별 요약 + 상세 내역을
> 함께 반환하고, FM이 이를 구조화하여 원인 분석까지 제공하는 패턴을 추적한다.

---

## 입력

```
2라인 설비 정지 이력 보여줘
```

---

## Step 1: IntentAgent (의도분석)

### 🔶 FM 출력 (← Gemini)
```json
{
  "intent": "downtime_query",
  "detail": {
    "line": "LINE-2",
    "model": "",
    "shift": "",
    "date_from": "",
    "date_to": "",
    "period": "",
    "keyword": ""
  },
  "reasoning": "2라인의 설비 정지 이력을 묻고 있으므로 downtime_query. 2라인 → LINE-2"
}
```

> **포인트**: "2라인" → `LINE-2` 매핑. 한국어 → ID 매핑규칙 적용.

---

## Step 2: InfoAgent → Tool 호출

### 🔶 FM 출력 → Tool 호출
- `get_downtime_history({"line": "LINE-2"})`

---

## Step 2.5: ToolNode (SQL 실행)

### Tool 결과
```json
{
  "summary": [
    {"reason_type": "equipment_failure", "count": 3, "total_minutes": 215, "avg_minutes": 72},
    {"reason_type": "material_shortage", "count": 1, "total_minutes": 45, "avg_minutes": 45},
    {"reason_type": "quality_issue", "count": 1, "total_minutes": 30, "avg_minutes": 30}
  ],
  "details": [
    {"line_id": "LINE-2", "start_datetime": "2026-02-27T14:30:00", "end_datetime": "2026-02-27T15:42:00",
     "duration_minutes": 72, "reason_type": "equipment_failure", "description": "용접 로봇 암 이상"},
    {"line_id": "LINE-2", "start_datetime": "2026-02-25T09:15:00", "end_datetime": "2026-02-25T10:30:00",
     "duration_minutes": 75, "reason_type": "equipment_failure", "description": "컨베이어 벨트 교체"},
    {"line_id": "LINE-2", "start_datetime": "2026-02-22T16:00:00", "end_datetime": "2026-02-22T17:08:00",
     "duration_minutes": 68, "reason_type": "equipment_failure", "description": "도장 부스 필터 막힘"},
    {"line_id": "LINE-2", "start_datetime": "2026-02-20T11:00:00", "end_datetime": "2026-02-20T11:45:00",
     "duration_minutes": 45, "reason_type": "material_shortage", "description": "SUV 범퍼 부품 공급 지연"},
    {"line_id": "LINE-2", "start_datetime": "2026-02-18T08:30:00", "end_datetime": "2026-02-18T09:00:00",
     "duration_minutes": 30, "reason_type": "quality_issue", "description": "도장 품질 불량 긴급 점검"}
  ]
}
```

---

## Step 2 재진입: InfoAgent (Tool 결과 수신)

### 🔶 FM 출력 (← Gemini) → 텍스트 응답
```
## LINE-2 (SUV라인) 설비 정지 이력

### 사유별 요약
| 사유 | 횟수 | 총 정지 시간 | 평균 |
|------|------|-------------|------|
| 설비 고장 | 3회 | 215분 (3시간 35분) | 72분 |
| 자재 부족 | 1회 | 45분 | 45분 |
| 품질 이슈 | 1회 | 30분 | 30분 |

### 상세 내역
| 일시 | 사유 | 시간 | 설명 |
|------|------|------|------|
| 2/27 14:30 | 설비 고장 | 72분 | 용접 로봇 암 이상 |
| 2/25 09:15 | 설비 고장 | 75분 | 컨베이어 벨트 교체 |
| 2/22 16:00 | 설비 고장 | 68분 | 도장 부스 필터 막힘 |
| 2/20 11:00 | 자재 부족 | 45분 | SUV 범퍼 부품 공급 지연 |
| 2/18 08:30 | 품질 이슈 | 30분 | 도장 품질 불량 긴급 점검 |

⚠️ **설비 고장**이 전체 정지의 74%(215/290분)를 차지합니다.
특히 도장 관련 문제(필터 막힘, 품질 불량)가 반복되고 있어 예방 정비 검토가 필요합니다.
```

---

## 학습 포인트

1. **요약 + 상세 동시 제공**: Tool이 summary와 details를 함께 반환하여 FM이 계층적 응답 생성.
2. **시간 변환**: FM이 215분 → "3시간 35분"으로 사용자 친화적 변환.
3. **패턴 분석**: FM이 "도장 관련 문제가 반복"이라는 패턴을 자동 감지하여 인사이트 제공.
4. **한국어 → ID → 한국어**: 사용자 "2라인" → detail `LINE-2` → 응답 "LINE-2 (SUV라인)".
