# Dify Chatflow 설정 가이드

Dify에서 Factory AI Chatflow를 만드는 방법을 설명합니다.

**핵심**: 질문을 3가지로 분류하여 각각 다른 방식으로 처리합니다.

```
질문 분류기 (3분류)
    ├─ 일반 대화    → Dify LLM 직접 응답        "안녕하세요", "MCP가 뭐야?"
    ├─ 간단한 조회  → MCP 도구 호출 (:8501)     "오늘 생산 현황", "라인 상태"
    └─ 복잡한 분석  → LangGraph (:8500)         "불량률이 왜 높아?", "개선 방안"
```

---

## 사전 준비

1. **Dify 실행 중** (Docker 또는 클라우드)
2. **LangGraph 서버**: `python server.py` (:8500)
3. **MCP 서버**: `python mcp_server.py` (:8501)
4. **factory.db 생성**: `python -m db.seed` (최초 1회)

---

## Step 1: MCP 서버 연결

Dify에서 MCP 도구를 사용할 수 있도록 등록합니다.

1. Dify 대시보드 → **Tools** → **MCP**
2. **Add MCP Server** 클릭
3. 설정:
   - **Name**: `Factory AI`
   - **URL**: `http://host.docker.internal:8501/mcp`
     - Dify가 Docker 안이면 `host.docker.internal`
     - Dify가 로컬이면 `localhost`
4. **Save** → 8개 도구가 자동 인식됨:

```
get_daily_production      일별 생산 실적
get_production_summary    기간별 생산 요약
get_defect_stats          불량 통계
get_line_status           라인 현황
get_downtime_history      설비 정지 이력
get_model_comparison      차종별 비교
get_shift_analysis        교대별 분석
get_production_trend      생산 추이
```

---

## Step 2: Custom Tool 등록 (LangGraph용)

복잡한 분석은 LangGraph 서버에 맡깁니다.

1. Dify 대시보드 → **Tools** → **Custom** → **Create Custom Tool**
2. `openapi.yaml` 내용 붙여넣기
3. Server URL: `http://host.docker.internal:8500`
4. **Test Connection** → `/health` 확인

---

## Step 3: Chatflow 만들기

### 완성된 Chatflow

```
[시작] → [질문 분류기] ─┬─ 일반 대화   → [LLM 노드] ──────────────→ [끝]
                        ├─ 간단한 조회 → [Agent 노드 + MCP 도구] ──→ [끝]
                        └─ 복잡한 분석 → [HTTP Request :8500] ────→ [끝]
```

### 3-1. Chatflow 생성

Dify 대시보드 → **Create App** → **Chatflow** → 이름: `Factory AI`

### 3-2. 질문 분류기 (Question Classifier)

**모델**: Gemini 2.0 Flash (또는 아무 LLM)

**클래스 3개**:

| 클래스 | 설명 | 예시 |
|--------|------|------|
| `일반 대화` | 공장과 무관한 일반 질문 | "안녕", "오늘 날씨", "MCP가 뭐야?" |
| `간단한 조회` | 데이터 1건 조회로 답할 수 있는 질문 | "오늘 생산 현황", "라인 상태", "이번 달 요약" |
| `복잡한 분석` | 여러 데이터를 조합해야 하는 심층 질문 | "불량률이 왜 높아?", "개선 방안", "상관관계 분석" |

**분류 힌트** (Instructions에 입력):
```
분류 기준:
- 일반 대화: 공장 생산과 무관한 질문. 인사, 잡담, 시스템 설명 요청 등.
- 간단한 조회: "~현황", "~보여줘", "~몇 대?", "~비교" 등 단순 데이터 조회.
  도구 1개로 답할 수 있는 질문.
- 복잡한 분석: "왜?", "원인", "개선", "추천", "비교 분석해서 ~" 등 심층 분석.
  여러 데이터를 조합하거나 인사이트 도출이 필요한 질문.
```

### 3-3. 일반 대화 경로 → LLM 노드

| 설정 | 값 |
|------|-----|
| 모델 | Gemini 2.0 Flash |
| 입력 | `{{#sys.query#}}` |

**시스템 프롬프트**:
```
당신은 자동차 공장 생산 관리 어시스턴트입니다.
공장과 무관한 질문에는 간단히 답하세요.
생산 관련 질문을 할 수 있다고 안내하세요.

가능한 질문 예시:
- "이번 달 생산 현황" — 라인별 실적/달성률
- "3라인 불량률" — 불량 통계
- "교대별 비교" — 주간/야간/심야 비교
- "불량률이 왜 높아?" — 원인 분석
```

### 3-4. 간단한 조회 경로 → Agent 노드 + MCP 도구

| 설정 | 값 |
|------|-----|
| 모델 | Gemini 2.0 Flash |
| 도구 | MCP에서 등록한 Factory AI 도구 8개 전부 선택 |
| 입력 | `{{#sys.query#}}` |

**시스템 프롬프트**:
```
사용자의 질문에 맞는 도구를 호출하여 공장 생산 데이터를 조회하세요.
결과는 한국어로 정리하여 표 형식으로 보여주세요.
수치는 쉼표로 구분하고, 달성률은 소수점 1자리까지 표시하세요.

한국어 → ID 매핑:
- 1라인/세단라인 → LINE-1, 2라인/SUV라인 → LINE-2, 3라인/EV라인 → LINE-3
- 소나타 → SONATA, 투싼 → TUCSON, GV70 → GV70, 아이오닉6 → IONIQ6
- 주간 → DAY, 야간 → NIGHT, 심야 → MIDNIGHT
- 오늘 → today, 이번 주 → this_week, 이번 달 → this_month
```

> Agent 노드를 사용하면 Dify의 LLM이 MCP 도구 중 적절한 것을 선택하여 호출합니다. LangGraph와 비슷하지만 **도구 1회 호출**로 끝나는 간단한 조회에 적합합니다.

### 3-5. 복잡한 분석 경로 → HTTP Request 노드

| 설정 | 값 |
|------|-----|
| Method | `POST` |
| URL | `http://host.docker.internal:8500/chat` |
| Headers | `Content-Type: application/json` |
| Body | 아래 참조 |

**Body**:
```json
{
  "message": "{{#sys.query#}}",
  "session_id": "{{#sys.conversation_id#}}"
}
```

**출력**: HTTP Response의 `response` 필드를 End 노드에 연결

> 복잡한 분석은 LangGraph가 **도구를 2~3회 연쇄 호출**하며 심층 추론합니다. "왜?"라는 질문에 불량 통계 조회 → 정지 이력 조회 → 상관관계 분석까지 자동으로 수행합니다.

### 3-6. 끝 (End) 노드

각 경로의 출력을 End 노드에 연결합니다:
- 일반 대화: LLM 출력
- 간단한 조회: Agent 출력
- 복잡한 분석: HTTP Response의 `response` 필드

---

## Step 4: 테스트

Chatflow 우측 상단 **Preview**로 테스트합니다.

### 일반 대화 → Dify 직접 응답

```
사용자: 안녕하세요!
AI: 안녕하세요! 공장 생산 관리 어시스턴트입니다.
    생산 현황, 불량 통계, 라인 상태 등을 질문해보세요.
```

### 간단한 조회 → MCP 도구

```
사용자: 이번 달 생산 현황
AI: [get_production_summary 호출]
    📊 2026년 2월 생산 현황
    | 라인 | 목표 | 실적 | 달성률 |
    | 1라인 | 9,600 | 8,704 | 90.7% |
    ...
```

### 복잡한 분석 → LangGraph

```
사용자: 3라인 불량률이 왜 높아?
AI: [LangGraph가 get_defect_stats + get_downtime_history 연쇄 호출]
    3라인(EV)의 불량률이 2.15%로 높은 주요 원인은...
    도장 불량이 38%로 가장 많으며, 2월 15일 모터 조립 설비 점검
    이후에도 전장 불량이 지속되고 있어 추가 점검이 필요합니다.
```

### 테스트 질문 모음

| 질문 | 경로 | 처리 |
|------|------|------|
| 안녕하세요 | 일반 대화 | Dify LLM |
| MCP가 뭐야? | 일반 대화 | Dify LLM |
| 오늘 생산 현황 | 간단한 조회 | MCP → `get_production_summary` |
| 라인 상태 보여줘 | 간단한 조회 | MCP → `get_line_status` |
| 교대별 생산량 비교 | 간단한 조회 | MCP → `get_shift_analysis` |
| 최근 생산 추이 | 간단한 조회 | MCP → `get_production_trend` |
| 불량률이 왜 높아? | 복잡한 분석 | LangGraph (멀티스텝) |
| 개선 방안 추천해줘 | 복잡한 분석 | LangGraph (멀티스텝) |
| 소나타 불량이랑 정지 상관관계 | 복잡한 분석 | LangGraph (멀티스텝) |

---

## Step 5: API 키 발급 (Open WebUI 연동용)

1. Chatflow 상단 **Publish**
2. 좌측 **API Access** → API Key 생성
3. `app-xxxxxxxxxxxx` 형태의 키를 복사
4. Open WebUI `docker-compose.yml`의 `DIFY_API_KEY`에 설정
