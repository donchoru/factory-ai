# Dify Chatflow 설정 가이드

Dify에서 Factory AI Chatflow를 만드는 방법을 설명합니다.
Stage 2(2분류)와 Stage 3(3분류) 두 가지 구성을 다룹니다.

---

## 사전 준비

1. **Dify 실행 중** (Docker 또는 클라우드)
2. **MCP 서버**: `python mcp_server.py` (:8501)
3. **factory.db 생성**: `python -m db.seed` (최초 1회)
4. **LangGraph 서버** (Stage 3만): `python server.py` (:8500)

---

## Step 1: MCP 서버 연결 (공통)

1. Dify 대시보드 → **Tools** → **MCP**
2. **Add MCP Server** 클릭
3. 설정:
   - **Name**: `Factory AI`
   - **URL**: `http://host.docker.internal:8501/mcp`
     - Dify가 Docker 안이면 `host.docker.internal`
     - Dify가 로컬이면 `localhost`
4. **Save** → 8개 도구 자동 인식:

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

## Stage 2: 2분류 Chatflow

> Dify가 **일반 대화 vs 데이터 조회**를 분류. Agent 노드가 MCP 도구 다회 호출.
> LangGraph 불필요.

### Chatflow

```
[시작] → [질문 분류기] ─┬─ 일반 대화  → [LLM 노드] ──────────────→ [끝]
                        └─ 데이터 조회 → [Agent 노드 + MCP 8개 도구] → [끝]
```

### 질문 분류기 설정

**모델**: Gemini 2.0 Flash (또는 아무 LLM)

| 클래스 | 설명 | 예시 |
|--------|------|------|
| `일반 대화` | 공장과 무관한 질문 | "안녕", "MCP가 뭐야?" |
| `데이터 조회` | 생산 데이터 관련 모든 질문 | "생산 현황", "왜 높아?", "개선 방안" |

**분류 힌트**:
```
분류 기준:
- 일반 대화: 공장 생산과 무관한 질문. 인사, 잡담, 시스템 설명 요청 등.
- 데이터 조회: 생산/불량/정지/달성률 등 공장 데이터와 관련된 모든 질문.
  "~현황", "~보여줘", "~몇 대?", "왜?", "원인", "개선" 등 포함.
```

### 일반 대화 → LLM 노드

| 설정 | 값 |
|------|-----|
| 모델 | Gemini 2.0 Flash |
| 입력 | `{{#sys.query#}}` |

**시스템 프롬프트**:
```
당신은 자동차 공장 생산 관리 어시스턴트입니다.
공장과 무관한 질문에는 간단히 답하세요.
생산 관련 질문을 할 수 있다고 안내하세요.
```

### 데이터 조회 → Agent 노드

| 설정 | 값 |
|------|-----|
| 모델 | Gemini 2.0 Flash |
| 도구 | MCP Factory AI 8개 전부 |
| 입력 | `{{#sys.query#}}` |

**시스템 프롬프트**:
```
사용자의 질문에 맞는 도구를 호출하여 공장 생산 데이터를 조회하세요.
필요하면 여러 도구를 순차적으로 호출하여 종합 분석하세요.
결과는 한국어로 표 형식으로 정리하세요.

한국어 → ID 매핑:
- 1라인 → LINE-1, 2라인 → LINE-2, 3라인 → LINE-3
- 소나타 → SONATA, 투싼 → TUCSON, GV70 → GV70, 아이오닉6 → IONIQ6
- 주간 → DAY, 야간 → NIGHT, 심야 → MIDNIGHT
- 오늘 → today, 이번 주 → this_week, 이번 달 → this_month
```

---

## Stage 3: 3분류 Chatflow

> Dify가 **3가지로 분류**. 간단한 건 MCP, 복잡한 건 LangGraph.
> LangGraph 서버(:8500)가 추가로 필요.

### Step 2 (추가): Custom Tool 등록

1. Dify → **Tools** → **Custom** → **Create Custom Tool**
2. `dify/openapi.yaml` 내용 붙여넣기
3. Server URL: `http://host.docker.internal:8500`
4. **Test Connection** → `/health` 확인

### Chatflow

```
[시작] → [질문 분류기] ─┬─ 일반 대화   → [LLM 노드] ──────────────→ [끝]
                        ├─ 간단한 조회 → [Agent 노드 + MCP 도구] ──→ [끝]
                        └─ 복잡한 분석 → [HTTP Request :8500] ────→ [끝]
```

### 질문 분류기 설정

| 클래스 | 설명 | 예시 |
|--------|------|------|
| `일반 대화` | 공장과 무관한 질문 | "안녕", "MCP가 뭐야?" |
| `간단한 조회` | 도구 1개로 답할 수 있는 질문 | "오늘 생산 현황", "라인 상태" |
| `복잡한 분석` | 여러 데이터 조합 필요한 심층 질문 | "왜 높아?", "개선 방안" |

**분류 힌트**:
```
분류 기준:
- 일반 대화: 공장 생산과 무관한 질문. 인사, 잡담, 시스템 설명 요청 등.
- 간단한 조회: "~현황", "~보여줘", "~몇 대?", "~비교" 등 단순 데이터 조회.
  도구 1개로 답할 수 있는 질문.
- 복잡한 분석: "왜?", "원인", "개선", "추천", "비교 분석해서 ~" 등 심층 분석.
  여러 데이터를 조합하거나 인사이트 도출이 필요한 질문.
```

### 일반 대화 → LLM 노드 (2분류와 동일)

### 간단한 조회 → Agent 노드 (2분류의 "데이터 조회"와 동일)

**시스템 프롬프트**:
```
사용자의 질문에 맞는 도구를 호출하여 공장 생산 데이터를 조회하세요.
결과는 한국어로 표 형식으로 정리하세요.

한국어 → ID 매핑:
- 1라인 → LINE-1, 2라인 → LINE-2, 3라인 → LINE-3
- 소나타 → SONATA, 투싼 → TUCSON, GV70 → GV70, 아이오닉6 → IONIQ6
- 주간 → DAY, 야간 → NIGHT, 심야 → MIDNIGHT
- 오늘 → today, 이번 주 → this_week, 이번 달 → this_month
```

### 복잡한 분석 → HTTP Request 노드

| 설정 | 값 |
|------|-----|
| Method | `POST` |
| URL | `http://host.docker.internal:8500/chat` |
| Headers | `Content-Type: application/json` |

**Body**:
```json
{
  "message": "{{#sys.query#}}",
  "session_id": "{{#sys.conversation_id#}}"
}
```

**출력**: HTTP Response의 `response` 필드를 End 노드에 연결

> 복잡한 분석은 LangGraph가 **도구를 2~3회 연쇄 호출**하며 심층 추론합니다.

---

## 테스트

| 질문 | 2분류 경로 | 3분류 경로 |
|------|-----------|-----------|
| 안녕하세요 | 일반 대화 → LLM | 일반 대화 → LLM |
| MCP가 뭐야? | 일반 대화 → LLM | 일반 대화 → LLM |
| 오늘 생산 현황 | 데이터 조회 → Agent+MCP | 간단한 조회 → Agent+MCP |
| 라인 상태 보여줘 | 데이터 조회 → Agent+MCP | 간단한 조회 → Agent+MCP |
| 교대별 비교 | 데이터 조회 → Agent+MCP | 간단한 조회 → Agent+MCP |
| 불량률이 왜 높아? | 데이터 조회 → Agent+MCP | **복잡한 분석 → LangGraph** |
| 개선 방안 추천 | 데이터 조회 → Agent+MCP | **복잡한 분석 → LangGraph** |

---

## API 키 발급 (Open WebUI 연동용)

1. Chatflow 상단 **Publish**
2. 좌측 **API Access** → API Key 생성
3. `app-xxxxxxxxxxxx` 형태의 키를 복사
4. Open WebUI `docker-compose.yml`의 `DIFY_API_KEY`에 설정

---

## 2분류 vs 3분류

| | 2분류 (Stage 2) | 3분류 (Stage 3) |
|---|---|---|
| 클래스 | 일반 / 데이터 | 일반 / 간단 / 복잡 |
| 복잡한 질문 | Agent가 다회 호출 (한계) | LangGraph 멀티스텝 (정확) |
| 추가 서버 | 불필요 | LangGraph :8500 |
| 장점 | 설정 간단 | 복잡한 분석 품질 |
