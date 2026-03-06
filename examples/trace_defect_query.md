# 예시 2: 불량 통계 조회 — 복합 결과 처리 패턴

> **학습 목표**: `defect_query` 의도에서 FM이 `get_defect_stats` Tool의 복합 결과
> (유형별 + 라인별 + 최근 상세)를 종합하여 사용자 친화적 응답을 생성하는 과정을 추적한다.

---

## 입력

```
이번 달 불량 현황 알려줘
```

---

## Step 1: IntentAgent (의도분석)

### 🔷 FM 입력 (→ Gemini gemini-2.0-flash)
- **System**: INTENT_SYSTEM_PROMPT (의도 6개 + JSON형식 + 매핑규칙)
- **Human**:
```
이번 달 불량 현황 알려줘
```

### 🔶 FM 출력 (← Gemini)
```json
{
  "intent": "defect_query",
  "detail": {
    "line": "",
    "model": "",
    "shift": "",
    "date_from": "2026-02-01",
    "date_to": "2026-02-28",
    "period": "this_month",
    "keyword": ""
  },
  "reasoning": "이번 달 불량 현황을 묻고 있으므로 defect_query"
}
```

---

## Step 2: InfoAgent (정보조회, 첫 호출)

### 🔷 FM 입력 (→ Gemini gemini-2.0-flash, 첫 호출)
- **System**: INFO_SYSTEM_PROMPT (도구 8개 + 체이닝 규칙)
- **Human**:
```
사용자 질문: 이번 달 불량 현황 알려줘
의도: defect_query
상세: {"line": "", "model": "", "shift": "", "date_from": "2026-02-01", "date_to": "2026-02-28", "period": "this_month", "keyword": ""}

위 의도에 맞는 도구를 호출하여 정보를 조회하세요.
```

### 🔶 FM 출력 (← Gemini) → Tool 호출 요청
- `get_defect_stats({"date_from": "2026-02-01", "date_to": "2026-02-28"})`

> **포인트**: FM이 `defect_query` 의도 → `get_defect_stats` 도구 선택 가이드를 정확히 따름.

---

## Step 2.5: ToolNode (SQL 실행)

### Tool 결과 (3가지 섹션)
```json
{
  "by_type": [
    {"defect_type": "paint", "total_count": 312, "affected_days": 28},
    {"defect_type": "assembly", "total_count": 287, "affected_days": 26},
    {"defect_type": "welding", "total_count": 198, "affected_days": 24},
    {"defect_type": "electric", "total_count": 145, "affected_days": 20}
  ],
  "by_line": [
    {"line_id": "LINE-2", "total_defects": 398, "total_produced": 6480, "defect_rate": 6.14},
    {"line_id": "LINE-1", "total_defects": 325, "total_produced": 10080, "defect_rate": 3.22},
    {"line_id": "LINE-3", "total_defects": 219, "total_produced": 5040, "defect_rate": 4.35}
  ],
  "recent_defects": [
    {"production_date": "2026-02-28", "line_id": "LINE-2", "model_id": "TUCSON", "defect_type": "paint", "defect_count": 5, "description": "도장 얼룩 발생"},
    ...
  ]
}
```

---

## Step 2 재진입: InfoAgent (Tool 결과 수신)

### 🔶 FM 출력 (← Gemini) → 텍스트 응답
```
## 2026년 2월 불량 현황

### 유형별 불량 집계
| 유형 | 건수 | 발생 일수 |
|------|------|----------|
| 도장(paint) | 312건 | 28일 |
| 조립(assembly) | 287건 | 26일 |
| 용접(welding) | 198건 | 24일 |
| 전장(electric) | 145건 | 20일 |

### 라인별 불량률
| 라인 | 불량 건수 | 생산량 | 불량률 |
|------|----------|--------|--------|
| LINE-2 (SUV) | 398건 | 6,480대 | ⚠️ 6.14% |
| LINE-3 (EV) | 219건 | 5,040대 | ⚠️ 4.35% |
| LINE-1 (세단) | 325건 | 10,080대 | 3.22% |

⚠️ LINE-2의 불량률(6.14%)이 기준(2%) 이상입니다. 도장 불량이 전체의 33%를 차지하고 있어 점검이 필요합니다.
```

> **포인트**: FM이 3개 섹션의 데이터를 종합하여:
> 1. 유형별 불량 순위 테이블
> 2. 라인별 불량률 비교 (2% 이상 ⚠️ 표시 — 응답 규칙 적용)
> 3. 핵심 인사이트 (LINE-2 + 도장 불량 33%) 자동 도출

---

## FM 호출 요약

| 단계 | FM 역할 | 입력 | 출력 |
|------|---------|------|------|
| IntentAgent | 의도 분류 | System + Human("이번 달 불량 현황 알려줘") | JSON: `defect_query` |
| InfoAgent 1차 | Tool 선택 | System + Human(질문+의도+상세) | tool_call: `get_defect_stats` |
| InfoAgent 재진입 | 응답 생성 | System + Messages(AI+Tool결과) | 텍스트: 유형별+라인별 종합 |

**총 FM 호출: 3회** (IntentAgent 1 + InfoAgent 2)

---

## 학습 포인트

1. **복합 결과 처리**: 하나의 Tool이 3개 섹션(유형별, 라인별, 최근 상세)을 반환. FM이 모두 종합하여 구조화된 응답 생성.
2. **응답 규칙 적용**: "불량률 2% 이상: 경고 표시" 규칙에 따라 LINE-2에 ⚠️ 마커 추가.
3. **인사이트 자동 도출**: FM이 단순 데이터 나열이 아닌 "도장 불량이 33%"라는 분석적 코멘트를 추가.
4. **마크다운 표**: 응답 규칙 "표 형식 사용 권장"에 따라 깔끔한 테이블 생성.
