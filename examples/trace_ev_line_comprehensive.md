# 예시 A4: EV 라인 종합 분석 — 전방위 진단 패턴

> **학습 목표**: "전반적으로 분석해줘"라는 개방형 요청에서 FM이
> 라인 현황 → 불량 → 정지 이력을 **자율적으로** 체이닝하여
> 특정 라인의 전방위 진단 리포트를 생성하는 패턴을 추적한다.
> 사용자가 구체적 지시를 하지 않아도 FM이 필요한 데이터를 스스로 판단.

---

## 입력

```
전기차 라인 전반적으로 분석해줘. 문제점이랑 개선할 점 정리해서
```

---

## Step 1: IntentAgent (의도분석)

### 🔶 FM 출력 (← Gemini)
```json
{
  "intent": "line_status",
  "detail": {
    "line": "LINE-3",
    "model": "",
    "shift": "",
    "date_from": "",
    "date_to": "",
    "period": "",
    "keyword": "전반적 분석"
  },
  "reasoning": "전기차라인 → LINE-3. 전반적 분석 요청이므로 라인 현황부터 시작. line_status."
}
```

> **포인트**: "전기차 라인" → LINE-3 매핑. "전반적으로 분석"은 단일 의도로 분류하기 어렵지만,
> 라인 현황이 가장 포괄적인 출발점이므로 line_status로 시작. keyword에 "전반적 분석"을 넣어 체이닝 유도.

---

## Step 2: InfoAgent — Round 1

### 🔶 FM 출력 → Tool 호출 (Round 1)
- `get_line_status({"line": "LINE-3"})`

---

## Step 2.5: ToolNode (Round 1)

### Tool 결과
```json
[
  {"line_id": "LINE-3", "line_name": "3라인 (EV)", "vehicle_type": "EV",
   "capacity_per_shift": 60, "status": "ACTIVE",
   "recent_achievement": 88.7, "today_actual": 170, "today_planned": 180,
   "recent_downtime_count": 3, "recent_defect_rate": 2.51}
]
```

---

## Step 2 재진입: InfoAgent (Round 1) — 체이닝 판단

### FM의 분석
```
LINE-3: 달성률 88.7%(⚠️ <90%), 불량률 2.51%(⚠️ >2%), 정지 3회
→ "전반적 분석"이므로 불량 상세와 정지 원인도 필요
```

### 🔶 FM 출력 → Tool 호출 (Round 2)
- `get_defect_stats({"line": "LINE-3"})`

---

## Step 2.5: ToolNode (Round 2)

### Tool 결과
```json
{
  "by_type": [
    {"defect_type": "electric", "total_count": 98, "affected_days": 25},
    {"defect_type": "assembly", "total_count": 62, "affected_days": 20},
    {"defect_type": "welding", "total_count": 38, "affected_days": 16},
    {"defect_type": "paint", "total_count": 21, "affected_days": 12}
  ],
  "by_line": [
    {"line_id": "LINE-3", "total_defects": 219, "total_produced": 5040, "defect_rate": 4.35}
  ],
  "recent_defects": [
    {"production_date": "2026-02-28", "defect_type": "electric", "defect_count": 6, "description": "배터리 셀 전압 편차 초과"},
    {"production_date": "2026-02-27", "defect_type": "assembly", "defect_count": 4, "description": "모터 마운트 체결 토크 미달"},
    {"production_date": "2026-02-26", "defect_type": "electric", "defect_count": 7, "description": "BMS 커넥터 접촉 불량"},
    ...
  ]
}
```

---

## Step 2 재진입: InfoAgent (Round 2) — 마지막 체이닝

### 🔶 FM 출력 → Tool 호출 (Round 3)
- `get_downtime_history({"line": "LINE-3"})`

---

## Step 2.5: ToolNode (Round 3)

### Tool 결과
```json
{
  "summary": [
    {"reason_type": "equipment_failure", "count": 2, "total_minutes": 165, "avg_minutes": 83},
    {"reason_type": "material_shortage", "count": 1, "total_minutes": 60, "avg_minutes": 60}
  ],
  "details": [
    {"start_datetime": "2026-02-24T22:00", "duration_minutes": 95, "reason_type": "equipment_failure",
     "description": "배터리 모듈 조립기 이상 — 정렬 센서 오작동"},
    {"start_datetime": "2026-02-18T14:00", "duration_minutes": 60, "reason_type": "material_shortage",
     "description": "배터리 셀 공급 지연 — 공급업체 품질 이슈"},
    {"start_datetime": "2026-02-10T06:00", "duration_minutes": 70, "reason_type": "equipment_failure",
     "description": "전장 검사기 교정 — 센서 드리프트 보정"}
  ]
}
```

---

## Step 2 재진입: InfoAgent (Round 3) — 최종 종합 응답

### 🔶 FM 출력 (← Gemini) → 텍스트 응답
```
## LINE-3 (전기차 라인) 종합 분석 리포트

### 📊 1. 핵심 지표 현황
| 항목 | 수치 | 상태 |
|------|------|------|
| 월간 달성률 | 88.7% | ⚠️ 기준(90%) 미달 |
| 월간 불량률 | 4.35% | ⚠️ 기준(2%) 초과 |
| 정지 횟수 | 3회/월 | 설비 2회 + 자재 1회 |
| 총 정지 시간 | 225분 (3.75시간) | 설비 165분 + 자재 60분 |
| 오늘(2/28) 실적 | 170/180대 (94.4%) | 소폭 회복 |

### 🔍 2. 불량 분석 — EV 특수성 부각

| 불량 유형 | 건수 | 비중 | EV 특수 여부 |
|----------|------|------|-------------|
| **전장(electric)** | **98건** | **45%** | ⚡ **EV 핵심** |
| 조립(assembly) | 62건 | 28% | △ 모터 마운트 등 |
| 용접(welding) | 38건 | 17% | - 일반 |
| 도장(paint) | 21건 | 10% | - 일반 |

⚡ **핵심 발견**: 전장 불량(45%)이 압도적 1위.
- 배터리 셀 전압 편차 (반복 발생)
- BMS 커넥터 접촉 불량
- 이는 EV 라인 특유의 고전압 부품 민감도에서 기인

### 🔧 3. 설비 정지 분석

| 일시 | 원인 | 시간 | 설명 |
|------|------|------|------|
| 2/24 22:00 | 설비 고장 | **95분** | 배터리 모듈 조립기 정렬 센서 |
| 2/18 14:00 | 자재 부족 | 60분 | 배터리 셀 공급 지연 |
| 2/10 06:00 | 설비 고장 | 70분 | 전장 검사기 센서 드리프트 |

⚠️ **패턴**: 3건 모두 **배터리/전장 관련** → EV 라인의 전기적 정밀도 요구가 정지의 근본 원인

### 🔗 4. 문제 간 연관 관계

```
배터리 셀 품질 이슈 (공급업체)
    ├→ 셀 전압 편차 → 전장 불량 45% (직접 원인)
    └→ 공급 지연 → 자재 부족 정지 60분 (간접 영향)

전장 설비 정밀도
    ├→ 조립기 센서 오작동 → 95분 장기 정지
    ├→ 검사기 드리프트 → 70분 정지 + 불량 미검출 가능
    └→ 전체 달성률 88.7% 하락의 주요 원인
```

### ✅ 5. 개선 로드맵

| 우선순위 | 구분 | 조치 | 기대 효과 |
|---------|------|------|----------|
| **P1** | 단기 | 배터리 셀 수입검사 강화 (전압 편차 0.05V 이내) | 전장 불량 -30% |
| **P2** | 단기 | 조립기 정렬 센서 예방 교체 (2주 주기) | 장기 정지 방지 |
| **P3** | 중기 | 배터리 셀 공급업체 이중화 | 공급 리스크 해소 |
| **P4** | 중기 | 전장 검사기 자동 교정 시스템 도입 | 드리프트 사전 감지 |
| **P5** | 장기 | EV 전용 불량 분류 체계 도입 (전장→세분화) | 정밀 관리 가능 |

---
📊 **총평**: LINE-3는 EV 라인 특유의 **배터리/전장 리스크**가 성과를 지배하고 있습니다.
일반적인 자동차 공정(도장, 용접) 불량은 비교적 적은 반면, 고전압 전장 부품의 품질 관리가 핵심 과제입니다.
단기적으로 **셀 수입검사 강화(P1)**와 **센서 예방 교체(P2)**만으로도 유의미한 개선이 기대됩니다.
```

---

## FM 호출 요약

| Round | Tool | 목적 | 수집 데이터 |
|-------|------|------|-----------|
| 1 | `get_line_status(LINE-3)` | 현황 진단 | 달성률, 불량률, 정지 횟수 |
| 2 | `get_defect_stats(LINE-3)` | 불량 심층 | 유형별 분포, 최근 상세 |
| 3 | `get_downtime_history(LINE-3)` | 정지 원인 | 사유별 + 시간별 상세 |

**총 FM 호출: 5회** / **도구 호출: 3회** (MAX 한도)

---

## 학습 포인트

1. **자율적 체이닝**: 사용자가 "전반적으로 분석해줘"라고만 했는데 FM이 3개 Tool을 자율적으로 선택. 어떤 데이터가 "전반적 분석"에 필요한지 FM이 판단.
2. **도메인 특수성 인식**: FM이 "EV 라인"의 특수성(전장 불량, 배터리 공급망)을 인식하고 분석에 반영. 일반 공장 vs EV 공장의 차이를 이해.
3. **인과관계 맵**: 불량 데이터와 정지 데이터를 교차하여 "배터리 셀 품질 → 전장 불량 → 달성률 하락" 인과관계를 트리 구조로 시각화.
4. **개선 로드맵**: 단기/중기/장기 + 우선순위(P1~P5)로 구조화된 실행 계획. 경영진 보고서에 바로 사용 가능한 수준.
5. **보고서 형식**: 핵심지표 → 불량분석 → 정지분석 → 연관관계 → 개선 로드맵 → 총평. 제조업 표준 분석 리포트 구조.
