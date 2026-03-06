# 예시 5: 일반 대화 — 최단 경로 패턴 (Tool 미사용)

> **학습 목표**: `general_chat` 의도는 InfoAgent를 거치지 않고 ResponseAgent로 직행하는 **최단 경로**.
> FM이 2번만 호출되며, Tool이 전혀 사용되지 않는 패턴을 추적한다.

---

## 입력

```
안녕하세요
```

---

## Step 1: IntentAgent (의도분석)

### 🔷 FM 입력 (→ Gemini gemini-2.0-flash)
- **System**: INTENT_SYSTEM_PROMPT (의도 6개 + JSON형식 + 매핑규칙)
- **Human**:
```
안녕하세요
```

### 🔶 FM 출력 (← Gemini)
```json
{
  "intent": "general_chat",
  "detail": {
    "line": "",
    "model": "",
    "shift": "",
    "date_from": "",
    "date_to": "",
    "period": "",
    "keyword": ""
  },
  "reasoning": "공장 생산과 무관한 일반적인 인사말입니다."
}
```

> **포인트**: "안녕하세요"에 생산, 불량, 라인 관련 키워드가 없으므로 `general_chat`으로 분류.
> detail의 모든 필드가 빈 값.

---

## 라우팅: general_chat → ResponseAgent 직행

```
route_by_intent("general_chat") → "respond_node"
```

> **핵심**: `general_chat`은 InfoAgent(Tool 루프)를 **완전히 건너뛰고** ResponseAgent로 직행.
> 다른 의도는 `info_node` → `tool_node` → `info_node` → `respond_node` 경로를 탐.

---

## Step 2: ResponseAgent (응답생성, 일반대화)

### 🔷 FM 입력 (→ Gemini gemini-2.0-flash, 일반대화)
- **System**: "당신은 친절한 자동차 공장 생산 관리 어시스턴트입니다. 공장과 무관한 질문에는 간단히 답하고, 생산 관련 질문을 유도하세요." (76자)
- **Human**: "안녕하세요"

> **주의**: 여기서 사용되는 System 프롬프트는 **INFO_SYSTEM_PROMPT가 아닌 별도의 짧은 프롬프트(76자)**.
> 일반 대화에는 Tool 선택 규칙이 필요 없으므로 경량 프롬프트 사용.

### 🔶 FM 출력 (← Gemini)
```
안녕하세요! 자동차 공장 생산 관리 어시스턴트입니다.
오늘 라인별 생산 현황이나 불량 통계 등 궁금한 점이 있으시면 말씀해주세요!
```

> **포인트**: FM이 "생산 관련 질문을 유도하세요" 지시에 따라 도메인 관련 질문을 유도하는 답변 생성.

---

## FM 호출 요약

| 단계 | FM 역할 | System 프롬프트 | 입력 | 출력 |
|------|---------|----------------|------|------|
| IntentAgent | 의도 분류 | INTENT_SYSTEM_PROMPT | "안녕하세요" | `general_chat` |
| ResponseAgent | 일반 대화 응답 | 일반대화 프롬프트 (76자) | "안녕하세요" | 인사 + 생산 유도 |

**총 FM 호출: 2회** (InfoAgent 미경유 → 최소 호출)

---

## 경로 비교

```
일반 대화 (general_chat):
  IntentAgent → ResponseAgent                    ← FM 2회

정보 조회 (그 외 5개 의도):
  IntentAgent → InfoAgent → ToolNode → InfoAgent → ResponseAgent   ← FM 3회+
```

---

## 학습 포인트

1. **최단 경로**: `general_chat`은 유일하게 InfoAgent를 건너뛰는 의도. FM 호출 2회로 응답 생성. 불필요한 Tool 호출 방지.
2. **다른 System 프롬프트 사용**: ResponseAgent의 일반대화 FM은 INFO_SYSTEM_PROMPT가 아닌 76자짜리 경량 프롬프트 사용. Tool 정보가 불필요하므로 토큰 절약.
3. **도메인 유도 전략**: "공장과 무관한 질문에는 간단히 답하고, 생산 관련 질문을 유도하세요"라는 프롬프트가 사용자를 시스템의 핵심 도메인으로 이끔.
4. **temperature 차이**: 일반대화 FM은 `temperature=0.7` (창의적), 다른 FM 호출은 `temperature=0` (결정적). 대화는 자연스럽게, 데이터 조회는 정확하게.
