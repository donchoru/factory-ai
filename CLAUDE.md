# Factory AI

자동차 공장 생산 데이터 자연어 질의 시스템.
코드는 Stage 3(최종) 기준. 연결만 바꾸면 Stage 1/2/3 모두 동작.

## 3단계 아키텍처
```
Stage 1: User → Open WebUI ──→ MCP (:8501) → DB
Stage 2: User → Open WebUI → Pipeline → Dify ─→ Agent+MCP → DB
Stage 3: User → Open WebUI → Pipeline → Dify ─┬→ Agent+MCP (간단)
                                               └→ LangGraph :8500 (복잡) → DB
```

### Stage 3 Pipeline 동작 (Dify SSE 프록시)
- `message` / `agent_message` → 토큰 실시간 스트리밍
- `node_started(http-request)` → "🔍 분석 중..." 즉시 표시
- JSON 응답 (LangGraph 경유) → `response` 필드 자동 추출
- conversation_id 자동 매핑: Open WebUI chat_id ↔ Dify conversation_id

## 기술 스택
- Python 3.13 / `.venv/`
- FastMCP (Streamable HTTP, :8501) — 모든 Stage 공통
- Dify Chatflow (질문 2분류/3분류) — Stage 2, 3
- LangGraph (StateGraph) + Gemini 2.0 Flash — Stage 3
- FastAPI (:8500) — Stage 3
- SQLite (factory.db) / Oracle 듀얼 지원
- Docker: Open WebUI (:3006) + Pipelines (:9099)

## 구조
```
mcp_server.py              # MCP 서버 (:8501) — 모든 Stage
server.py                  # LangGraph 서버 (:8500) — Stage 3
main.py                    # CLI 테스트 — Stage 3
config.py                  # DB + Gemini + Server 설정
agents/
  state.py                 # AgentState TypedDict
  prompts.py               # 시스템 프롬프트 2종
  intent_agent.py          # 6종 의도 분류
  info_agent.py            # InfoAgent + ResponseAgent
  message_trimmer.py       # 3계층 토큰 관리
graph/
  workflow.py              # StateGraph + 조건부 라우팅
tools/
  factory_tools.py         # @tool 8개 (LangGraph용)
db/
  connection.py            # 브릿지 패턴 (SQLite/Oracle 자동 전환)
  schema.sql               # 6테이블 스키마
  seed.py                  # 가상 데이터 생성
  backends/                # SQLite + Oracle 백엔드
dify/
  openapi.yaml             # LangGraph Custom Tool 스펙
  README.md                # 2분류/3분류 Chatflow 가이드
open-webui/
  docker-compose.yml       # Open WebUI + Pipelines (Dify 환경변수)
  pipelines/factory_agent.py  # Dify SSE 프록시 + 진행상태 감지
docs/
  MCP_GUIDE.md             # MCP 상세 가이드
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

## 실행 (Stage별)
```bash
# 공통
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m db.seed

# Stage 1: MCP만
python mcp_server.py

# Stage 2: + Dify
python mcp_server.py
cd open-webui && docker compose up -d
# Dify 2분류 Chatflow → dify/README.md

# Stage 3: + LangGraph
echo "GEMINI_API_KEY=your-key" > .env
python mcp_server.py
python server.py
cd open-webui && docker compose up -d
# Dify 3분류 Chatflow → dify/README.md
```

## API (Stage 3)
```bash
# JSON 응답 (Dify HTTP Request가 호출)
curl -X POST localhost:8500/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "오늘 생산 현황", "session_id": "test"}'

# SSE 스트리밍 (직접 테스트용)
curl -N -X POST localhost:8500/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "오늘 생산 현황", "session_id": "test"}'

# 헬스체크
curl localhost:8500/health
```

## 포트
| 서비스 | 포트 | Stage |
|--------|------|-------|
| MCP | 8501 | 1, 2, 3 |
| Open WebUI | 3006 | 1, 2, 3 |
| Pipelines | 9099 | 2, 3 |
| Dify | 별도 | 2, 3 |
| LangGraph | 8500 | 3 |
