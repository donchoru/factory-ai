# Factory AI

**자동차 공장 생산 데이터를 자연어로 질의하는 AI 시스템**

"이번 달 소나타 몇 대 만들었어?", "3라인 불량률이 왜 높아?" 같은 질문을 입력하면, AI가 데이터베이스를 조회해서 한국어로 분석 결과를 알려줍니다.

---

## 한눈에 보는 구조

```
사용자: "이번 달 생산 현황 알려줘"
    │
    ▼
┌─ Open WebUI ────────────┐   채팅 UI (사용자와 대화)
│  ChatGPT 같은 웹 채팅    │
└────────┬────────────────┘
         │
         ▼
┌─ Dify ──────────────────┐   워크플로 엔진 (라우팅 + 간단한 건 직접 처리)
│  "이건 공장 질문이네"     │
│  → LangGraph한테 시키자   │   ← 간단한 인사/잡담은 여기서 바로 답변
└────────┬────────────────┘
         │ POST /chat
         ▼
┌─ LangGraph (:8500) ─────┐   AI 에이전트 (복잡한 분석 전담)
│  의도분석 → 도구선택      │
│  → SQL 실행 → 응답생성    │
└────────┬────────────────┘
         │
         ▼
┌─ SQLite ────────────────┐   데이터베이스
│  factory.db              │
│  (가상 공장 생산 데이터)   │
└─────────────────────────┘
```

---

## 왜 이런 구조인가?

### 각 레이어의 역할

| 레이어 | 역할 | 비유 |
|--------|------|------|
| **Open WebUI** | 사용자와 대화하는 UI | 은행 창구 (고객 응대) |
| **Dify** | 간단한 건 직접 처리, 복잡한 건 전문가에게 라우팅 | 안내 데스크 (업무 분류) |
| **LangGraph** | 여러 도구를 조합해 복잡한 분석 수행 | 전문 분석가 (실무 처리) |
| **SQLite** | 생산/불량/정지 데이터 저장 | 서류 보관실 (데이터) |

### 이 구조의 장점

```
"안녕하세요"                    → Dify가 즉시 응답 (LangGraph 호출 불필요)
"오늘 날씨 어때?"               → Dify가 즉시 응답
"이번 달 생산 현황"              → Dify → LangGraph → SQL → 분석 응답
"소나타 불량률이 높은데 왜 그래?" → Dify → LangGraph → SQL 2~3회 → 심층 분석
```

- **빠른 응답**: 간단한 질문은 Dify가 바로 답하니까 빠릅니다
- **노코드 수정**: Dify에서 프롬프트, 분류 규칙, 분기 로직을 GUI로 수정 가능 (코드 변경 없음)
- **관심사 분리**: UI, 라우팅, 분석이 각각 독립되어 한 곳을 바꿔도 나머지에 영향 없음

---

## 목차

1. [기술 스택 소개](#기술-스택-소개) — 각 기술이 뭔지, 왜 쓰는지
2. [전체 아키텍처 상세](#전체-아키텍처-상세)
3. [가상 공장 데이터](#가상-공장-데이터)
4. [빠른 시작](#빠른-시작)
5. [Dify Chatflow 설정](#dify-chatflow-설정) — 핵심 라우팅 로직
6. [Open WebUI 연동](#open-webui-연동) — Dify와 연결하는 방법
7. [8개 조회 도구](#8개-조회-도구)
8. [LangGraph 에이전트 동작 원리](#langgraph-에이전트-동작-원리)
9. [보너스: MCP 서버](#보너스-mcp-서버)
10. [API 레퍼런스](#api-레퍼런스)
11. [트러블슈팅](#트러블슈팅)

---

## 기술 스택 소개

이 프로젝트에서 쓰는 기술들을 처음 보는 분을 위해 하나씩 설명합니다.

### Open WebUI — 채팅 인터페이스

ChatGPT 같은 채팅 UI를 **내 서버에 직접 설치**해서 쓸 수 있는 오픈소스 프로젝트입니다. Docker로 실행하면 바로 웹 채팅 화면이 뜹니다.

이 프로젝트에서의 역할: **사용자가 대화하는 창구**. Open WebUI 자체는 데이터 분석을 하지 않고, Dify에게 메시지를 전달합니다.

### Dify — AI 워크플로 빌더

AI 워크플로를 **드래그 앤 드롭**으로 만들 수 있는 플랫폼입니다. 코드를 쓰지 않고도 "이 질문이 오면 → 이쪽으로 보내고, 저 질문이 오면 → 직접 답하기" 같은 로직을 만들 수 있습니다.

이 프로젝트에서의 역할: **안내 데스크**

```
질문 분류기 (Question Classifier)
    ├─ "일반 대화" → Dify의 LLM이 직접 답변 (빠름)
    └─ "공장 데이터 조회" → LangGraph 서버로 전달 (정확함)
```

Dify를 쓰는 이유: 프롬프트를 수정하거나 분류 규칙을 바꿀 때 **코드 배포 없이 웹 GUI에서 바로 변경**할 수 있습니다.

### LangGraph — AI 에이전트 프레임워크

LLM이 **여러 단계를 거쳐 복잡한 작업을 수행**하도록 설계하는 프레임워크입니다.

일반적인 LLM은 "질문 → 응답" 한 번으로 끝나지만, LangGraph는 여러 노드(단계)를 연결하여 LLM이 **스스로 판단하며 단계를 진행**하게 합니다.

```
"소나타 불량률이 높은데 왜 그래?"
    ↓
[IntentAgent]    의도 파악: defect_query
    ↓
[InfoAgent]      도구 선택: get_defect_stats(model="SONATA")
    ↓
[ToolNode]       SQL 실행 → 불량 유형별 결과
    ↓
[InfoAgent]      "도장 불량이 많네, 정지 이력도 확인해보자"
                 → get_downtime_history(line="LINE-1")  ← 자기가 추가 판단!
    ↓
[ToolNode]       SQL 실행 → 정지 이력
    ↓
[ResponseAgent]  두 결과를 종합하여 한국어 응답 생성
```

이 프로젝트에서의 역할: **복잡한 공장 데이터 분석 전담**. 최대 3라운드까지 도구를 반복 호출하며 심층 분석합니다.

### Gemini — LLM (대형 언어 모델)

Google의 **Gemini 2.0 Flash**를 사용합니다. LangGraph 안에서 의도 분류, 도구 선택, 응답 생성을 담당합니다.

### FastAPI — HTTP API 서버

LangGraph 에이전트를 HTTP 서버로 감싸는 Python 웹 프레임워크입니다. Dify가 `POST /chat`으로 호출할 수 있게 합니다.

### SQLite — 데이터베이스

파일 하나(`factory.db`)로 동작하는 경량 데이터베이스. 가상의 자동차 공장 생산 데이터가 저장되어 있습니다.

### FastMCP — MCP 프로토콜 서버 (보너스)

Anthropic의 MCP(Model Context Protocol)로 도구를 직접 노출하는 서버. Open WebUI v0.8.8+에서 LLM이 Dify를 거치지 않고 도구를 직접 호출할 수 있는 **대안 경로**입니다.

---

## 전체 아키텍처 상세

### 메인 경로: Open WebUI → Dify → LangGraph

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  ┌─ Open WebUI (:3006) ──────────────────────────────────────┐   │
│  │  사용자 채팅 UI (Docker)                                   │   │
│  │                                                           │   │
│  │  Pipeline (factory_agent.py)                              │   │
│  │    → Dify Chat API 호출                                    │   │
│  └──────────────────────────┬────────────────────────────────┘   │
│                             │                                    │
│                             ▼                                    │
│  ┌─ Dify ────────────────────────────────────────────────────┐   │
│  │  Chatflow: 질문 분류기 (Question Classifier)               │   │
│  │                                                           │   │
│  │  ┌─────────────────┐     ┌──────────────────────────────┐ │   │
│  │  │ "일반 대화"      │     │ "공장 데이터 조회"            │ │   │
│  │  │                 │     │                              │ │   │
│  │  │ LLM 노드        │     │ HTTP Request 노드            │ │   │
│  │  │ (Gemini 직접)   │     │ POST :8500/chat              │ │   │
│  │  │                 │     │                              │ │   │
│  │  │ "안녕하세요!"   │     │ "이번 달 생산 현황"           │ │   │
│  │  │ → 바로 응답     │     │ → LangGraph로 전달            │ │   │
│  │  └─────────────────┘     └──────────────┬───────────────┘ │   │
│  │                                         │                 │   │
│  └─────────────────────────────────────────┼─────────────────┘   │
│                                            │                     │
└────────────────────────────────────────────┼─────────────────────┘
                                             │
           ┌─ 호스트 머신 ───────────────────┼────────────────────┐
           │                                 ▼                    │
           │  ┌─ LangGraph + FastAPI (:8500) ──────────────────┐  │
           │  │                                                │  │
           │  │  IntentAgent (의도분석)                          │  │
           │  │      ↓                                         │  │
           │  │  InfoAgent (도구선택 + Gemini Tool Use)          │  │
           │  │      ↓                                         │  │
           │  │  ToolNode (SQL 실행 — 8개 도구)                  │  │
           │  │      ↓                                         │  │
           │  │  InfoAgent 재진입 (추가 조회 — 최대 3라운드)       │  │
           │  │      ↓                                         │  │
           │  │  ResponseAgent (한국어 응답 생성)                 │  │
           │  │                                                │  │
           │  └──────────────────────┬─────────────────────────┘  │
           │                         │                            │
           │                         ▼                            │
           │  ┌─ SQLite (factory.db) ─────────────────────────┐   │
           │  │  production_lines(3) │ models(4) │ shifts(3)   │   │
           │  │  daily_production(~252) │ defects(~170)        │   │
           │  │  downtime(~18)                                 │   │
           │  └────────────────────────────────────────────────┘   │
           │                                                      │
           └──────────────────────────────────────────────────────┘
```

### 질문 유형별 흐름

#### 간단한 질문 → Dify에서 직접 처리

```
사용자: "안녕하세요"
    ↓
Open WebUI → Dify 질문 분류기
    ↓ 판단: "일반 대화"
Dify LLM 노드
    ↓ Gemini 직접 호출
"안녕하세요! 공장 생산 관리 어시스턴트입니다. 생산 현황이나 불량 통계를 질문해보세요."
```

LangGraph를 호출하지 않으므로 **빠르고 저렴**합니다.

#### 복잡한 질문 → LangGraph로 라우팅

```
사용자: "3라인 불량률이 왜 높아?"
    ↓
Open WebUI → Dify 질문 분류기
    ↓ 판단: "공장 데이터 조회"
Dify HTTP Request 노드
    ↓ POST :8500/chat
LangGraph 서버
    ↓ IntentAgent: defect_query
    ↓ InfoAgent: get_defect_stats(line="LINE-3")
    ↓ ToolNode: SQL 실행
    ↓ InfoAgent 재진입: get_downtime_history(line="LINE-3")  ← 추가 분석
    ↓ ResponseAgent: 종합 분석 응답 생성
"3라인(EV)의 불량률이 2.15%로 높은 주요 원인은..."
```

---

## 가상 공장 데이터

가상의 자동차 공장 데이터를 사용합니다. `python -m db.seed`로 생성합니다.

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

🔄 3교대: 주간(06~14시) / 야간(14~22시) / 심야(22~06시)
```

### 데이터베이스 (6개 테이블)

| 테이블 | 행 수 | 설명 |
|--------|-------|------|
| `production_lines` | 3 | 생산 라인 (LINE-1/2/3) |
| `models` | 4 | 차종 (소나타/투싼/GV70/아이오닉6) |
| `shifts` | 3 | 교대 (주간/야간/심야) |
| `daily_production` | ~252 | 일별 생산 실적 |
| `defects` | ~170 | 불량 상세 (도장/조립/용접/전장) |
| `downtime` | ~18 | 설비 정지 이력 |

---

## 빠른 시작

### 1. 클론 및 환경 설정

```bash
git clone https://github.com/donchoru/factory-ai.git
cd factory-ai

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Gemini API 키 설정

```bash
echo "GEMINI_API_KEY=your-api-key-here" > .env
```

### 3. 데이터베이스 생성

```bash
python -m db.seed
```

### 4. LangGraph 서버 실행

```bash
python server.py    # :8500에서 대기
```

이제 Dify에서 `http://localhost:8500/chat`으로 호출할 수 있습니다.

### 5. CLI로 직접 테스트 (선택)

서버 없이 LangGraph를 직접 테스트할 수도 있습니다.

```bash
python main.py
```

```
질문> 이번 달 생산 현황
[production_query]
📊 2026년 2월 생산 현황입니다...
```

---

## Dify Chatflow 설정

Dify에서 "간단한 건 직접, 복잡한 건 LangGraph로" 라우팅하는 Chatflow를 만듭니다.

### 완성된 Chatflow 모양

```
[시작] → [질문 분류기] ─┬─ 일반 대화 → [LLM] → [끝]
                        └─ 공장 조회 → [HTTP Request :8500] → [끝]
```

### 설정 순서

#### 1. Custom Tool 등록

1. Dify 대시보드 → **Tools** → **Custom** → **Create Custom Tool**
2. `dify/openapi.yaml` 내용 붙여넣기
3. Server URL: `http://host.docker.internal:8500`

#### 2. Chatflow 생성

1. **Create App** → **Chatflow** → 이름: `Factory AI`

#### 3. 질문 분류기 (Question Classifier) 노드

| 설정 | 값 |
|------|-----|
| 모델 | Gemini 2.0 Flash |
| 클래스 1 | `일반 대화` — 공장과 무관한 질문 |
| 클래스 2 | `공장 데이터 조회` — 생산/불량/정지/라인/차종 관련 |

#### 4. LLM 노드 (일반 대화 경로)

| 설정 | 값 |
|------|-----|
| 모델 | Gemini 2.0 Flash |
| 시스템 프롬프트 | "자동차 공장 생산 관리 어시스턴트입니다. 공장과 무관한 질문에는 간단히 답하고, 생산 관련 질문을 안내하세요." |
| 입력 | `{{#sys.query#}}` |

#### 5. HTTP Request 노드 (공장 조회 경로)

| 설정 | 값 |
|------|-----|
| Method | `POST` |
| URL | `http://host.docker.internal:8500/chat` |
| Body | `{"message": "{{#sys.query#}}", "session_id": "{{#sys.conversation_id#}}"}` |
| 출력 변수 | `response` 필드 |

#### 6. Publish → API Key 발급

Chatflow를 Publish한 뒤, **API Access**에서 키를 발급받습니다 (`app-xxxxxxxxxxxx`).

> 상세 가이드: [`dify/README.md`](dify/README.md)

---

## Open WebUI 연동

Open WebUI에서 Dify Chatflow를 호출하도록 Pipeline을 연결합니다.

### docker-compose.yml 설정

```bash
cd open-webui
```

`docker-compose.yml`에서 Dify API 정보를 설정합니다:

```yaml
pipelines:
  environment:
    - DIFY_API_URL=http://host.docker.internal    # Dify 서버 주소
    - DIFY_API_KEY=app-xxxxxxxxxxxx                # Step 6에서 발급받은 키
```

### 실행

```bash
docker compose up -d
```

- Open WebUI: http://localhost:3006

### 전체 흐름

```
Open WebUI (:3006)
    ↓
Pipeline (factory_agent.py)
    ↓ POST /v1/chat-messages (Dify Chat API)
Dify
    ├─ 일반 대화 → 직접 응답
    └─ 공장 조회 → POST :8500/chat → LangGraph → 응답
```

---

## 8개 조회 도구

LangGraph가 사용하는 SQL 조회 도구들입니다. Dify를 통해 자연어로 질문하면 LangGraph가 적절한 도구를 자동 선택합니다.

| # | 도구 | 설명 | 질문 예시 |
|---|------|------|----------|
| 1 | `get_daily_production` | 일별 생산 실적 | "2월 15일 LINE-1 실적" |
| 2 | `get_production_summary` | 기간별 생산 요약 | "이번 달 생산 현황" |
| 3 | `get_defect_stats` | 불량 통계 | "3라인 불량 현황" |
| 4 | `get_line_status` | 라인 현황 | "어떤 라인이 제일 잘 돌아가?" |
| 5 | `get_downtime_history` | 설비 정지 이력 | "설비 정지 이력 보여줘" |
| 6 | `get_model_comparison` | 차종별 비교 | "차종별 실적 비교" |
| 7 | `get_shift_analysis` | 교대별 분석 | "교대별 생산량 비교" |
| 8 | `get_production_trend` | 생산 추이 | "최근 2주 생산 추이" |

### 파라미터 참조표

| 한국어 | ID | 카테고리 |
|--------|-----|---------|
| 1라인, 세단라인 | `LINE-1` | 라인 |
| 2라인, SUV라인 | `LINE-2` | 라인 |
| 3라인, EV라인 | `LINE-3` | 라인 |
| 소나타 | `SONATA` | 차종 |
| 투싼 | `TUCSON` | 차종 |
| GV70 | `GV70` | 차종 |
| 아이오닉6 | `IONIQ6` | 차종 |
| 주간 | `DAY` | 교대 |
| 야간 | `NIGHT` | 교대 |
| 심야 | `MIDNIGHT` | 교대 |

---

## LangGraph 에이전트 동작 원리

LangGraph 서버(:8500)가 복잡한 질문을 처리하는 과정입니다.

### StateGraph 구조

```
         ┌──────────────┐
         │ IntentAgent  │ ← Step 1: 의도 분류 (6가지)
         └──────┬───────┘
                │
        ┌───────┴───────┐
        ▼               ▼
 ┌────────────┐  ┌────────────┐
 │ InfoAgent  │  │  Respond   │ ← general_chat이면 바로 여기로
 │ (도구선택)  │  │ (직접응답)  │
 └──────┬─────┘  └────────────┘
        │
   ┌────┴────┐
   ▼         ▼
┌───────┐ ┌────────────┐
│ Tools │ │  Respond   │ ← 도구 불필요하면 여기로
│ (SQL) │ └────────────┘
└───┬───┘
    │
    └──→ InfoAgent (재진입, 최대 3라운드)
```

### 도구 체이닝 예시

복잡한 질문에서는 LangGraph가 **스스로 판단하여** 도구를 여러 번 호출합니다:

```
질문: "소나타 불량률이 높은데 왜 그래?"

Round 1: get_defect_stats(model="SONATA")
         → 도장 42%, 조립 31% ...

Round 2: get_downtime_history(line="LINE-1")     ← LLM이 추가 분석 결정
         → 도장 부스 필터 교체 정비 이력 ...

최종: "소나타 불량의 주요 원인은 도장 불량(42%)이며,
      LINE-1 도장 부스 정비 이후에도 지속되고 있어 추가 점검이 필요합니다."
```

Dify의 단순 라우팅으로는 이런 **멀티스텝 추론**을 할 수 없어서, 복잡한 질문은 LangGraph에게 맡기는 것입니다.

---

## 보너스: MCP 서버

메인 경로(Open WebUI → Dify → LangGraph) 외에, **MCP(Model Context Protocol)** 서버도 제공합니다.

MCP는 LLM이 도구를 직접 호출할 수 있게 해주는 프로토콜입니다. Open WebUI v0.8.8+에서 지원합니다.

```bash
python mcp_server.py    # :8501에서 대기
```

Open WebUI Admin → Settings → Tools → MCP Servers → `http://host.docker.internal:8501/mcp`

Dify/LangGraph를 거치지 않고 LLM이 SQL 도구를 **직접** 호출하는 대안 경로입니다.

> 상세 가이드: [`docs/MCP_GUIDE.md`](docs/MCP_GUIDE.md)

---

## 프로젝트 구조

```
factory-ai/
│
├── server.py               # LangGraph 서버 (:8500) — Dify가 호출
├── mcp_server.py            # MCP 서버 (:8501) — 보너스 경로
├── main.py                 # CLI 테스트용
├── config.py               # 설정 (DB 경로, Gemini 키)
│
├── agents/                 # LangGraph 에이전트
│   ├── state.py            #   상태 타입 정의
│   ├── prompts.py          #   시스템 프롬프트 (의도분석/정보조회)
│   ├── intent_agent.py     #   IntentAgent — 의도 분류
│   ├── info_agent.py       #   InfoAgent + ResponseAgent
│   └── message_trimmer.py  #   메시지 토큰 관리
│
├── graph/
│   └── workflow.py         # StateGraph 정의 (노드/엣지/라우팅)
│
├── tools/
│   └── factory_tools.py    # 8개 SQL 도구
│
├── db/
│   ├── connection.py       # SQLite 유틸 (query 함수)
│   ├── schema.sql          # 6테이블 스키마
│   └── seed.py             # 가상 데이터 생성기
│
├── dify/
│   ├── openapi.yaml        # Dify Custom Tool 스펙
│   └── README.md           # Dify Chatflow 설정 가이드
│
├── open-webui/
│   ├── docker-compose.yml  # Open WebUI + Pipeline (Docker)
│   └── pipelines/
│       └── factory_agent.py # Dify API 호출 Pipeline
│
├── docs/
│   └── MCP_GUIDE.md        # MCP 서버 상세 가이드
│
├── requirements.txt
└── factory.db              # SQLite 데이터베이스
```

---

## API 레퍼런스

### LangGraph 서버 (:8500)

Dify에서 호출하는 엔드포인트입니다.

```bash
# 자연어 질의
curl -X POST http://localhost:8500/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "이번 달 생산 현황", "session_id": "test"}'

# 응답
# {"response": "📊 2026년 2월...", "intent": "production_query", ...}

# 헬스체크
curl http://localhost:8500/health

# 세션 초기화
curl -X POST "http://localhost:8500/reset?session_id=test"
```

### MCP 서버 (:8501)

```bash
# MCP 핸드셰이크 (Open WebUI가 자동 처리)
curl -X POST http://localhost:8501/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize",...}'
```

---

## 트러블슈팅

### Dify에서 LangGraph 연결 실패

```
# LangGraph 서버가 실행 중인지 확인
curl http://localhost:8500/health

# Dify가 Docker 안이면 host.docker.internal 사용
# ✗ http://localhost:8500
# ✓ http://host.docker.internal:8500
```

### Gemini API 키 오류

```bash
# .env 파일 확인
cat .env
# GEMINI_API_KEY=your-key-here
```

### 포트 충돌

```bash
lsof -i :8500
kill $(lsof -ti:8500)
```

### factory.db가 없을 때

```bash
python -m db.seed
```

### 로그 확인

```bash
tail -f logs/server-err.log    # LangGraph 서버
tail -f logs/mcp-err.log       # MCP 서버
```

---

## 포트 요약

| 서비스 | 포트 | 역할 |
|--------|------|------|
| LangGraph + FastAPI | `8500` | AI 에이전트 서버 (Dify가 호출) |
| MCP (FastMCP) | `8501` | 도구 직접 노출 (보너스) |
| Open WebUI | `3006` | 채팅 UI |
| Pipelines | `9099` | Open WebUI → Dify 중계 |

---

## 기술 스택 요약

| 기술 | 역할 | 레이어 |
|------|------|--------|
| **Open WebUI** | 채팅 UI | 프론트엔드 |
| **Dify** | 라우팅 + 간단한 응답 | 미들웨어 |
| **LangGraph** | 멀티스텝 에이전트 | 백엔드 |
| Gemini 2.0 Flash | LLM | LangGraph 내부 |
| FastAPI | HTTP 서버 | LangGraph 래퍼 |
| FastMCP | MCP 서버 | 보너스 경로 |
| SQLite | 데이터베이스 | 데이터 |
| Docker | 컨테이너 | 인프라 |
