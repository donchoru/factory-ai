# 예시 9: 도구 체이닝 — 순차 호출 패턴

> **학습 목표**: 1차 도구 결과에서 정보를 추출하여 2차 도구를 추가 호출하는
> **도구 체이닝(순차 실행)** 패턴의 전체 흐름을 FM I/O 관점에서 추적한다.

---

## 입력

```
소나타 불량률이 높은데 왜 그래? 정지 이력도 같이 보여줘
```

---

## Step 1: IntentAgent (의도분석)

### 🔶 FM 출력 (← Gemini)
```json
{
  "intent": "defect_query",
  "detail": {
    "line": "",
    "model": "SONATA",
    "shift": "",
    "date_from": "",
    "date_to": "",
    "period": "",
    "keyword": "정지 이력"
  },
  "reasoning": "소나타 불량률과 정지 이력의 상관관계를 분석 요청. 불량이 핵심이므로 defect_query"
}
```

> **포인트**: "불량률 + 정지 이력" 복합 질문. 핵심이 불량이므로 defect_query로 분류.
> keyword에 "정지 이력"이 추출되어 FM이 체이닝을 판단하는 단서.

---

## Step 2: InfoAgent (정보조회, 첫 호출)

### 🔶 FM 출력 → Tool 호출 (Round 1)
- `get_defect_stats({"model": "SONATA"})`

> **포인트**: 1차로 소나타 불량 통계 조회. 체이닝 규칙에 따라 결과 분석 후 2차 호출 예정.

---

## Step 2.5: ToolNode (SQL 실행, Round 1)

### Tool 결과
```json
{
  "by_type": [
    {"defect_type": "paint", "total_count": 58, "affected_days": 22},
    {"defect_type": "welding", "total_count": 42, "affected_days": 18},
    {"defect_type": "assembly", "total_count": 23, "affected_days": 12},
    {"defect_type": "electric", "total_count": 12, "affected_days": 8}
  ],
  "by_line": [
    {"line_id": "LINE-1", "total_defects": 135, "total_produced": 9656, "defect_rate": 1.40}
  ],
  "recent_defects": [...]
}
```

---

## Step 2 재진입: InfoAgent (Tool 결과 수신, Round 1)

### 🔷 FM 입력 (재진입 Round 1)
- **System**: INFO_SYSTEM_PROMPT (도구 8개 + 체이닝 규칙)
- **Messages**: [AIMessage(tool_calls), ToolMessage(불량 통계)]
- **Guide**: "도구 실행 결과를 분석하세요. 사용자의 질문에 완전히 답하기 위해 추가 조회가 필요하면 도구를 더 호출하고, 충분한 정보가 모였으면 최종 응답을 생성하세요."

### 🔶 FM 출력 → Tool 호출 요청 (Round 2)
- `get_downtime_history({"line": "LINE-1"})`

> **핵심 — 체이닝 발생**: FM이 다음을 판단:
> 1. 불량 통계 확인 완료 ✅
> 2. 사용자가 "정지 이력도 같이"라고 요청 → 추가 조회 필요
> 3. 소나타 = LINE-1이므로 LINE-1 정지 이력 조회
>
> 프롬프트의 체이닝 예시와 정확히 일치:
> ```
> "소나타 불량률이 높은데 왜 그래?"
> → 1차: get_defect_stats(model="SONATA") → 2차: get_downtime_history(line="LINE-1")
> ```

---

## Step 2.5: ToolNode (SQL 실행, Round 2)

### Tool 결과
```json
{
  "summary": [
    {"reason_type": "equipment_failure", "count": 2, "total_minutes": 145, "avg_minutes": 73},
    {"reason_type": "planned_maintenance", "count": 1, "total_minutes": 120, "avg_minutes": 120}
  ],
  "details": [
    {"line_id": "LINE-1", "start_datetime": "2026-02-26T10:00:00", "duration_minutes": 85, "reason_type": "equipment_failure", "description": "도장 건조 램프 교체"},
    {"line_id": "LINE-1", "start_datetime": "2026-02-19T06:00:00", "duration_minutes": 120, "reason_type": "planned_maintenance", "description": "월간 정비"},
    {"line_id": "LINE-1", "start_datetime": "2026-02-12T15:30:00", "duration_minutes": 60, "reason_type": "equipment_failure", "description": "용접 전극 마모"}
  ]
}
```

---

## Step 2 재진입: InfoAgent (Tool 결과 수신, Round 2)

### 🔶 FM 출력 (← Gemini) → 텍스트 응답
```
## 소나타(LINE-1) 불량 + 정지 상관분석

### 불량 현황
| 불량 유형 | 건수 | 비중 |
|----------|------|------|
| 도장 | 58건 | 43% |
| 용접 | 42건 | 31% |
| 조립 | 23건 | 17% |
| 전장 | 12건 | 9% |

**불량률**: 1.40% (기준 2% 미만으로 양호)

### 설비 정지 이력
| 일시 | 사유 | 시간 | 설명 |
|------|------|------|------|
| 2/26 10:00 | 설비 고장 | 85분 | 도장 건조 램프 교체 |
| 2/19 06:00 | 정기 정비 | 120분 | 월간 정비 |
| 2/12 15:30 | 설비 고장 | 60분 | 용접 전극 마모 |

### 상관관계 분석
📊 **도장 불량(43%)이 최다** + **도장 설비 고장(2/26 램프 교체)** → 도장 공정이 LINE-1의 핵심 개선 포인트.
용접 불량(31%)도 용접 전극 마모(2/12)와 연관 가능성 있음.

실제 불량률 1.40%는 기준(2%) 이내이나, 도장 공정의 설비 노후화에 주의가 필요합니다.
```

> **포인트**: FM이 2개 Tool 결과를 교차 분석:
> - 도장 불량 43% + 도장 설비 고장 → 상관관계 도출
> - 용접 불량 31% + 용접 전극 마모 → 연관 가능성 제시

---

## FM 호출 요약

| 단계 | FM 역할 | 입력 | 출력 |
|------|---------|------|------|
| IntentAgent | 의도 분류 | System + Human(질문) | JSON: `defect_query` |
| InfoAgent 1차 | Tool 선택 | System + Human(질문+의도) | tool_call: `get_defect_stats` |
| InfoAgent Round 1 | **체이닝 판단** | System + Messages + Guide | tool_call: `get_downtime_history` |
| InfoAgent Round 2 | 응답 생성 | System + Messages + Guide | 텍스트: 상관분석 |

**총 FM 호출: 4회** (IntentAgent 1 + InfoAgent 3)
**도구 호출: 2회** (Round 1: 불량 통계 + Round 2: 정지 이력)

---

## 학습 포인트

1. **도구 체이닝**: 1차 결과(불량 통계)를 분석 후, 사용자 요청("정지 이력도")에 따라 2차 도구(정지 이력)를 자동 호출.
2. **교차 분석**: FM이 2개 다른 도메인(불량 + 정지)의 데이터를 교차하여 "도장 불량 ↔ 도장 설비 고장" 상관관계 도출.
3. **체이닝 규칙 정확 적용**: INFO_SYSTEM_PROMPT의 체이닝 예시 `defect_stats → downtime_history`와 정확히 일치하는 실행 흐름.
4. **MAX_TOOL_ROUNDS=3 안전장치**: 최대 3라운드까지만 도구 호출 허용. 이 예시는 2라운드로 완료.
