# Factory AI

자동차 공장 생산 데이터 자연어 질의 시스템 — LangGraph + Gemini + SQLite.

## 기술 스택
- Python 3.13 / `.venv/`
- LangGraph (StateGraph)
- langchain-google-genai (Gemini 2.0 Flash)
- SQLite (factory.db — `python -m db.seed`로 재생성)
- FastAPI (:8500) — Dify/Open WebUI 연동

## 아키텍처
```
Open WebUI (:3006) — 채팅 UI
    ↓ Pipeline → Dify Chat API
Dify (Chatflow) — 라우팅 + 간단한 건 직접 처리
    ├─ 일반 대화 → Dify LLM 직접 응답
    └─ 공장 조회 → POST :8500/chat
LangGraph + FastAPI (:8500) — 복잡한 분석 전담
  IntentAgent → InfoAgent ↔ ToolNode → ResponseAgent
    ↓ @tool SQL queries
SQLite (factory.db — 2026년 2월 가상 생산 데이터)
```

## 구조
```
main.py                     # CLI 대화형 진입점
server.py                   # FastAPI 서버 (:8500)
mcp_server.py               # MCP 서버 (:8501, FastMCP Streamable HTTP)
config.py                   # 환경 변수, 모델 설정
agents/
  state.py                  # AgentState (conversation_history 포함)
  prompts.py                # System 프롬프트 2종
  intent_agent.py           # IntentAgent + _build_context() + FM I/O
  info_agent.py             # InfoAgent + ResponseAgent + FM I/O
  message_trimmer.py        # 3계층 토큰 관리
graph/
  workflow.py               # StateGraph + 조건부 라우팅
tools/
  factory_tools.py          # @tool 8개 + ALL_TOOLS
db/
  schema.sql                # 6테이블 스키마 + 마스터 데이터
  connection.py             # SQLite 유틸
  seed.py                   # 가상 생산 데이터 생성
dify/
  openapi.yaml              # Dify Custom Tool 스펙
  README.md                 # Dify 연동 가이드
open-webui/
  docker-compose.yml        # Open WebUI + Pipelines
  pipelines/factory_agent.py # Pipeline 클래스
```

## 의도 6개
production_query, defect_query, line_status, downtime_query, trend_analysis, general_chat

## 도구 8개
1. get_daily_production — 일별 생산 실적
2. get_production_summary — 기간별 요약
3. get_defect_stats — 불량 통계
4. get_line_status — 라인 현황
5. get_downtime_history — 정지 이력
6. get_model_comparison — 차종별 비교
7. get_shift_analysis — 교대별 분석
8. get_production_trend — 생산 추이

## DB 테이블 6개
production_lines(3), models(4), shifts(3), daily_production(~252), defects(~170), downtime(~18)

## 실행
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m db.seed          # DB 생성 (최초 1회)
python main.py             # CLI 테스트
python server.py           # FastAPI 서버 (:8500)
```

## API
```bash
# 자연어 질의
curl -X POST localhost:8500/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "오늘 생산 현황", "session_id": "test"}'

# 헬스체크
curl localhost:8500/health

# 세션 초기화
curl -X POST "localhost:8500/reset?session_id=test"
```

## MCP 서버 (:8501)
FastMCP로 8개 SQL 도구를 MCP 프로토콜(Streamable HTTP)로 노출.
Open WebUI에서 LLM이 직접 도구를 선택/호출할 수 있다.

```bash
python mcp_server.py        # MCP 서버 (:8501)
```

- **Transport**: Streamable HTTP (`/mcp`)
- **launchd**: `com.dongcheol.factory-mcp` (KeepAlive)
- **Open WebUI 설정**: Admin → Settings → Tools → MCP Servers
  - URL: `http://host.docker.internal:8501/mcp`

## 연동
- **Dify**: `dify/openapi.yaml` → Custom Tool 등록 → Chatflow HTTP Request
- **Open WebUI Pipeline**: `cd open-webui && docker compose up -d` → localhost:3006
- **Open WebUI MCP**: Admin → Tools → MCP Servers → `http://host.docker.internal:8501/mcp`
