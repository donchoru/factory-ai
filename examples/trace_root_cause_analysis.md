# 예시 A1: 근본 원인 분석 — 3개 Tool 체이닝 심층 패턴

> **학습 목표**: "왜 달성률이 떨어졌어?"라는 원인 분석 요청에서 FM이
> 생산 요약 → 불량 통계 → 정지 이력 **3단계 체이닝**으로 근본 원인을 추적하는 과정을 추적한다.
> 단일 Tool로는 답할 수 없는 복합 분석 질문의 처리 패턴.

---

## 입력

```
이번 주 달성률이 왜 떨어졌어? 원인 분석해줘
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
    "period": "this_week",
    "keyword": "원인 분석"
  },
  "reasoning": "이번 주 달성률 하락 원인을 분석하는 요청. 생산 실적이 기본이므로 production_query. keyword에 '원인 분석'으로 체이닝 유도."
}
```

> **포인트**: 핵심은 "왜?"라는 원인 분석. FM이 production_query로 시작하되 keyword에 "원인 분석"을 넣어 후속 체이닝의 단서를 남김.

---

## Step 2: InfoAgent (정보조회, 첫 호출) — Round 1

### 🔷 FM 입력 (→ Gemini gemini-2.0-flash, 첫 호출)
- **System**: INFO_SYSTEM_PROMPT (도구 8개 + **체이닝 규칙**)
- **Human**:
```
사용자 질문: 이번 주 달성률이 왜 떨어졌어? 원인 분석해줘
의도: production_query
상세: {"line": "", "model": "", "shift": "", "date_from": "", "date_to": "", "period": "this_week", "keyword": "원인 분석"}

위 의도에 맞는 도구를 호출하여 정보를 조회하세요.
```

### 🔶 FM 출력 → Tool 호출 (Round 1)
- `get_production_summary({"period": "this_week"})`

> **판단**: FM이 우선 이번 주 생산 현황부터 파악. "원인 분석"은 데이터 확보 후 체이닝으로.

---

## Step 2.5: ToolNode (Round 1)

### Tool 결과
```json
{
  "period": "this_week",
  "by_line": [
    {"line_id": "LINE-1", "line_name": "1라인 (세단)", "total_planned": 2520, "total_actual": 2389, "total_defects": 38, "achievement_rate": 94.8, "defect_rate": 1.59},
    {"line_id": "LINE-2", "line_name": "2라인 (SUV)", "total_planned": 1680, "total_actual": 1512, "achievement_rate": 90.0, "defect_rate": 3.44},
    {"line_id": "LINE-3", "line_name": "3라인 (EV)", "total_planned": 1260, "total_actual": 1108, "achievement_rate": 87.9, "defect_rate": 3.07}
  ],
  "by_model": [...]
}
```

---

## Step 2 재진입: InfoAgent (Round 1 결과 수신) — 체이닝 판단

### 🔷 FM 입력 (재진입 Round 1)
- **Messages**: [AIMessage(tool_calls), ToolMessage(생산 요약)]
- **Guide**: "도구 실행 결과를 분석하세요. 사용자의 질문에 완전히 답하기 위해 추가 조회가 필요하면 도구를 더 호출하고..."

### 🔶 FM 출력 → Tool 호출 (Round 2)
- `get_defect_stats({"date_from": "2026-02-23", "date_to": "2026-02-28"})`

> **핵심 — 체이닝 발생 (Round 2)**:
> FM이 Round 1 결과를 분석:
> - LINE-2: 달성률 90.0%, 불량률 3.44% ← **가장 문제**
> - LINE-3: 달성률 87.9%, 불량률 3.07% ← **기준 미달**
> - "원인 분석"을 위해 불량 상세가 필요하다고 판단 → `get_defect_stats` 호출

---

## Step 2.5: ToolNode (Round 2)

### Tool 결과
```json
{
  "by_type": [
    {"defect_type": "paint", "total_count": 42, "affected_days": 6},
    {"defect_type": "assembly", "total_count": 35, "affected_days": 6},
    {"defect_type": "electric", "total_count": 28, "affected_days": 5},
    {"defect_type": "welding", "total_count": 18, "affected_days": 4}
  ],
  "by_line": [
    {"line_id": "LINE-2", "total_defects": 52, "defect_rate": 3.44},
    {"line_id": "LINE-3", "total_defects": 34, "defect_rate": 3.07},
    {"line_id": "LINE-1", "total_defects": 37, "defect_rate": 1.55}
  ],
  "recent_defects": [
    {"production_date": "2026-02-27", "line_id": "LINE-2", "defect_type": "paint", "defect_count": 8, "description": "도장 얼룩 다수 발생"},
    {"production_date": "2026-02-26", "line_id": "LINE-3", "defect_type": "electric", "defect_count": 7, "description": "배터리 모듈 커넥터 불량"},
    ...
  ]
}
```

---

## Step 2 재진입: InfoAgent (Round 2 결과 수신) — 추가 체이닝 판단

### 🔶 FM 출력 → Tool 호출 (Round 3)
- `get_downtime_history({"date_from": "2026-02-23", "date_to": "2026-02-28"})`

> **체이닝 Round 3**: FM이 불량 데이터만으로는 "왜?"에 완전히 답할 수 없다고 판단.
> 정지 이력까지 확인하여 **불량 ↔ 설비 정지 상관관계**를 분석하려는 것.
> 프롬프트의 체이닝 규칙: "최대 3라운드까지 도구 호출 가능"

---

## Step 2.5: ToolNode (Round 3)

### Tool 결과
```json
{
  "summary": [
    {"reason_type": "equipment_failure", "count": 4, "total_minutes": 310, "avg_minutes": 78},
    {"reason_type": "material_shortage", "count": 2, "total_minutes": 95, "avg_minutes": 48},
    {"reason_type": "quality_issue", "count": 1, "total_minutes": 45, "avg_minutes": 45}
  ],
  "details": [
    {"line_id": "LINE-2", "start_datetime": "2026-02-27T14:30", "duration_minutes": 72, "reason_type": "equipment_failure", "description": "용접 로봇 암 이상"},
    {"line_id": "LINE-3", "start_datetime": "2026-02-26T09:00", "duration_minutes": 95, "reason_type": "equipment_failure", "description": "배터리 모듈 조립기 이상"},
    {"line_id": "LINE-2", "start_datetime": "2026-02-25T09:15", "duration_minutes": 75, "reason_type": "equipment_failure", "description": "컨베이어 벨트 교체"},
    {"line_id": "LINE-2", "start_datetime": "2026-02-24T16:00", "duration_minutes": 68, "reason_type": "equipment_failure", "description": "도장 부스 필터 막힘"},
    {"line_id": "LINE-3", "start_datetime": "2026-02-24T11:00", "duration_minutes": 45, "reason_type": "material_shortage", "description": "배터리 셀 공급 지연"},
    {"line_id": "LINE-2", "start_datetime": "2026-02-23T08:30", "duration_minutes": 50, "reason_type": "material_shortage", "description": "SUV 범퍼 부품 지연"},
    {"line_id": "LINE-3", "start_datetime": "2026-02-23T22:00", "duration_minutes": 45, "reason_type": "quality_issue", "description": "전장 품질 긴급 점검"}
  ]
}
```

---

## Step 2 재진입: InfoAgent (Round 3 결과 수신) — 최종 응답 생성

### 🔶 FM 출력 (← Gemini) → 텍스트 응답
```
## 이번 주(2/23~2/28) 달성률 하락 근본 원인 분석

### 1. 현황 요약
| 라인 | 달성률 | 불량률 | 정지 횟수 | 정지 시간 |
|------|--------|--------|----------|----------|
| LINE-1 (세단) | 94.8% | 1.55% | 0회 | 0분 |
| LINE-2 (SUV) | ⚠️ 90.0% | ⚠️ 3.44% | **4회** | **265분** |
| LINE-3 (EV) | ⚠️ 87.9% | ⚠️ 3.07% | **3회** | **185분** |

### 2. 근본 원인 분석

#### 📌 LINE-2 (달성률 90.0% — 가장 큰 하락)
- **설비 고장 3회**(215분): 용접 로봇, 컨베이어, 도장 부스
- **자재 부족 1회**(50분): SUV 범퍼 부품 지연
- **도장 불량 집중**: 전체 불량 52건 중 도장 20건(38%) → 도장 부스 필터 막힘(2/24)과 직접 연관
- ⚡ **핵심**: 도장 공정 설비 노후화 + 부품 공급 불안정의 이중 문제

#### 📌 LINE-3 (달성률 87.9% — 기준 미달)
- **설비 고장 1회**(95분): 배터리 모듈 조립기 → 이 하나가 95분 장기 정지
- **자재 부족 1회**(45분): 배터리 셀 공급 지연
- **전장 불량 집중**: 전체 불량 34건 중 전장 15건(44%) → 배터리 관련 불량이 지배적
- ⚡ **핵심**: EV 라인 특유의 배터리 공급망 + 모듈 조립 공정 리스크

#### ✅ LINE-1 (달성률 94.8% — 양호)
- 정지 0회, 불량률 1.55%로 기준 이내. 이번 주 문제 없음.

### 3. 개선 권고
1. **LINE-2 도장 공정**: 필터 교체 주기 단축 + 도장 부스 예방 정비 강화
2. **LINE-3 배터리 공급**: 셀 공급업체 이중화 + 안전 재고 수준 상향
3. **LINE-3 조립기**: 배터리 모듈 조립기 정밀 점검 (1회 95분은 과도)

---
📊 **결론**: 이번 주 달성률 하락의 **80%는 LINE-2와 LINE-3의 설비 고장**이 원인.
LINE-1은 안정적이므로 LINE-2/3의 설비 노후화 및 공급망 리스크에 집중 대응이 필요합니다.
```

---

## FM 호출 요약

| 단계 | FM 역할 | Tool | 수집 데이터 |
|------|---------|------|-----------|
| IntentAgent | 의도 분류 | — | — |
| InfoAgent Round 1 | **현황 파악** | `get_production_summary` | 라인별 달성률/불량률 |
| InfoAgent Round 2 | **불량 분석** | `get_defect_stats` | 유형별/라인별 불량 상세 |
| InfoAgent Round 3 | **정지 분석** | `get_downtime_history` | 사유별/라인별 정지 이력 |
| InfoAgent 최종 | **교차 종합** | — | 3개 데이터 교차 → 근본 원인 |

**총 FM 호출: 5회** (IntentAgent 1 + InfoAgent 4)
**도구 호출: 3회** (MAX_TOOL_ROUNDS 한도 전부 사용)

---

## 학습 포인트

1. **3단계 체이닝**: 현황→불량→정지 순서로 점점 깊은 데이터를 수집. 각 라운드가 이전 결과를 참고하여 다음 Tool을 결정.
2. **교차 분석**: FM이 3개 Tool의 결과를 교차하여 "도장 부스 필터 막힘(정지) → 도장 불량 38%(불량) → 달성률 90%(생산)" 인과관계를 도출.
3. **MAX_TOOL_ROUNDS=3 활용**: 이 예시가 3라운드를 모두 사용하는 최대 체이닝 케이스. 4라운드 이상 시 "더 이상 도구를 호출하지 말고..." 가이드가 강제 종료.
4. **개선 권고**: FM이 데이터 분석을 넘어 실행 가능한 개선 방안까지 제시. 공장 관리자에게 실질적 가치 제공.
5. **구조화된 응답**: 현황 요약 → 라인별 원인 → 개선 권고 → 결론 순서로 보고서 형식. 의사결정에 바로 활용 가능.
