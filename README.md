# Factory AI

**자동차 공장 생산 데이터를 자연어로 질의하는 AI 시스템**

"이번 달 소나타 몇 대 만들었어?", "3라인 불량률이 왜 높아?" 같은 자연어 질문을 입력하면, AI가 데이터베이스를 조회해서 한국어로 분석 결과를 알려줍니다.

---

## 한눈에 보는 구조

```
사용자 질문: "이번 달 생산 현황 알려줘"
    │
    ├─ 경로 A: LangGraph Agent (:8500) ──── Gemini가 의도 분석 → 도구 선택 → 응답 생성
    │    └─ 프론트엔드: Open WebUI Pipeline 또는 Dify Chatflow
    │
    └─ 경로 B: MCP Server (:8501) ──── Open WebUI의 LLM이 직접 도구 호출
         └─ 프론트엔드: Open WebUI (MCP 네이티브)
    │
    ▼
SQLite (factory.db) ─── 2026년 2월 가상 생산 데이터
```

---

## 목차

1. [이 프로젝트가 하는 일](#이-프로젝트가-하는-일)
2. [기술 스택 소개](#기술-스택-소개) — 각 기술이 뭔지, 왜 쓰는지
3. [전체 아키텍처](#전체-아키텍처) — 어떻게 연결되는지
4. [프로젝트 구조](#프로젝트-구조)
5. [가상 공장 데이터](#가상-공장-데이터) — 어떤 데이터로 테스트하는지
6. [빠른 시작](#빠른-시작)
7. [3가지 실행 방법](#3가지-실행-방법)
8. [프론트엔드 연동 3가지](#프론트엔드-연동-3가지)
9. [8개 조회 도구 상세](#8개-조회-도구-상세)
10. [LangGraph 에이전트 동작 원리](#langgraph-에이전트-동작-원리)
11. [MCP 서버 동작 원리](#mcp-서버-동작-원리)
12. [API 레퍼런스](#api-레퍼런스)
13. [트러블슈팅](#트러블슈팅)

---

## 이 프로젝트가 하는 일

자동차 공장의 **생산 관리 데이터**를 자연어로 질의할 수 있는 시스템입니다.

### 질문 예시

| 질문 | AI가 하는 일 |
|------|-------------|
| "오늘 생산 현황" | 라인별 목표/실적/달성률 테이블 생성 |
| "소나타 이번 달 달성률은?" | 소나타 모델의 월간 실적 집계 |
| "3라인 불량률이 왜 높아?" | 불량 유형별 분석 + 설비 정지 상관관계 |
| "교대별 생산량 비교" | 주간/야간/심야 교대 생산량 비교표 |
| "어떤 라인이 제일 잘 돌아가?" | 라인 현황 + 달성률 순위 |
| "최근 생산 추이 보여줘" | 일별 생산량/달성률 트렌드 데이터 |

### 응답 예시

```
📊 2026년 2월 생산 현황

| 라인 | 목표 | 실적 | 달성률 | 불량률 |
|------|------|------|--------|--------|
| 1라인 (세단) | 9,600 | 8,704 | 90.7% | 1.02% |
| 2라인 (SUV) | 6,400 | 5,832 | 91.1% | 1.45% |
| 3라인 (EV) | 4,800 | 4,356 | 90.8% | ⚠️ 2.15% |

⚠️ 3라인(EV)의 불량률이 2%를 초과했습니다.
주요 불량 유형: 전장(센서 오류) 38%, 용접 25%
```

---

## 기술 스택 소개

이 프로젝트는 여러 기술을 조합해서 만들었습니다. 각각이 어떤 역할인지 설명합니다.

### LangGraph — AI 에이전트의 "두뇌"

```
LangGraph = LangChain + 상태 그래프(StateGraph)
```

**LangGraph**는 LLM(대형언어모델)이 **여러 단계를 거쳐 복잡한 작업을 수행**하도록 설계하는 프레임워크입니다.

일반적인 LLM 호출은 "질문 → 응답" 한 번으로 끝나지만, LangGraph는 여러 노드(단계)를 연결하여 LLM이 **스스로 판단하며 단계를 진행**하게 합니다.

이 프로젝트에서 LangGraph가 하는 일:

```
[IntentAgent]          "이번 달 소나타 몇 대?" → 의도: production_query
     ↓
[InfoAgent]            의도에 맞는 도구(get_production_summary) 선택
     ↓
[ToolNode]             SQL 실행 → JSON 결과
     ↓
[InfoAgent 재진입]      결과 분석 → 추가 조회 필요? → 최대 3라운드 반복
     ↓
[ResponseAgent]        한국어 응답 생성
```

> **비유**: LangGraph는 "업무 매뉴얼"입니다. 신입사원(LLM)에게 "이렇게 판단하고, 이 도구를 쓰고, 이 순서로 일하세요"라고 알려주는 것입니다.

### Gemini — LLM (대형 언어 모델)

**Gemini 2.0 Flash**는 Google이 만든 LLM입니다. 이 프로젝트에서는 LangGraph 안에서 두 가지 역할을 합니다:

1. **의도 분류**: 사용자 질문을 6가지 카테고리로 분류
2. **도구 선택 + 응답 생성**: 어떤 SQL 도구를 호출할지 판단하고, 결과를 사용자에게 설명

> 다른 LLM(GPT-4, Claude 등)으로 교체할 수도 있지만, 현재는 Gemini의 속도와 비용 효율성 때문에 사용합니다.

### FastAPI — HTTP API 서버

**FastAPI**는 Python 웹 프레임워크입니다. 이 프로젝트에서는 외부 시스템(Dify, Open WebUI)이 LangGraph 에이전트와 소통할 수 있도록 HTTP 엔드포인트를 제공합니다.

```
외부 시스템 ──HTTP POST──→ FastAPI(:8500) ──→ LangGraph ──→ SQLite
                              └── /chat, /health, /reset
```

### FastMCP — MCP 프로토콜 서버

**FastMCP**는 MCP(Model Context Protocol) 서버를 쉽게 만들 수 있는 Python 라이브러리입니다.

**MCP**는 Anthropic이 만든 오픈 프로토콜로, LLM이 **외부 도구를 직접 사용**할 수 있게 해주는 표준 규격입니다.

```python
# 이것만으로 MCP 도구가 됩니다
@mcp.tool()
def get_production_summary(period: str = "this_month") -> str:
    """기간별 생산 요약"""
    rows = query("SELECT ... FROM daily_production ...")
    return json.dumps(rows)
```

> **비유**: FastAPI가 "웹 API 서버"라면, FastMCP는 "AI 도구 서버"입니다. 웹 브라우저가 API를 호출하듯, LLM이 MCP를 통해 도구를 호출합니다.

### SQLite — 데이터베이스

**SQLite**는 파일 하나(`factory.db`)로 동작하는 경량 데이터베이스입니다. 별도 서버 설치가 필요 없어 개인 프로젝트에 적합합니다.

이 프로젝트에서는 가상의 자동차 공장 생산 데이터(2026년 2월)가 저장되어 있습니다.

### Open WebUI — 채팅 인터페이스

**Open WebUI**는 ChatGPT 같은 채팅 UI를 자체 서버에 설치해서 쓸 수 있는 오픈소스 프로젝트입니다.

이 프로젝트에서 Open WebUI는 두 가지 방식으로 Factory AI와 연동됩니다:

| 방식 | 설명 | 버전 요구 |
|------|------|----------|
| **Pipeline** | Open WebUI → Pipeline 컨테이너 → FastAPI(:8500) 중계 | 모든 버전 |
| **MCP** | Open WebUI의 LLM이 MCP(:8501) 도구를 직접 호출 | v0.8.8 이상 |

### Dify — 워크플로 빌더

**Dify**는 AI 워크플로를 노코드/로우코드로 만들 수 있는 플랫폼입니다. 드래그 앤 드롭으로 LLM과 외부 API를 연결하는 "Chatflow"를 만들 수 있습니다.

이 프로젝트에서는 Dify의 **Custom Tool** 기능을 이용해 Factory AI API를 등록하고, Chatflow에서 사용합니다.

```
Dify Chatflow
    │
    └─ HTTP Request 노드 → POST localhost:8500/chat
         └─ "이번 달 생산 현황" → LangGraph → 응답
```

---

## 전체 아키텍처

### 한눈에 보는 연결도

```
┌─────────────────────────────────────────────────────────────┐
│                     프론트엔드 (3가지)                        │
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │   CLI        │  │   Dify       │  │   Open WebUI       │  │
│  │  (터미널)    │  │  (워크플로)   │  │   (채팅 UI)        │  │
│  │             │  │              │  │                    │  │
│  │ python      │  │ HTTP Request │  │ Pipeline  또는 MCP │  │
│  │  main.py    │  │    노드      │  │   2가지 경로      │  │
│  └──────┬──────┘  └──────┬───────┘  └──┬────────────┬────┘  │
│         │               │             │            │        │
└─────────┼───────────────┼─────────────┼────────────┼────────┘
          │               │             │            │
          ▼               ▼             ▼            ▼
┌─────────────────────────────────┐  ┌──────────────────────┐
│      FastAPI (:8500)            │  │   FastMCP (:8501)    │
│                                 │  │                      │
│  POST /chat ─→ LangGraph       │  │  MCP Streamable HTTP │
│  GET  /health                   │  │  POST /mcp           │
│  POST /reset                    │  │                      │
│                                 │  │  8개 도구를 MCP       │
│  IntentAgent (의도분석)          │  │  프로토콜로 직접 노출  │
│      ↓                          │  │                      │
│  InfoAgent (도구선택)            │  │  LangGraph를 거치지   │
│      ↓                          │  │  않고 SQL 직접 실행   │
│  ToolNode (SQL 실행)            │  │                      │
│      ↓                          │  └──────────┬───────────┘
│  ResponseAgent (응답생성)        │             │
│                                 │             │
└────────────────┬────────────────┘             │
                 │                               │
                 ▼                               ▼
          ┌──────────────────────────────────────────┐
          │           SQLite (factory.db)             │
          │                                          │
          │  production_lines(3) │ models(4)          │
          │  shifts(3) │ daily_production(~252)       │
          │  defects(~170) │ downtime(~18)            │
          └──────────────────────────────────────────┘
```

### 경로별 차이

| | 경로 A: LangGraph | 경로 B: MCP |
|---|---|---|
| **서버** | FastAPI `:8500` | FastMCP `:8501` |
| **LLM 위치** | 서버 내부 (Gemini) | 프론트엔드 (아무 LLM) |
| **의도 분석** | IntentAgent가 6개 카테고리 분류 | LLM이 자체 판단 |
| **도구 선택** | Gemini가 LangGraph 안에서 결정 | LLM이 MCP 프로토콜로 직접 선택 |
| **멀티스텝** | 최대 3라운드 도구 체이닝 | LLM 능력에 따라 |
| **장점** | 정교한 추론, 맞춤형 프롬프트 | 간단, LLM 교체 자유 |
| **프론트엔드** | CLI, Dify, Open WebUI Pipeline | Open WebUI MCP |

### 프론트엔드별 연결 방식

#### 1. CLI (터미널)

가장 단순한 형태. LangGraph를 직접 호출합니다.

```
터미널 → main.py → build_graph() → IntentAgent → ... → 응답 출력
```

#### 2. Dify

Dify의 Chatflow에서 HTTP Request 노드로 FastAPI를 호출합니다.

```
Dify 채팅 → Chatflow → HTTP Request 노드
                          │ POST host.docker.internal:8500/chat
                          │ body: {"message": "{{query}}", "session_id": "{{conversation_id}}"}
                          ▼
                       FastAPI → LangGraph → 응답
                          │
                       Dify가 response 필드를 사용자에게 표시
```

#### 3. Open WebUI — Pipeline 방식

Open WebUI에서 Pipeline(중간 서버)을 거쳐 FastAPI를 호출합니다.

```
Open WebUI (:3006)
    ↓ OpenAI-compatible API
Pipelines 컨테이너 (:9099)
    ↓ factory_agent.py가 HTTP 요청 중계
FastAPI (:8500)
    ↓ LangGraph
응답
```

> Pipeline은 Open WebUI의 확장 기능입니다. 외부 API를 OpenAI API 형식으로 래핑하여 Open WebUI가 호출할 수 있게 합니다.

#### 4. Open WebUI — MCP 방식

Open WebUI v0.8.8+에서 MCP를 직접 지원합니다. LangGraph를 거치지 않고 LLM이 도구를 직접 호출합니다.

```
Open WebUI (:3006)
    ↓ 사용자 질문 + 도구 목록을 LLM에게 전달
LLM (GPT-4, Claude 등)
    ↓ "get_production_summary를 호출하자"
MCP 서버 (:8501)
    ↓ SQL 실행
LLM이 결과를 해석하여 응답 생성
```

---

## 프로젝트 구조

```
factory-ai/
│
├── main.py                 # CLI 대화형 인터페이스
├── server.py               # FastAPI 서버 (:8500) — LangGraph 연동
├── mcp_server.py            # MCP 서버 (:8501) — 도구 직접 노출
├── config.py               # 설정 (DB 경로, Gemini 키, 포트)
├── requirements.txt        # Python 의존성
├── factory.db              # SQLite 데이터베이스
│
├── agents/                 # LangGraph 에이전트 로직
│   ├── state.py            #   AgentState 타입 정의
│   ├── prompts.py          #   시스템 프롬프트 2종 (의도분석/정보조회)
│   ├── intent_agent.py     #   IntentAgent — 의도 분류
│   ├── info_agent.py       #   InfoAgent + ResponseAgent — 도구 호출/응답 생성
│   └── message_trimmer.py  #   메시지 토큰 관리 (3계층)
│
├── graph/
│   └── workflow.py         # StateGraph 정의 — 노드/엣지/라우팅
│
├── tools/
│   └── factory_tools.py    # 8개 SQL 도구 (LangChain @tool)
│
├── db/
│   ├── connection.py       # SQLite 유틸 (query, execute)
│   ├── schema.sql          # 6테이블 스키마 + 마스터 데이터
│   └── seed.py             # 가상 생산 데이터 생성기
│
├── dify/
│   ├── openapi.yaml        # Dify Custom Tool 등록용 OpenAPI 스펙
│   └── README.md           # Dify 연동 가이드
│
├── open-webui/
│   ├── docker-compose.yml  # Open WebUI + Pipelines Docker 구성
│   └── pipelines/
│       └── factory_agent.py # Open WebUI Pipeline 클래스
│
├── docs/
│   └── MCP_GUIDE.md        # MCP 서버 상세 가이드
│
└── logs/                   # 서버 로그
```

---

## 가상 공장 데이터

이 프로젝트는 **가상의 자동차 공장** 데이터를 사용합니다. 실제 공장 데이터가 아닌, `db/seed.py`로 생성한 테스트용 데이터입니다.

### 공장 구성

```
🏭 가상 자동차 공장 (2026년 2월)
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

🔄 3교대 운영
├── 주간 (DAY): 06:00 ~ 14:00
├── 야간 (NIGHT): 14:00 ~ 22:00
└── 심야 (MIDNIGHT): 22:00 ~ 06:00
```

### 데이터베이스 테이블 (6개)

| 테이블 | 행 수 | 설명 |
|--------|-------|------|
| `production_lines` | 3 | 생산 라인 마스터 (LINE-1/2/3) |
| `models` | 4 | 차종 마스터 (소나타/투싼/GV70/아이오닉6) |
| `shifts` | 3 | 교대 마스터 (주간/야간/심야) |
| `daily_production` | ~252 | 일별 생산 실적 (2월 한 달) |
| `defects` | ~170 | 불량 상세 (유형: 도장/조립/용접/전장) |
| `downtime` | ~18 | 설비 정지 이력 (계획정비/설비고장/자재부족/품질이슈) |

### 데이터 특성

- **달성률**: 평일 90~100%, 주말 75~88%, 일요일 70~82%
- **불량률**: LINE-1 0.5~1.5%, LINE-2 0.5~2.0%, LINE-3 2~4% (EV 라인이 높음)
- **설비 정지**: 계획정비 6건 + 비계획정지 ~12건
- **재현 가능**: `random.seed(42)` — 같은 시드로 항상 동일한 데이터 생성

---

## 빠른 시작

### 1. 클론 및 환경 설정

```bash
git clone https://github.com/donchoru/factory-ai.git
cd factory-ai

# Python 가상환경 생성
python -m venv .venv
source .venv/bin/activate    # macOS/Linux
# .venv\Scripts\activate     # Windows

# 의존성 설치
pip install -r requirements.txt
```

### 2. Gemini API 키 설정

LangGraph 에이전트(경로 A)를 사용하려면 Gemini API 키가 필요합니다.

```bash
# .env 파일 생성
echo "GEMINI_API_KEY=your-api-key-here" > .env
```

> MCP 서버(경로 B)만 사용할 경우 API 키 없이도 동작합니다 (SQL 직접 실행).

### 3. 데이터베이스 생성

```bash
python -m db.seed
```

출력:
```
기존 DB 삭제: factory.db
스키마 생성 완료
데이터 생성 중...
  daily_production: 252행
  defects: 170행
  downtime: 18행
DB 생성 완료: factory.db
```

### 4. 실행

```bash
# CLI로 바로 테스트
python main.py

# 또는 서버 기동
python server.py       # FastAPI (:8500) — LangGraph
python mcp_server.py   # MCP (:8501) — 도구 직접 노출
```

---

## 3가지 실행 방법

### 방법 1: CLI (로컬 테스트)

```bash
python main.py
```

```
=== Factory AI — 자동차 공장 생산 질의 시스템 ===
종료: quit | 이력 초기화: clear

질문> 이번 달 생산 현황
[production_query]
📊 2026년 2월 생산 현황입니다...

질문> 그중에 불량률 높은 라인은?
[defect_query]
3라인(EV)의 불량률이 2.15%로 가장 높습니다...
```

대화 맥락을 기억합니다 ("그중에", "그 라인" 등 대명사 처리).

### 방법 2: FastAPI 서버 (:8500)

```bash
python server.py
```

```bash
# 자연어 질의
curl -X POST http://localhost:8500/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "오늘 생산 현황", "session_id": "test"}'

# 헬스체크
curl http://localhost:8500/health

# 세션 초기화
curl -X POST "http://localhost:8500/reset?session_id=test"
```

### 방법 3: MCP 서버 (:8501)

```bash
python mcp_server.py
```

Open WebUI 등 MCP 호스트에서 `http://localhost:8501/mcp`로 연결합니다.

```bash
# 동작 확인 (MCP initialize 핸드셰이크)
curl -X POST http://localhost:8501/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0", "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-03-26",
      "capabilities": {},
      "clientInfo": {"name": "test", "version": "1.0"}
    }
  }'
```

---

## 프론트엔드 연동 3가지

### 1. Dify 연동

Dify의 Custom Tool 기능으로 Factory AI API를 등록합니다.

#### 설정 순서

1. **Dify 대시보드** → Tools → Custom → Create Custom Tool
2. `dify/openapi.yaml` 내용을 붙여넣기
3. Server URL: `http://host.docker.internal:8500` (Docker) 또는 `http://localhost:8500` (로컬)
4. Chatflow 생성 → HTTP Request 노드 추가:

```
URL: http://host.docker.internal:8500/chat
Method: POST
Body:
{
  "message": "{{#sys.query#}}",
  "session_id": "{{#sys.conversation_id#}}"
}
```

> 자세한 내용: [`dify/README.md`](dify/README.md)

### 2. Open WebUI — Pipeline 방식

Docker Compose로 Open WebUI와 Pipeline 서버를 함께 실행합니다.

```bash
cd open-webui
docker compose up -d
```

- Open WebUI: http://localhost:3006
- Pipeline이 자동으로 Factory AI(:8500)에 연결됩니다

#### docker-compose.yml 구성

```
┌─ Docker ─────────────────────────────────────────┐
│                                                  │
│  open-webui (:3006)                              │
│    └── OPENAI_API_BASE_URL → pipelines:9099      │
│                                                  │
│  pipelines (:9099)                               │
│    └── factory_agent.py                          │
│         └── POST host.docker.internal:8500/chat  │
│                                                  │
└──────────────────────────────────────────────────┘
         │
         ▼ host.docker.internal
┌─ 호스트 머신 ────────────────────────────────────┐
│  FastAPI (:8500) → LangGraph → SQLite            │
└──────────────────────────────────────────────────┘
```

### 3. Open WebUI — MCP 방식 (v0.8.8+)

LLM이 도구를 **직접** 호출하는 방식입니다. Pipeline이 필요 없습니다.

#### 설정 순서

1. MCP 서버 실행: `python mcp_server.py`
2. Open WebUI 접속 → Admin Panel → Settings → Tools
3. MCP Servers 섹션에서 **+ Add** 클릭
4. URL 입력: `http://host.docker.internal:8501/mcp`
5. Save

설정 완료 후 채팅에서 자연어로 질문하면 LLM이 자동으로 도구를 선택합니다.

> 자세한 내용: [`docs/MCP_GUIDE.md`](docs/MCP_GUIDE.md)

---

## 8개 조회 도구 상세

모든 도구는 SQLite에서 데이터를 조회하여 JSON 문자열을 반환합니다.

### 1. `get_daily_production` — 일별 생산 실적

개별 생산 레코드를 조건별로 조회합니다.

```
파라미터: line(라인), model(차종), date_from(시작일), date_to(종료일), shift(교대)
예시: "2월 15일 LINE-1 주간 실적" → get_daily_production(line="LINE-1", date_from="2026-02-15", date_to="2026-02-15", shift="DAY")
```

### 2. `get_production_summary` — 기간별 생산 요약

라인별/모델별 합계와 달성률을 집계합니다.

```
파라미터: period (today / this_week / this_month)
예시: "이번 달 생산 현황" → get_production_summary(period="this_month")
```

### 3. `get_defect_stats` — 불량 통계

불량 유형별(도장/조립/용접/전장) 집계 + 라인별 불량률 + 최근 불량 10건.

```
파라미터: line, model, date_from, date_to
예시: "3라인 불량 현황" → get_defect_stats(line="LINE-3")
```

### 4. `get_line_status` — 라인 현황

라인 정보 + 최근 7일 달성률 + 오늘 실적 + 정지 횟수 + 불량률.

```
파라미터: line (빈 문자열이면 전체)
예시: "어떤 라인이 제일 잘 돌아가?" → get_line_status()
```

### 5. `get_downtime_history` — 설비 정지 이력

정지 사유별(계획정비/설비고장/자재부족/품질이슈) 집계 + 상세 내역.

```
파라미터: line, date_from, date_to
예시: "이번 달 설비 정지 이력" → get_downtime_history()
```

### 6. `get_model_comparison` — 차종별 비교

소나타/투싼/GV70/아이오닉6 간 생산량, 달성률, 불량률, 일평균 비교.

```
파라미터: date_from (기본 2026-02-01), date_to (기본 2026-02-28)
예시: "차종별 실적 비교" → get_model_comparison()
```

### 7. `get_shift_analysis` — 교대별 분석

주간/야간/심야 교대 간 생산량, 달성률, 불량률 비교.

```
파라미터: line, date_from, date_to
예시: "교대별 생산량 비교" → get_shift_analysis()
```

### 8. `get_production_trend` — 생산 추이

일별 생산량과 달성률 트렌드 (차트용 시계열 데이터).

```
파라미터: line, model, days (기본 28)
예시: "최근 2주 생산 추이" → get_production_trend(days=14)
```

### 파라미터 참조표

| 카테고리 | 한국어 | ID |
|----------|--------|-----|
| 라인 | 1라인, 세단라인 | `LINE-1` |
| | 2라인, SUV라인 | `LINE-2` |
| | 3라인, EV라인, 전기차라인 | `LINE-3` |
| 차종 | 소나타 | `SONATA` |
| | 투싼 | `TUCSON` |
| | GV70, 제네시스 | `GV70` |
| | 아이오닉6, 아이오닉 | `IONIQ6` |
| 교대 | 주간, 낮 | `DAY` |
| | 야간, 밤 | `NIGHT` |
| | 심야, 새벽 | `MIDNIGHT` |
| 기간 | 오늘 | `today` |
| | 이번 주 | `this_week` |
| | 이번 달 | `this_month` |

---

## LangGraph 에이전트 동작 원리

### StateGraph 구조

```
         ┌──────────────┐
         │ intent_agent │ ← 진입점
         │  (의도분석)   │
         └──────┬───────┘
                │
        ┌───────┴───────┐
        ▼               ▼
 ┌────────────┐  ┌────────────┐
 │ info_agent │  │  respond   │ ← general_chat이면 바로 여기로
 │ (도구선택)  │  │ (응답생성)  │
 └──────┬─────┘  └────────────┘
        │
   ┌────┴────┐
   ▼         ▼
┌───────┐ ┌────────────┐
│ tools │ │  respond   │ ← 도구 호출 불필요하면 여기로
│(SQL)  │ │ (응답생성)  │
└───┬───┘ └────────────┘
    │
    └──→ info_agent (재진입, 최대 3라운드)
```

### 처리 단계별 설명

#### Step 1: IntentAgent (의도 분석)

사용자 질문을 6가지 카테고리로 분류합니다.

```
입력: "3라인 불량률이 왜 높아?"
          ↓ Gemini 호출 (temperature=0)
출력: {"intent": "defect_query", "detail": {"line": "LINE-3"}, "reasoning": "불량 관련 질문"}
```

6가지 의도:
- `production_query` — 생산 실적/수량
- `defect_query` — 불량 통계
- `line_status` — 라인 현황
- `downtime_query` — 설비 정지
- `trend_analysis` — 추이/트렌드
- `general_chat` — 일반 대화

#### Step 2: InfoAgent (도구 선택)

의도에 맞는 도구를 선택하고 호출합니다. Gemini의 **Tool Use** 기능을 사용합니다.

```
입력: intent=defect_query, detail={line: "LINE-3"}
          ↓ Gemini 호출 (tools=ALL_TOOLS)
출력: tool_calls=[{name: "get_defect_stats", args: {line: "LINE-3"}}]
```

#### Step 2.5: ToolNode (SQL 실행)

선택된 도구를 실행하여 SQLite에서 데이터를 조회합니다.

```
입력: get_defect_stats(line="LINE-3")
          ↓ SQL 실행
출력: {"by_type": [{"defect_type": "electric", ...}], "by_line": [...], "recent_defects": [...]}
```

#### Step 2 재진입: InfoAgent (결과 분석)

도구 결과를 받아 추가 조회가 필요한지 판단합니다.

- 추가 조회 필요 → Step 2.5로 다시 이동 (최대 3라운드)
- 충분한 정보 → Step 3으로 이동

#### Step 3: ResponseAgent (응답 생성)

최종 한국어 응답을 생성합니다.

```
입력: InfoAgent의 마지막 AI 메시지 (마크다운 표 포함)
출력: "3라인(EV)의 불량 현황입니다. 전장(센서 오류)이 38%로 가장 많고..."
```

### 도구 체이닝 예시

복잡한 질문에서는 도구를 여러 번 호출합니다:

```
질문: "소나타 불량률이 높은데 왜 그래?"

Round 1: get_defect_stats(model="SONATA")
         → 불량 유형: 도장 42%, 조립 31% ...

Round 2: get_downtime_history(line="LINE-1")
         → LINE-1 설비 고장 3건, 도장 부스 관련 ...

최종 응답: "소나타의 불량률이 높은 주요 원인은 도장 불량(42%)입니다.
          LINE-1의 도장 부스 필터 교체 정비 이후에도 도장 흐름 불량이
          지속되고 있어 추가 점검이 필요합니다."
```

---

## MCP 서버 동작 원리

MCP 서버는 LangGraph를 거치지 않고 **SQL 도구를 직접 노출**합니다.

### 통신 흐름

```
[1] Open WebUI → LLM에게 질문 + 사용 가능한 도구 목록 전달
[2] LLM이 적절한 도구 선택 (예: get_production_summary)
[3] Open WebUI → MCP 서버로 도구 호출 (POST /mcp, JSON-RPC)
[4] MCP 서버 → SQLite 쿼리 실행
[5] 결과를 MCP 프로토콜로 반환
[6] LLM이 결과를 해석하여 자연어 응답 생성
```

### LangGraph vs MCP 어떤 걸 써야 할까?

| 상황 | 추천 |
|------|------|
| 정교한 멀티스텝 추론이 필요할 때 | LangGraph (경로 A) |
| 다양한 LLM을 자유롭게 바꿔가며 쓰고 싶을 때 | MCP (경로 B) |
| Gemini API 키가 없을 때 | MCP (경로 B) |
| 맞춤형 프롬프트/의도분석이 중요할 때 | LangGraph (경로 A) |
| 빠르게 프로토타이핑할 때 | MCP (경로 B) |

> 상세 가이드: [`docs/MCP_GUIDE.md`](docs/MCP_GUIDE.md)

---

## API 레퍼런스

### FastAPI (:8500)

#### `POST /chat` — 자연어 질의

```bash
curl -X POST http://localhost:8500/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "이번 달 생산 현황", "session_id": "user1"}'
```

응답:
```json
{
  "response": "📊 2026년 2월 생산 현황입니다...",
  "intent": "production_query",
  "session_id": "user1",
  "trace": ["## Step 1: IntentAgent...", "## Step 2: InfoAgent..."]
}
```

#### `GET /health` — 헬스체크

```bash
curl http://localhost:8500/health
```

응답:
```json
{
  "status": "ok",
  "db_stats": {
    "production_lines": 3,
    "models": 4,
    "shifts": 3,
    "daily_production": 252,
    "defects": 170,
    "downtime": 18
  }
}
```

#### `POST /reset` — 세션 초기화

```bash
curl -X POST "http://localhost:8500/reset?session_id=user1"
```

### MCP 서버 (:8501)

MCP 프로토콜(JSON-RPC 2.0 over Streamable HTTP)을 사용합니다.

엔드포인트: `POST /mcp`

필수 헤더:
```
Content-Type: application/json
Accept: application/json, text/event-stream
```

Open WebUI 등 MCP 호스트에서 자동으로 처리하므로 직접 호출할 일은 거의 없습니다.

---

## 트러블슈팅

### Gemini API 키 오류

```
google.api_core.exceptions.PermissionDenied
```

→ `.env` 파일에 `GEMINI_API_KEY`가 올바르게 설정되었는지 확인

### 포트 충돌

```
[Errno 48] address already in use
```

```bash
# 포트 사용 중인 프로세스 확인
lsof -i :8500   # 또는 :8501

# 강제 종료
kill $(lsof -ti:8500)
```

### factory.db가 없을 때

```bash
python -m db.seed
```

### Docker에서 호스트 접근 불가

Open WebUI/Dify가 Docker 안에서 실행 중일 때 `localhost`가 아닌 `host.docker.internal`을 사용해야 합니다.

```
✗ http://localhost:8500        ← Docker 컨테이너 안의 localhost
✓ http://host.docker.internal:8500  ← 호스트 머신의 localhost
```

### MCP 서버에서 도구가 안 보일 때

1. 서버 실행 확인: `curl http://localhost:8501/mcp ...`
2. Docker 네트워크 확인: `docker exec <container> curl http://host.docker.internal:8501/mcp`
3. Open WebUI Admin → Settings → Tools에서 URL 재확인

### 로그 확인

```bash
# FastAPI 서버
tail -f logs/server-err.log

# MCP 서버
tail -f logs/mcp-err.log
```

---

## 포트 요약

| 서비스 | 포트 | 용도 |
|--------|------|------|
| FastAPI (LangGraph) | `8500` | 자연어 질의 API |
| FastMCP (MCP) | `8501` | 도구 직접 노출 |
| Open WebUI | `3006` | 채팅 UI |
| Pipelines | `9099` | Open WebUI Pipeline |

---

## 기술 스택 요약

| 기술 | 버전 | 역할 |
|------|------|------|
| Python | 3.13 | 런타임 |
| LangGraph | 0.2+ | AI 에이전트 워크플로 |
| Gemini | 2.0 Flash | LLM (의도분석 + 응답생성) |
| FastAPI | 0.115+ | HTTP API 서버 |
| FastMCP | 3.1+ | MCP 프로토콜 서버 |
| SQLite | 내장 | 데이터베이스 |
| Open WebUI | 0.8.8+ | 채팅 프론트엔드 |
| Dify | - | 워크플로 프론트엔드 |
| Docker | - | Open WebUI/Dify 실행 |

---

## 라이선스

Private repository — 개인 프로젝트
