# Factory AI

> 자동차 공장 생산 데이터를 자연어로 질의하는 AI 시스템.
> LangGraph 멀티에이전트가 의도를 분석하고, 8개 도구를 연쇄 호출하여 답변합니다.

## 아키텍처

```
User → Open WebUI (:3006) → Pipeline (:9099) → LangGraph (:8500) SSE 스트리밍
                                                    │
                                      IntentAgent → InfoAgent ↔ ToolNode → ResponseAgent
                                                                    │
                                                              factory.db (SQLite)
```

**흐름:**
1. 사용자가 Open WebUI에서 질문
2. Pipeline이 LangGraph `/chat/stream`에 SSE 요청
3. IntentAgent가 6종 의도 분류 (Gemini)
4. InfoAgent가 적절한 도구 호출 (최대 3라운드 연쇄)
5. ResponseAgent가 최종 답변 생성
6. 4글자씩 SSE 스트리밍으로 응답

## 빠른 시작

```bash
# 1. 환경 설정
git clone https://github.com/donchoru/factory-ai.git
cd factory-ai
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. 환경변수
cp .env.example .env
# .env에 GEMINI_API_KEY 입력

# 3. DB 생성 (최초 1회)
python -m db.seed

# 4. 서버 시작
python mcp_server.py    # MCP 서버 (:8501)
python server.py        # LangGraph 서버 (:8500)

# 5. 테스트
python main.py          # CLI 대화
curl localhost:8500/health

# 6. Open WebUI (Docker)
cd open-webui && docker compose up -d    # :3006
```

## 프로젝트 구조

```
server.py                  # FastAPI 서버 (:8500) — /chat, /chat/stream, /health
mcp_server.py              # MCP 서버 (:8501) — 8개 도구 노출 (Streamable HTTP)
main.py                    # CLI 대화 테스트
config.py                  # 환경변수 + 기본값

agents/
  state.py                 # AgentState (TypedDict) + 디버그 덤프
  prompts.py               # 시스템 프롬프트 — 의도분류 / 정보조회
  intent_agent.py           # 6종 의도 분류 (Gemini, temperature=0)
  info_agent.py             # 도구 호출 + 최종 응답 생성
  message_trimmer.py        # 3계층 토큰 관리 (개별/윈도우/총량)

graph/
  workflow.py              # StateGraph + 조건부 라우팅

tools/
  factory_tools.py         # @tool 8개 (LangGraph용)

db/
  connection.py            # 브릿지 패턴 (SQLite/Oracle 자동 전환)
  schema.sql               # 6테이블 DDL
  seed.py                  # 가상 데이터 생성 (2026년 2월)
  backends/                # SQLite + Oracle 백엔드

open-webui/
  docker-compose.yml       # Open WebUI (:3006) + Pipeline (:9099)
  pipelines/
    factory_agent.py       # Pipeline — LangGraph SSE 직접 연동

dify/
  openapi.yaml             # LangGraph Custom Tool 스펙 (Dify용)
  README.md                # Dify Chatflow 설정 가이드
```

## LangGraph 그래프

```
[IntentAgent] → route_by_intent
    ├─ general_chat → [ResponseAgent] → END
    └─ 데이터 관련  → [InfoAgent] → should_use_tools
                         ├─ tool_calls → [ToolNode] → InfoAgent (재진입, max 3회)
                         └─ 응답 완성  → [ResponseAgent] → END
```

### 의도 6종

| 의도 | 설명 | 예시 |
|------|------|------|
| `production_query` | 생산 실적/수량 | "오늘 생산 현황", "소나타 몇 대?" |
| `defect_query` | 불량 통계/유형 | "불량 현황", "도장 불량 추이" |
| `line_status` | 라인 현황/가동 | "라인 상태", "어디가 제일 잘 돌아가?" |
| `downtime_query` | 설비 정지 | "정지 이력", "왜 자주 서?" |
| `trend_analysis` | 생산 추이/트렌드 | "이번 달 추이", "달성률 변화" |
| `general_chat` | 일반 대화 | "안녕", "MCP가 뭐야?" |

### 도구 8개

| 도구 | 설명 |
|------|------|
| `get_daily_production` | 일별 생산 실적 (라인/모델/날짜/교대 필터) |
| `get_production_summary` | 기간별 요약 (today / this_week / this_month) |
| `get_defect_stats` | 불량 통계 (유형별 집계 + 라인별 불량률) |
| `get_line_status` | 라인 현황 + 최근 달성률 + 가동 상태 |
| `get_downtime_history` | 설비 정지 이력 (사유별 분류 + 상세) |
| `get_model_comparison` | 차종별 비교 (달성률, 불량률, 일평균) |
| `get_shift_analysis` | 교대별 분석 (DAY / NIGHT / MIDNIGHT) |
| `get_production_trend` | 생산 추이 (일별 그래프용 데이터) |

## API

### POST /chat/stream — SSE 스트리밍 (Pipeline용)

```bash
curl -N -X POST localhost:8500/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "오늘 생산 현황", "session_id": "test"}'
```

응답 (SSE):
```
data: {"event": "message", "answer": "## 생"}
data: {"event": "message", "answer": "산 현황"}
...
data: {"event": "done", "intent": "production_query", "elapsed": "3.52s"}
```

### POST /chat — JSON 응답 (Dify / 직접 호출용)

```bash
curl -X POST localhost:8500/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "오늘 생산 현황", "session_id": "test"}'
```

응답:
```json
{
  "response": "## 생산 현황\n| 라인 | 계획 | 실적 | 달성률 |\n...",
  "intent": "production_query",
  "session_id": "test",
  "trace": ["## Step 1: IntentAgent ...", "## Step 2: InfoAgent ..."]
}
```

### GET /health

```bash
curl localhost:8500/health
```

### POST /reset — 세션 초기화

```bash
curl -X POST "localhost:8500/reset?session_id=test"
```

## DB 구조

6개 테이블, SQLite 기본 (Oracle 전환 가능):

| 테이블 | 행수 | 설명 |
|--------|------|------|
| `production_lines` | 3 | 1라인(세단), 2라인(SUV), 3라인(EV) |
| `models` | 4 | SONATA, TUCSON, GV70, IONIQ6 |
| `shifts` | 3 | DAY, NIGHT, MIDNIGHT |
| `daily_production` | ~300 | 일별 생산 실적 (2월 한달) |
| `defects` | ~287 | 불량 상세 (유형: 도장/조립/용접/전장) |
| `downtime` | ~17 | 설비 정지 (정기 점검 + 랜덤 고장) |

Oracle 전환: `.env`에 `DB_TYPE=oracle` + Oracle 접속 정보 설정.

## 컴포넌트 & 포트

| 컴포넌트 | 포트 | 설명 |
|----------|------|------|
| LangGraph Server | 8500 | 멀티에이전트 — `/chat`, `/chat/stream` |
| MCP Server | 8501 | 8개 SQL 도구 — Streamable HTTP (`/mcp`) |
| Open WebUI | 3006 | 채팅 UI |
| Pipeline | 9099 | Open WebUI ↔ LangGraph SSE 프록시 |

## 기술 스택

- **LLM**: Gemini 2.0 Flash (`langchain-google-genai`)
- **Agent**: LangGraph `StateGraph` + 조건부 라우팅
- **MCP**: FastMCP (Streamable HTTP)
- **API**: FastAPI + Uvicorn
- **DB**: SQLite (기본) / Oracle (선택)
- **UI**: Open WebUI + Pipelines (Docker)

## Dify 연동 (선택)

현재는 **Pipeline → LangGraph 직접 연동**이 기본입니다.
Dify를 사용하려면 `dify/README.md`를 참조하세요.

- Dify 2분류: 일반 대화 vs 데이터 조회 (Agent+MCP)
- Dify 3분류: 일반 / 간단한 조회(Agent+MCP) / 복잡한 분석(LangGraph)

## 한국어 → ID 매핑

| 구분 | 한국어 | ID |
|------|--------|-----|
| 라인 | 1라인, 세단라인 | LINE-1 |
| | 2라인, SUV라인 | LINE-2 |
| | 3라인, EV라인 | LINE-3 |
| 차종 | 소나타 | SONATA |
| | 투싼 | TUCSON |
| | 제네시스, GV70 | GV70 |
| | 아이오닉6 | IONIQ6 |
| 교대 | 주간 | DAY |
| | 야간 | NIGHT |
| | 심야 | MIDNIGHT |
| 기간 | 오늘 | today |
| | 이번 주 | this_week |
| | 이번 달 | this_month |
