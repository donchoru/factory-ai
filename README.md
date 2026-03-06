# Factory AI

**자동차 공장 생산 데이터를 자연어로 질의하는 AI 시스템**

"이번 달 소나타 몇 대 만들었어?", "3라인 불량률이 왜 높아?" 같은 질문을 입력하면, AI가 데이터베이스를 조회해서 한국어로 분석 결과를 알려줍니다.

**코드는 Stage 3(최종) 기준이지만, 연결만 바꾸면 Stage 1/2/3 어디서든 동작합니다.**

---

## 3단계 아키텍처

하나의 코드베이스에서 연결 방식만 바꿔 3가지 구성으로 운영할 수 있습니다.

```
Stage 1: User → Open WebUI ──→ MCP (:8501) → DB
Stage 2: User → Open WebUI → Pipeline → Dify ─→ Agent+MCP → DB
Stage 3: User → Open WebUI → Pipeline → Dify ─┬→ Agent+MCP (간단)
                                               └→ LangGraph :8500 (복잡) → DB
```

| | Stage 1 | Stage 2 | Stage 3 |
|---|---|---|---|
| **무엇을 띄우나** | MCP 서버만 | MCP + Dify | MCP + Dify + LangGraph |
| **분류** | 없음 (LLM 직접) | Dify 2분류 | Dify 3분류 |
| **일반 대화** | LLM이 처리 | Dify LLM 전용 노드 | Dify LLM 전용 노드 |
| **데이터 조회** | MCP 1회 호출 | Agent 다회 호출 | Agent 다회 호출 |
| **복잡한 분석** | 한계 | Agent 다회 (한계) | LangGraph 멀티스텝 |
| **Gemini 키 필요** | 불필요 | 불필요 | 필요 |
| **난이도** | 쉬움 (5분) | 중간 (Dify 셋업) | 풀스택 |

> **핵심**: MCP 서버, DB, 코드는 **전혀 안 바뀝니다**. 어디에 연결하느냐만 다릅니다.

---

## Stage 1: MCP Only

> **가장 단순한 구성.** Open WebUI의 LLM이 MCP 도구를 직접 호출합니다.

```
┌─ Open WebUI (:3006) ─┐     ┌─ MCP 서버 (:8501) ─┐     ┌─ SQLite ─┐
│  LLM이 도구 직접 선택  │ ──→ │  8개 SQL 도구       │ ──→ │ factory.db│
└──────────────────────┘     └────────────────────┘     └──────────┘
```

### 실행

```bash
git clone https://github.com/donchoru/factory-ai.git
cd factory-ai
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m db.seed          # DB 생성 (최초 1회)
python mcp_server.py       # MCP 서버 (:8501)
```

```bash
cd open-webui && docker compose up -d   # Open WebUI (:3006)
```

### Open WebUI 설정

Admin → Settings → Tools → **MCP Servers** → Add:
- URL: `http://host.docker.internal:8501/mcp`
- 8개 도구 자동 인식

### 사용

```
사용자: 이번 달 생산 현황
AI: [get_production_summary 호출]
    📊 2026년 2월 생산 현황
    | 라인 | 목표 | 실적 | 달성률 |
    | 1라인 | 9,600 | 8,704 | 90.7% |
    ...
```

### 장점
- 설정 5분 — Dify 없이 바로 사용
- 외부 서비스 의존 없음
- Gemini API 키 불필요 (Open WebUI에 연결된 아무 LLM 사용)

### 한계
- LLM이 도구 선택을 잘못할 수 있음 (분류기 없음)
- 도구 1회 호출만 → "불량률이 왜 높아?" 같은 복합 질문 대응 어려움
- "안녕하세요"에도 도구 호출을 시도

---

## Stage 2: Dify 2분류 추가

> Stage 1에 **Dify를 추가**하여 일반 대화를 필터링하고, Agent 노드가 도구를 다회 호출합니다.

```
┌─ Open WebUI ─┐     ┌─ Dify (2분류) ────────────────────────┐
│   채팅 UI     │ ──→ │  ├─ 일반 대화  → LLM 직접 응답         │
└──────────────┘     │  └─ 데이터 조회 → Agent + MCP 다회 호출 │
                     └───────────────────┬────────────────────┘
                                         │
                              ┌─ MCP (:8501) ─┐     ┌─ SQLite ─┐
                              │  8개 SQL 도구   │ ──→ │ factory.db│
                              └────────────────┘     └──────────┘
```

### Stage 1 대비 변경점

| 추가 | 역할 |
|------|------|
| Dify Chatflow | 2분류 (일반 대화 / 데이터 조회) |
| `open-webui/pipelines/factory_agent.py` | Dify API 프록시 Pipeline |
| docker-compose에 `pipelines` 서비스 | Pipeline 컨테이너 추가 |

### Stage 1 대비 개선점

1. **질문 분류** — "안녕하세요" → Dify LLM 직접 응답 (도구 호출 안 함)
   - Stage 1에선 "안녕"에도 도구를 호출하려 했음

2. **Agent 다회 호출** — Dify Agent가 MCP 도구를 여러 번 호출 가능
   - "불량률이랑 정지 이력 같이 보여줘" → `get_defect_stats` + `get_downtime_history`
   - Stage 1에선 LLM이 1회만 호출하고 끝

3. **일반 대화 품질** — 전용 LLM 노드 + 시스템 프롬프트
   - "MCP가 뭐야?" → 친절한 설명 + 생산 관련 질문 유도
   - Stage 1에선 도구 호출 실패 후 어색한 응답

### 실행

```bash
# MCP 서버는 Stage 1과 동일
python mcp_server.py       # :8501

# Open WebUI + Pipeline
cd open-webui && docker compose up -d   # :3006

# Dify 설정 (별도)
# → dify/README.md의 "2분류" 섹션 참조
```

### Dify 설정

MCP 등록: Dify → Tools → MCP → `http://host.docker.internal:8501/mcp`

```
[시작] → [질문 분류기] ─┬─ 일반 대화  → [LLM 노드] ──────────────→ [끝]
                        └─ 데이터 조회 → [Agent 노드 + MCP 8개 도구] → [끝]
```

> Open WebUI에서는 MCP 직접 연결을 **제거** — Dify가 대신 처리

### 한계
- "왜?"류 심층 분석은 Dify Agent 한계 — 도구 체이닝 전략이 LLM 즉흥에 의존
- 의도 분석 없이 도구를 선택 → 파라미터 매핑 불안정 ("3라인" → "3"으로 보내는 실수)
- 멀티턴 대화에서 대명사 해석 부족

---

## Stage 3: LangGraph 멀티에이전트 추가

> Stage 2에 **LangGraph를 추가**하여 복잡한 분석을 멀티스텝으로 처리합니다. 최종 구성.

```
┌─ Open WebUI ─┐     ┌─ Dify (3분류) ──────────────────────────────────┐
│   채팅 UI     │ ──→ │  ├─ 일반 대화   → LLM 직접 응답                  │
└──────────────┘     │  ├─ 간단한 조회  → Agent + MCP (:8501)           │
                     │  └─ 복잡한 분석  → HTTP → LangGraph (:8500)      │
                     └──────────┬─────────────────────┬─────────────────┘
                                │                     │
                     ┌─ MCP (:8501) ─┐   ┌─ LangGraph (:8500) ───────────┐
                     │  8개 SQL 도구   │   │  IntentAgent → InfoAgent      │
                     └───────┬────────┘   │      ↕ ToolNode (최대 3회)     │
                             │            │  ResponseAgent                 │
                             ▼            └──────────────┬────────────────┘
                     ┌─ SQLite (factory.db) ─┐           │
                     │  생산·불량·정지 데이터   │ ◄─────────┘
                     └───────────────────────┘
```

### Stage 2 대비 변경점

| 추가 | 역할 |
|------|------|
| `server.py` | FastAPI :8500 (LangGraph 서버) |
| `main.py` | CLI 대화 테스트 진입점 |
| `agents/intent_agent.py` | 6종 의도 분류 (JSON 구조화) |
| `agents/info_agent.py` | 도구 선택 + 체이닝 + 응답 생성 |
| `agents/prompts.py` | 시스템 프롬프트 2종 |
| `agents/state.py` | AgentState + 상태 추적 |
| `agents/message_trimmer.py` | 3계층 토큰 관리 |
| `graph/workflow.py` | StateGraph 4노드 + 조건부 라우팅 |
| `tools/factory_tools.py` | @tool 8개 (LangGraph용) |
| `dify/openapi.yaml` | LangGraph Custom Tool 스펙 |
| `config.py` 확장 | + GEMINI_API_KEY, GEMINI_MODEL, SERVER_PORT |
| Dify Chatflow | 2분류 → **3분류** |

### Stage 2 대비 개선점

1. **3분류 = 경로 최적화** — 복잡도에 따라 처리 방식이 달라짐
   - 간단한 조회 → Dify Agent (빠름, ~2초)
   - 복잡한 분석 → LangGraph (정확, ~5-10초)
   - Stage 2에선 모든 데이터 질문이 같은 경로

2. **의도 분석 Agent** — 6종 분류 + JSON 구조화
   ```json
   {"intent": "production_query", "detail": {"model": "SONATA", "period": "this_month"}}
   ```
   - 한국어→ID 매핑이 프롬프트에 명시 — "3라인" → LINE-3 안정적
   - Stage 2에선 Dify Agent가 즉흥으로 파라미터 생성 → 실수 빈번

3. **전략적 도구 체이닝 (최대 3라운드)**
   ```
   "소나타 불량률이 높은데 왜 그래?"
   → 1차: get_defect_stats(model="SONATA")     → 불량 유형 확인
   → 2차: get_downtime_history(line="LINE-1")   → 정비/정지 상관관계
   → 3차: 결과 종합 → 원인 분석 응답 생성
   ```
   - Stage 2 Agent는 1-2회 호출 후 바로 응답 — 깊이 부족

4. **토큰 관리** — ToolMessage 3000자 제한, 히스토리 12건, 총 30000자
   - 긴 조회 결과가 컨텍스트를 잡아먹는 문제 해결
   - Stage 2 Dify는 내부 관리하지만 투명하지 않음

5. **실행 추적 (Trace)** — IntentAgent→InfoAgent→ToolNode→ResponseAgent 전 과정 기록
   - API 응답의 `trace` 필드로 디버깅 가능
   - Stage 2 Dify 내부 동작은 블랙박스

6. **멀티턴 대화** — "그 라인 정지 이력은?" → 이전 대화에서 언급된 라인 참조
   - conversation_history를 IntentAgent + InfoAgent 모두에 전달
   - Stage 2는 Dify conversation_id로 일부 지원하지만 도구 호출 맥락 유실

### 실행

```bash
# Gemini API 키 설정 (LangGraph에 필요)
echo "GEMINI_API_KEY=your-key" > .env

# 서버 3개
python mcp_server.py       # :8501 (MCP)
python server.py           # :8500 (LangGraph)
cd open-webui && docker compose up -d   # :3006 (Open WebUI + Pipeline)

# Dify 설정 (별도)
# → dify/README.md의 "3분류" 섹션 참조
```

### Dify 설정

```
[시작] → [질문 분류기] ─┬─ 일반 대화   → [LLM 노드] ──────────────→ [끝]
                        ├─ 간단한 조회 → [Agent 노드 + MCP 도구] ──→ [끝]
                        └─ 복잡한 분석 → [HTTP Request :8500] ────→ [끝]
```

- MCP: Dify → Tools → MCP → `http://host.docker.internal:8501/mcp`
- Custom Tool: Dify → Tools → Custom → `dify/openapi.yaml` (Server: `:8500`)

### CLI 테스트 (Dify 없이)

```bash
python main.py
```

```
질문> 이번 달 소나타 달성률은?
[production_query]
📊 2026년 2월 소나타 생산 현황...
```

---

## Stage 비교 상세

### 한눈에 비교

| | Stage 1 (MCP) | Stage 2 (+Dify) | Stage 3 (+LangGraph) |
|---|---|---|---|
| **분류** | 없음 | 2분류 | 3분류 |
| **일반 대화** | LLM 직접 | Dify LLM 전용 | Dify LLM 전용 |
| **간단 조회** | MCP 1회 | Agent 다회 | Agent 다회 |
| **복잡 분석** | 불가 | Agent 다회 (한계) | LangGraph 멀티스텝 |
| **의도 분석** | 없음 | 없음 | 6종 JSON 분류 |
| **도구 체이닝** | 1회 | LLM 즉흥 | 전략적 최대 3회 |
| **토큰 관리** | 없음 | Dify 내부 | 3계층 트리밍 |
| **디버깅** | 없음 | Dify 로그 | Trace 전체 기록 |
| **멀티턴** | 없음 | 부분 | 대명사 해석 포함 |
| **응답 속도** | ~1-2초 | ~2-3초 | 간단 ~2초 / 복잡 ~5-10초 |

### 같은 질문, 다른 처리

```
질문: "3라인 불량률이 왜 높아?"

Stage 1: MCP get_defect_stats(line="LINE-3") 1회 호출 → 수치만 나열
Stage 2: Dify Agent가 get_defect_stats + get_downtime_history 호출 → 나열 + 간단 코멘트
Stage 3: LangGraph IntentAgent → defect_query 분류
         → InfoAgent Round 1: get_defect_stats(line="LINE-3") → 도장 불량 42% 파악
         → InfoAgent Round 2: get_downtime_history(line="LINE-3") → 정비 이력 상관관계
         → ResponseAgent: "3라인 불량률 2.15%의 주요 원인은 도장 불량(42%)이며,
           2/15 모터 조립 설비 점검 이후에도 전장 불량이 지속되어 추가 점검 필요"
```

### 무엇을 띄우나

```bash
# Stage 1 — MCP만
python mcp_server.py                    # :8501
docker compose -f open-webui/docker-compose.yml up -d   # :3006
# → Open WebUI에서 MCP 직접 연결

# Stage 2 — + Dify
python mcp_server.py                    # :8501
docker compose -f open-webui/docker-compose.yml up -d   # :3006 + Pipeline :9099
# → Dify에 MCP 등록, Open WebUI에서 MCP 직접 연결 제거
# → Dify 2분류 Chatflow 생성

# Stage 3 — + LangGraph
python mcp_server.py                    # :8501
python server.py                        # :8500
docker compose -f open-webui/docker-compose.yml up -d   # :3006 + Pipeline :9099
# → Dify에 MCP + Custom Tool(openapi.yaml) 등록
# → Dify 3분류 Chatflow 생성
```

---

## 빠른 시작

### 환경 설정 (공통)

```bash
git clone https://github.com/donchoru/factory-ai.git
cd factory-ai

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m db.seed          # DB 생성 (최초 1회)
```

### Stage 1로 시작 (추천)

```bash
python mcp_server.py       # MCP 서버 시작 (:8501)
```

Open WebUI → Admin → Tools → MCP Servers → `http://host.docker.internal:8501/mcp`

### Stage 3까지 확장

```bash
echo "GEMINI_API_KEY=your-key" > .env
python server.py           # LangGraph 서버 (:8500)
```

Dify에서 3분류 Chatflow 생성 → `dify/README.md` 참조

---

## 가상 공장 데이터

`python -m db.seed`로 생성되는 가상 자동차 공장 (2026년 2월).

```
🏭 가상 자동차 공장
│
├── LINE-1: 1라인 (세단)
│   └── 소나타 (SONATA) — 교대당 목표 120대
│
├── LINE-2: 2라인 (SUV)
│   ├── 투싼 (TUCSON) — 교대당 목표 45대
│   └── GV70 — 교대당 목표 35대
│
└── LINE-3: 3라인 (EV)
    └── 아이오닉6 (IONIQ6) — 교대당 목표 60대

🔄 3교대: 주간(06~14시) / 야간(14~22시) / 심야(22~06시)
```

### DB 테이블 (6개)

| 테이블 | 행 수 | 설명 |
|--------|-------|------|
| `production_lines` | 3 | 생산 라인 (LINE-1/2/3) |
| `models` | 4 | 차종 (소나타/투싼/GV70/아이오닉6) |
| `shifts` | 3 | 교대 (주간/야간/심야) |
| `daily_production` | ~300 | 일별 생산 실적 |
| `defects` | ~287 | 불량 상세 (도장/조립/용접/전장) |
| `downtime` | ~17 | 설비 정지 이력 |

### 데이터 특성

- 평일 달성률 90-100%, 토요일 75-88%, 일요일 70-82%
- LINE-3(EV) 불량률 2-4% (의도적으로 높게 설정)
- 계획 정비 6건 + 비계획 정지 ~12건 (랜덤)

---

## MCP 도구 8개

MCP 서버(:8501)와 LangGraph(@tool) 모두에서 동일한 8개 도구를 제공합니다.

| # | 도구 | 설명 | 질문 예시 |
|---|------|------|----------|
| 1 | `get_daily_production` | 일별 생산 실적 | "2월 15일 1라인 실적" |
| 2 | `get_production_summary` | 기간별 생산 요약 | "이번 달 생산 현황" |
| 3 | `get_defect_stats` | 불량 통계 | "3라인 불량 현황" |
| 4 | `get_line_status` | 라인 현황 | "어떤 라인이 제일 잘 돌아가?" |
| 5 | `get_downtime_history` | 설비 정지 이력 | "설비 정지 이력 보여줘" |
| 6 | `get_model_comparison` | 차종별 비교 | "차종별 실적 비교" |
| 7 | `get_shift_analysis` | 교대별 분석 | "교대별 생산량 비교" |
| 8 | `get_production_trend` | 생산 추이 | "최근 2주 생산 추이" |

### 파라미터 매핑

| 한국어 | ID | 카테고리 |
|--------|-----|---------|
| 1라인, 세단라인 | `LINE-1` | 라인 |
| 2라인, SUV라인 | `LINE-2` | 라인 |
| 3라인, EV라인, 전기차라인 | `LINE-3` | 라인 |
| 소나타 | `SONATA` | 차종 |
| 투싼 | `TUCSON` | 차종 |
| GV70, 제네시스 | `GV70` | 차종 |
| 아이오닉6, 아이오닉 | `IONIQ6` | 차종 |
| 주간, 낮 | `DAY` | 교대 |
| 야간, 밤 | `NIGHT` | 교대 |
| 심야, 새벽 | `MIDNIGHT` | 교대 |
| 오늘 | `today` | 기간 |
| 이번 주 | `this_week` | 기간 |
| 이번 달 | `this_month` | 기간 |

---

## LangGraph 에이전트 (Stage 3)

### StateGraph 구조

```
[IntentAgent] → route_by_intent
    ├─ general_chat → [ResponseAgent] → END
    └─ other → [InfoAgent]
[InfoAgent] → should_use_tools
    ├─ has_tool_calls → [ToolNode] → InfoAgent (loop, max 3)
    └─ no_tool_calls → [ResponseAgent] → END
```

### 의도 6개

| 의도 | 설명 | 라우팅 |
|------|------|--------|
| `production_query` | 생산 실적/수량 조회 | InfoAgent |
| `defect_query` | 불량 통계/유형별 분석 | InfoAgent |
| `line_status` | 라인 현황/가동 상태 | InfoAgent |
| `downtime_query` | 설비 정지 이력 | InfoAgent |
| `trend_analysis` | 생산 추이/트렌드 | InfoAgent |
| `general_chat` | 일반 대화 | ResponseAgent 직행 |

### 도구 체이닝 예시

```
질문: "소나타 불량률이 높은데 왜 그래?"

Round 1: get_defect_stats(model="SONATA")
         → 도장 42%, 조립 31% ...

Round 2: get_downtime_history(line="LINE-1")     ← LLM이 추가 분석 결정
         → 도장 부스 필터 교체 정비 이력 ...

최종: "소나타 불량의 주요 원인은 도장 불량(42%)이며,
      LINE-1 도장 부스 정비 이후에도 지속되고 있어 추가 점검이 필요합니다."
```

### 토큰 관리 전략

| 계층 | 제한 | 역할 |
|------|------|------|
| ToolMessage 트리밍 | 개별 3,000자 | 긴 SQL 결과 잘라냄 |
| 히스토리 윈도우 | 12건 | 오래된 메시지 제거 |
| 총 컨텐츠 제한 | 30,000자 | 가장 긴 ToolMessage 반복 축소 |

---

## 프로젝트 구조

```
factory-ai/
├── mcp_server.py            # MCP 서버 (:8501) — 모든 Stage 공통
├── server.py                # LangGraph 서버 (:8500) — Stage 3
├── main.py                  # CLI 대화 테스트 — Stage 3
├── config.py                # 설정 (DB + Gemini + Server)
│
├── agents/                  # LangGraph 에이전트 — Stage 3
│   ├── state.py             #   AgentState TypedDict
│   ├── prompts.py           #   시스템 프롬프트 (의도분석/정보조회)
│   ├── intent_agent.py      #   IntentAgent — 6종 의도 분류
│   ├── info_agent.py        #   InfoAgent + ResponseAgent
│   └── message_trimmer.py   #   3계층 토큰 관리
│
├── graph/
│   └── workflow.py          # StateGraph 정의 (노드/엣지/라우팅)
│
├── tools/
│   └── factory_tools.py     # @tool 8개 (LangGraph용)
│
├── db/                      # DB 레이어 — 모든 Stage 공통
│   ├── connection.py        #   브릿지 패턴 (SQLite/Oracle 자동 전환)
│   ├── schema.sql           #   6테이블 스키마 + 마스터 데이터
│   ├── seed.py              #   가상 생산 데이터 생성기
│   └── backends/
│       ├── base.py          #   추상 클래스
│       ├── sqlite.py        #   SQLite 구현
│       └── oracle.py        #   Oracle 구현
│
├── dify/                    # Dify 연동 — Stage 2, 3
│   ├── openapi.yaml         #   LangGraph Custom Tool 스펙 (Stage 3)
│   └── README.md            #   Chatflow 설정 가이드 (2분류/3분류)
│
├── open-webui/              # Open WebUI Docker — 모든 Stage 공통
│   ├── docker-compose.yml   #   Open WebUI + Pipelines
│   └── pipelines/
│       └── factory_agent.py #   Dify API 프록시 Pipeline
│
├── docs/
│   └── MCP_GUIDE.md         # MCP 프로토콜 상세 가이드
│
├── requirements.txt
├── .env                     # GEMINI_API_KEY (Stage 3에서 필요)
└── factory.db               # SQLite DB (seed.py로 생성)
```

---

## API 레퍼런스

### LangGraph 서버 (:8500) — Stage 3

```bash
# 자연어 질의
curl -X POST localhost:8500/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "이번 달 생산 현황", "session_id": "test"}'

# 응답: {"response": "📊 ...", "intent": "production_query", "trace": [...]}

# 헬스체크
curl localhost:8500/health

# 세션 초기화
curl -X POST "localhost:8500/reset?session_id=test"
```

### MCP 서버 (:8501) — 모든 Stage

```bash
python mcp_server.py    # Streamable HTTP, :8501/mcp
```

---

## 포트 요약

| 서비스 | 포트 | Stage |
|--------|------|-------|
| MCP (FastMCP) | `8501` | 1, 2, 3 |
| Open WebUI | `3006` | 1, 2, 3 |
| Pipelines | `9099` | 2, 3 |
| LangGraph (FastAPI) | `8500` | 3 |
| Dify | 별도 | 2, 3 |

---

## 기술 스택

| 기술 | 역할 | Stage |
|------|------|-------|
| **FastMCP** | MCP 서버 (8개 도구 노출) | 1, 2, 3 |
| **SQLite** | 데이터베이스 | 1, 2, 3 |
| **Open WebUI** | 채팅 UI | 1, 2, 3 |
| **Dify** | 질문 분류 + 라우팅 | 2, 3 |
| **LangGraph** | 멀티스텝 에이전트 | 3 |
| **Gemini 2.0 Flash** | LLM (의도분석/도구선택/응답) | 3 |
| **FastAPI** | LangGraph HTTP 서버 | 3 |
| **Docker** | 컨테이너 (Open WebUI) | 1, 2, 3 |
| **Oracle** (선택) | 엔터프라이즈 DB 전환 | 1, 2, 3 |

---

## Oracle 지원

`.env`에서 DB_TYPE을 바꾸면 Oracle로 전환됩니다. SQL 플레이스홀더(`?` → `:N`)와 LIMIT 구문이 자동 변환됩니다.

```env
DB_TYPE=oracle
ORACLE_DSN=localhost:1521/XEPDB1
ORACLE_USER=factory
ORACLE_PASSWORD=factory123
```

---

## 트러블슈팅

### factory.db가 없을 때
```bash
python -m db.seed
```

### Gemini API 키 오류 (Stage 3)
```bash
cat .env    # GEMINI_API_KEY=your-key
```

### 포트 충돌
```bash
lsof -i :8500    # 또는 :8501
kill $(lsof -ti:8500)
```

### Dify에서 MCP/LangGraph 연결 실패
```bash
# Docker 안에서 호스트 접근
# ✗ http://localhost:8501
# ✓ http://host.docker.internal:8501
```

### 로그 확인
```bash
tail -f logs/server-err.log    # LangGraph
tail -f logs/mcp-err.log       # MCP
```
