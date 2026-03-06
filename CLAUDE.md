# Factory AI

자동차 공장 생산 데이터 자연어 질의 — LangGraph 멀티에이전트 + SSE 스트리밍.

## 아키텍처
```
User → Open WebUI (:3006) → Pipeline (:9099) → LangGraph (:8500) SSE
                                                  IntentAgent → InfoAgent ↔ ToolNode → ResponseAgent
                                                                                │
                                                                          factory.db
```

## 기술 스택
- Python 3.13 / `.venv/`
- LangGraph (StateGraph) + Gemini 2.0 Flash
- FastMCP (Streamable HTTP, :8501)
- FastAPI (:8500) — `/chat`, `/chat/stream`
- SQLite (factory.db) / Oracle 듀얼 지원
- Docker: Open WebUI (:3006) + Pipelines (:9099)

## 구조
```
server.py                  # FastAPI (:8500) — /chat, /chat/stream, /health
mcp_server.py              # MCP (:8501) — 8개 도구 (Streamable HTTP)
main.py                    # CLI 대화 테스트
config.py                  # 환경변수 + 기본값
agents/
  state.py                 # AgentState TypedDict + dump
  prompts.py               # 시스템 프롬프트 2종
  intent_agent.py          # 6종 의도 분류
  info_agent.py            # InfoAgent(도구호출) + ResponseAgent(응답생성)
  message_trimmer.py       # 3계층 토큰 관리
graph/
  workflow.py              # StateGraph + 조건부 라우팅
tools/
  factory_tools.py         # @tool 8개 (LangGraph용)
db/
  connection.py            # 브릿지 패턴 (SQLite/Oracle 자동 전환)
  schema.sql               # 6테이블 DDL
  seed.py                  # 가상 데이터 생성
  backends/                # SQLite + Oracle 백엔드
dify/
  openapi.yaml             # LangGraph Custom Tool 스펙 (Dify용)
  README.md                # Dify Chatflow 가이드
open-webui/
  docker-compose.yml       # Open WebUI + Pipelines
  pipelines/factory_agent.py  # LangGraph SSE 직접 연동
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
production_lines(3), models(4), shifts(3), daily_production(~300), defects(~287), downtime(~17)

## 실행
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m db.seed              # DB 생성 (최초 1회)
python mcp_server.py           # MCP 서버 (:8501)
python server.py               # LangGraph 서버 (:8500)
python main.py                 # CLI 테스트
cd open-webui && docker compose up -d  # Open WebUI (:3006)
```

## API
```bash
# SSE 스트리밍
curl -N -X POST localhost:8500/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "오늘 생산 현황", "session_id": "test"}'

# JSON 응답
curl -X POST localhost:8500/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "오늘 생산 현황", "session_id": "test"}'

# 헬스체크
curl localhost:8500/health
```

## Dify 연동 (선택)
현재는 Pipeline → LangGraph 직접 연동 (SSE 스트리밍).
Dify 사용 시 `dify/README.md` 참조.
