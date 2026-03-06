# Factory AI — MCP 서버 가이드

> 자동차 공장 생산 데이터를 자연어로 질의하는 시스템에 **MCP(Model Context Protocol)** 서버를 추가한 과정을 처음부터 끝까지 설명합니다.

---

## 목차

1. [배경: 왜 MCP를 추가했나?](#1-배경-왜-mcp를-추가했나)
2. [MCP란 무엇인가?](#2-mcp란-무엇인가)
3. [아키텍처 비교: Before vs After](#3-아키텍처-비교-before-vs-after)
4. [프로젝트 구조](#4-프로젝트-구조)
5. [사용 가능한 도구 8개](#5-사용-가능한-도구-8개)
6. [설치 및 실행](#6-설치-및-실행)
7. [Open WebUI 연동](#7-open-webui-연동)
8. [동작 원리 상세](#8-동작-원리-상세)
9. [트러블슈팅](#9-트러블슈팅)

---

## 1. 배경: 왜 MCP를 추가했나?

### 기존 구조의 문제

Factory AI는 자동차 공장의 생산 데이터(일별 실적, 불량, 설비 정지 등)를 자연어로 질의할 수 있는 시스템입니다.

기존에는 이런 흐름으로 동작했습니다:

```
사용자: "이번 달 생산 현황 알려줘"
    ↓
Open WebUI (채팅 UI)
    ↓
Pipeline (패스스루 — 그냥 전달만 함)
    ↓
FastAPI 서버 (:8500)
    ↓
LangGraph 에이전트 (IntentAgent → InfoAgent → ToolNode)
    ↓
Gemini가 "어떤 도구를 쓸지" 판단 → SQL 실행 → 응답 생성
```

이 구조에서 **Gemini(LLM)는 LangGraph 안에 갇혀 있습니다.** Open WebUI의 LLM은 단순히 Factory AI 서버에 메시지를 전달하는 중개인 역할만 합니다. Open WebUI에 연결된 LLM(예: GPT-4, Claude)이 아무리 똑똑해도, 직접 공장 데이터를 조회할 방법이 없었습니다.

### MCP로 해결

MCP 서버를 추가하면:

```
사용자: "이번 달 생산 현황 알려줘"
    ↓
Open WebUI (채팅 UI)
    ↓
Open WebUI의 LLM이 직접 "get_production_summary" 도구 선택
    ↓
MCP 서버 (:8501) → SQLite 직접 조회
    ↓
결과를 LLM이 직접 해석하여 응답
```

**핵심 차이**: Open WebUI에 연결된 LLM이 **직접** 공장 데이터 조회 도구를 사용할 수 있게 됩니다.

---

## 2. MCP란 무엇인가?

### 한 줄 요약

> MCP(Model Context Protocol)는 **LLM이 외부 도구를 사용할 수 있게 해주는 표준 프로토콜**입니다.

### 쉬운 비유

LLM을 "매우 똑똑한 신입사원"이라고 생각해보세요.

- **MCP 없이**: 신입사원이 회사 시스템에 접근할 수 없어서, 매번 선배(LangGraph)에게 "이 데이터 좀 찾아주세요"라고 부탁해야 합니다.
- **MCP 있으면**: 신입사원에게 회사 시스템 계정을 만들어줘서, 직접 데이터를 조회할 수 있습니다.

### 기술적으로

MCP는 Anthropic이 만든 오픈 프로토콜로, LLM 애플리케이션(호스트)과 외부 데이터/도구(서버) 사이의 통신 규격입니다.

```
┌─────────────────┐     MCP 프로토콜     ┌─────────────────┐
│   MCP 호스트     │ ◄──────────────────► │   MCP 서버       │
│ (Open WebUI,    │   JSON-RPC 2.0      │ (Factory AI,    │
│  Claude Desktop,│   over HTTP         │  파일시스템,     │
│  Cursor 등)     │                     │  DB 등)         │
└─────────────────┘                     └─────────────────┘
```

### Streamable HTTP란?

MCP는 여러 전송 방식(transport)을 지원합니다:

| Transport | 설명 | 용도 |
|-----------|------|------|
| **stdio** | 표준 입출력 | 로컬 프로세스 (Claude Desktop 등) |
| **SSE** | Server-Sent Events | 레거시 HTTP 연결 |
| **Streamable HTTP** | HTTP POST + SSE | **웹 서비스용 (우리가 사용)** |

Streamable HTTP는 `POST /mcp` 엔드포인트에 JSON-RPC 메시지를 보내는 방식입니다. Open WebUI v0.8.8부터 이 방식을 지원합니다.

---

## 3. 아키텍처 비교: Before vs After

### Before: Pipeline 방식만 존재

```
Open WebUI (:3006)
    │
    ▼
Pipelines 컨테이너 (:9099)
    │  factory_agent.py가 HTTP 요청을 중계
    ▼
FastAPI 서버 (:8500)
    │
    ├─ IntentAgent (Gemini) ─── 의도 분류
    │       ↓
    ├─ InfoAgent (Gemini) ──── 도구 선택 + 호출
    │       ↓
    ├─ ToolNode ─────────────── SQL 실행
    │       ↓
    └─ ResponseAgent ────────── 응답 생성
         │
         ▼
    SQLite (factory.db)
```

**특징**: Gemini가 의도분석 → 도구선택 → 응답생성까지 전부 담당. Open WebUI의 LLM은 참여하지 않음.

### After: MCP 방식 추가

```
Open WebUI (:3006)
    │
    ├─ [기존] Pipeline 경로 ──────────── FastAPI (:8500) → LangGraph
    │
    └─ [신규] MCP 경로
         │
         ▼
    Open WebUI의 LLM (GPT-4, Claude 등)
         │  "get_production_summary 도구를 호출해야겠다"
         │
         ▼
    MCP 서버 (:8501)
         │  Streamable HTTP (POST /mcp)
         ▼
    SQLite (factory.db)
```

**특징**: Open WebUI에 연결된 LLM이 직접 도구를 선택하고 결과를 해석. LangGraph를 거치지 않음.

### 두 방식의 공존

| 항목 | Pipeline (기존) | MCP (신규) |
|------|----------------|------------|
| 포트 | :8500 (FastAPI) | :8501 (FastMCP) |
| LLM | 내부 Gemini | Open WebUI에 연결된 아무 LLM |
| 도구 선택 | Gemini가 LangGraph 안에서 | LLM이 MCP 프로토콜로 직접 |
| 의도 분석 | IntentAgent가 6개 의도 분류 | LLM이 자체 판단 |
| 프로세스 | `python server.py` | `python mcp_server.py` |
| 장점 | 정교한 멀티스텝 추론 | 간단, LLM 선택 자유 |

두 서버는 **같은 `factory.db`를 읽기 전용으로 공유**하므로 충돌 없이 동시에 실행됩니다.

---

## 4. 프로젝트 구조

```
factory-ai/
├── mcp_server.py          ← 신규: MCP 서버 (8개 도구, :8501)
├── server.py              ← 기존: FastAPI 서버 (LangGraph, :8500)
├── main.py                ← CLI 대화형 인터페이스
├── config.py              ← 환경 변수 (DB 경로, Gemini 키 등)
│
├── tools/
│   └── factory_tools.py   ← 8개 도구 원본 (@tool 데코레이터 — LangGraph용)
│
├── db/
│   ├── connection.py      ← SQLite 유틸 (query, execute 함수)
│   ├── schema.sql         ← 6개 테이블 DDL + 마스터 데이터
│   └── seed.py            ← 가상 생산 데이터 생성기
│
├── agents/                ← LangGraph 에이전트 (Pipeline 방식 전용)
│   ├── state.py
│   ├── prompts.py
│   ├── intent_agent.py
│   ├── info_agent.py
│   └── message_trimmer.py
│
├── graph/
│   └── workflow.py        ← StateGraph 정의 (LangGraph 워크플로)
│
├── open-webui/
│   ├── docker-compose.yml ← Open WebUI + Pipelines 컨테이너
│   └── pipelines/
│       └── factory_agent.py
│
├── dify/
│   ├── openapi.yaml
│   └── README.md
│
├── docs/
│   └── MCP_GUIDE.md       ← 이 문서
│
├── requirements.txt
├── factory.db             ← SQLite 데이터베이스
└── CLAUDE.md
```

### 핵심 파일 관계

```
mcp_server.py (MCP 서버)
    │
    ├── from db.connection import query   ← SQL 실행 유틸 공유
    │       └── config.py → DB_PATH
    │             └── factory.db
    │
    └── from fastmcp import FastMCP       ← MCP 프로토콜 처리
```

`mcp_server.py`는 기존의 `tools/factory_tools.py`에 있는 8개 도구의 SQL 로직을 **복사**하여 `@mcp.tool()` 데코레이터로 감쌌습니다. 데이터베이스 접근은 기존 `db/connection.py`의 `query()` 함수를 그대로 사용합니다.

> **왜 기존 도구를 import하지 않고 복사했나?**
> 기존 도구는 LangChain의 `@tool` 데코레이터가 붙어있어 반환값이 LangChain 형식입니다.
> MCP 서버는 FastMCP의 `@mcp.tool()` 데코레이터가 필요하므로, SQL 로직만 가져와서 새 데코레이터를 적용했습니다.

---

## 5. 사용 가능한 도구 8개

### 데이터베이스 구조 (미리 알면 좋은 것)

```
production_lines (3개 라인)
├── LINE-1: 1라인 (세단) — 소나타, 교대당 120대
├── LINE-2: 2라인 (SUV) — 투싼+GV70, 교대당 80대
└── LINE-3: 3라인 (EV) — 아이오닉6, 교대당 60대

models (4개 차종)
├── SONATA (소나타) → LINE-1
├── TUCSON (투싼) → LINE-2
├── GV70 → LINE-2
└── IONIQ6 (아이오닉6) → LINE-3

shifts (3교대)
├── DAY (주간): 06:00~14:00
├── NIGHT (야간): 14:00~22:00
└── MIDNIGHT (심야): 22:00~06:00

daily_production (~252행): 일별 생산 실적
defects (~170행): 불량 상세
downtime (~18행): 설비 정지 이력
```

### 도구 상세

#### 1. `get_daily_production` — 일별 생산 실적

개별 생산 레코드를 날짜/라인/모델/교대 조건으로 조회합니다.

| 파라미터 | 타입 | 설명 | 예시 |
|----------|------|------|------|
| `line` | string | 라인 ID | `"LINE-1"`, `""` (전체) |
| `model` | string | 모델 ID | `"SONATA"`, `""` (전체) |
| `date_from` | string | 시작일 | `"2026-02-01"` |
| `date_to` | string | 종료일 | `"2026-02-28"` |
| `shift` | string | 교대 ID | `"DAY"`, `""` (전체) |

**사용 예시 (자연어):**
- "2월 15일 LINE-1 생산 실적" → `get_daily_production(line="LINE-1", date_from="2026-02-15", date_to="2026-02-15")`
- "소나타 야간 생산량" → `get_daily_production(model="SONATA", shift="NIGHT")`

---

#### 2. `get_production_summary` — 기간별 생산 요약

라인별/모델별 합계와 달성률을 집계합니다.

| 파라미터 | 타입 | 설명 | 예시 |
|----------|------|------|------|
| `period` | string | 기간 | `"today"`, `"this_week"`, `"this_month"` |

**반환 구조:**
```json
{
  "period": "this_month",
  "by_line": [
    {"line_id": "LINE-1", "line_name": "1라인 (세단)", "total_planned": 9600,
     "total_actual": 8704, "achievement_rate": 90.7, "defect_rate": 1.02}
  ],
  "by_model": [
    {"model_id": "SONATA", "model_name": "소나타", "total_actual": 8704, ...}
  ]
}
```

---

#### 3. `get_defect_stats` — 불량 통계

불량 유형별 집계 + 라인별 불량률 + 최근 불량 상세(10건).

| 파라미터 | 설명 |
|----------|------|
| `line` | 라인 ID (선택) |
| `model` | 모델 ID (선택) |
| `date_from` | 시작일 (선택) |
| `date_to` | 종료일 (선택) |

**불량 유형**: `paint`(도장), `assembly`(조립), `welding`(용접), `electric`(전장)

---

#### 4. `get_line_status` — 라인 현황

라인 정보 + 최근 7일 달성률 + 오늘 실적 + 정지 횟수.

| 파라미터 | 설명 |
|----------|------|
| `line` | 라인 ID. 빈 문자열이면 전체 라인. |

---

#### 5. `get_downtime_history` — 설비 정지 이력

정지 사유별 집계(합계/평균) + 상세 내역.

| 파라미터 | 설명 |
|----------|------|
| `line` | 라인 ID (선택) |
| `date_from` | 시작일 (선택) |
| `date_to` | 종료일 (선택) |

**정지 사유**: `planned_maintenance`(계획정비), `equipment_failure`(설비고장), `material_shortage`(자재부족), `quality_issue`(품질문제)

---

#### 6. `get_model_comparison` — 차종별 비교

모델 간 생산량, 달성률, 불량률, 일평균 비교.

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `date_from` | 시작일 | `"2026-02-01"` |
| `date_to` | 종료일 | `"2026-02-28"` |

---

#### 7. `get_shift_analysis` — 교대별 분석

교대(주간/야간/심야) 간 생산량, 달성률, 불량률 비교.

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `line` | 라인 ID (선택) | `""` (전체) |
| `date_from` | 시작일 | `"2026-02-01"` |
| `date_to` | 종료일 | `"2026-02-28"` |

---

#### 8. `get_production_trend` — 생산 추이

일별 생산량과 달성률 트렌드 (차트용 데이터).

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `line` | 라인 ID (선택) | `""` (전체) |
| `model` | 모델 ID (선택) | `""` (전체) |
| `days` | 최근 N일 | `28` |

---

## 6. 설치 및 실행

### 사전 요구사항

- Python 3.12 이상
- factory.db가 생성되어 있어야 합니다 (없으면 `python -m db.seed`)

### Step 1: 의존성 설치

```bash
cd /path/to/factory-ai
source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt`에 `fastmcp>=2.0.0`이 포함되어 있습니다.

### Step 2: MCP 서버 실행

```bash
python mcp_server.py
```

성공하면 이런 출력이 나옵니다:

```
╭──────────────────────────────────────────────────╮
│          ▄▀▀ ▄▀█ █▀▀ ▀█▀ █▀▄▀█ █▀▀ █▀█          │
│          █▀  █▀█ ▄▄█  █  █ ▀ █ █▄▄ █▀▀          │
│                                                  │
│                  FastMCP 3.1.0                   │
│                                                  │
│         Server:      Factory AI, 3.1.0           │
╰──────────────────────────────────────────────────╯

Starting MCP server 'Factory AI' with transport 'streamable-http'
on http://0.0.0.0:8501/mcp
```

### Step 3: 동작 확인

```bash
# MCP initialize 핸드셰이크 테스트
curl -X POST http://localhost:8501/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-03-26",
      "capabilities": {},
      "clientInfo": {"name": "test", "version": "1.0"}
    }
  }'
```

정상 응답:
```
event: message
data: {"jsonrpc":"2.0","id":1,"result":{
  "protocolVersion":"2025-03-26",
  "serverInfo":{"name":"Factory AI","version":"3.1.0"},
  ...
}}
```

### Step 4: macOS 자동 시작 등록 (선택)

```bash
# plist 파일이 ~/Library/LaunchAgents/ 에 있어야 합니다
launchctl load ~/Library/LaunchAgents/com.dongcheol.factory-mcp.plist

# 상태 확인
launchctl list | grep factory-mcp

# 중지
launchctl unload ~/Library/LaunchAgents/com.dongcheol.factory-mcp.plist
```

plist 내용 (`com.dongcheol.factory-mcp.plist`):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.dongcheol.factory-mcp</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/factory-ai/.venv/bin/python</string>
        <string>mcp_server.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/factory-ai</string>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/path/to/factory-ai/logs/mcp.log</string>
    <key>StandardErrorPath</key>
    <string>/path/to/factory-ai/logs/mcp-err.log</string>
</dict>
</plist>
```

---

## 7. Open WebUI 연동

### Open WebUI란?

Open WebUI는 ChatGPT 같은 채팅 인터페이스를 자체 서버에 설치해서 쓸 수 있는 오픈소스 프로젝트입니다. v0.8.8부터 MCP Streamable HTTP를 네이티브 지원합니다.

### 설정 방법

#### 1. Open WebUI가 Docker로 실행 중인 경우

```bash
cd open-webui
docker compose up -d
# Open WebUI: http://localhost:3006
```

#### 2. MCP 서버 연결 추가

1. Open WebUI 웹 접속 (http://localhost:3006)
2. 좌측 하단 **사용자 아이콘** → **Admin Panel**
3. **Settings** → **Tools** 탭
4. **MCP Servers** 섹션에서 **"+ Add"** 클릭
5. URL 입력:

```
http://host.docker.internal:8501/mcp
```

> `host.docker.internal`은 Docker 컨테이너 안에서 호스트 머신의 localhost에 접근하기 위한 특별한 주소입니다. Open WebUI가 Docker로 실행 중이고, MCP 서버는 호스트에서 실행 중이므로 이 주소를 사용합니다.

6. **Save** 클릭

#### 3. 도구가 연결되었는지 확인

설정 저장 후 Tools 섹션에서 8개 도구가 표시되면 성공:

```
get_daily_production      일별 생산 실적 조회
get_production_summary    기간별 생산 요약
get_defect_stats          불량 통계
get_line_status           라인 현황
get_downtime_history      설비 정지 이력
get_model_comparison      차종별 생산 비교
get_shift_analysis        교대별 생산 분석
get_production_trend      생산 추이
```

#### 4. 채팅에서 사용

Open WebUI에서 새 채팅을 열고 자연어로 질문하면, LLM이 자동으로 적절한 도구를 선택하여 호출합니다.

**예시 대화:**

```
사용자: 이번 달 생산 현황 알려줘

AI: [get_production_summary 도구 호출 중...]

AI: 2026년 2월 생산 현황입니다.

| 라인 | 목표 | 실적 | 달성률 | 불량률 |
|------|------|------|--------|--------|
| 1라인 (세단) | 9,600 | 8,704 | 90.7% | 1.02% |
| 2라인 (SUV) | 6,400 | 5,832 | 91.1% | 1.45% |
| 3라인 (EV) | 4,800 | 4,356 | 90.8% | 0.87% |
```

```
사용자: LINE-2 불량이 좀 높은데 어떤 유형이 많아?

AI: [get_defect_stats 도구 호출 중...]

AI: LINE-2의 불량 유형별 현황입니다.
...
```

---

## 8. 동작 원리 상세

### MCP 서버 코드 구조

`mcp_server.py`의 핵심은 매우 단순합니다:

```python
from fastmcp import FastMCP
from db.connection import query

# 1. MCP 서버 인스턴스 생성
mcp = FastMCP("Factory AI")

# 2. 도구 등록 (@mcp.tool 데코레이터)
@mcp.tool()
def get_production_summary(period: str = "this_month") -> str:
    """기간별 생산 요약 — 라인별, 모델별 합계와 달성률."""
    # SQL 실행
    rows = query("SELECT ... FROM daily_production ...")
    return json.dumps(rows, ensure_ascii=False)

# ... 나머지 7개 도구도 동일 패턴 ...

# 3. 서버 시작
if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8501)
```

### 통신 흐름 (자세히)

사용자가 "이번 달 생산 현황"을 입력했을 때:

```
[1] Open WebUI → LLM에게 사용자 메시지 + 사용 가능한 도구 목록 전달
    "사용자가 '이번 달 생산 현황'이라고 물었습니다.
     사용 가능한 도구: get_daily_production, get_production_summary, ..."

[2] LLM이 판단
    "생산 요약이 필요하니까 get_production_summary(period='this_month')를 호출하자"

[3] Open WebUI → MCP 서버로 도구 호출 요청 (HTTP POST /mcp)
    {"jsonrpc":"2.0", "method":"tools/call",
     "params":{"name":"get_production_summary","arguments":{"period":"this_month"}}}

[4] MCP 서버가 SQL 실행
    SELECT ... FROM daily_production WHERE production_date >= '2026-02-01' ...

[5] MCP 서버 → Open WebUI로 결과 반환
    {"result": {"content": [{"text": "{\"period\":\"this_month\",\"by_line\":[...]}"}]}}

[6] Open WebUI → LLM에게 도구 결과 전달
    "도구 호출 결과: {JSON 데이터}"

[7] LLM이 결과를 해석하여 사용자에게 자연어 응답 생성
    "2026년 2월 생산 현황입니다. 1라인은 목표 9,600대 중 8,704대를 생산하여..."
```

### db/connection.py — 데이터베이스 접근

```python
import sqlite3
from config import DB_PATH  # factory.db 경로

def query(sql: str, params: tuple = ()) -> list[dict]:
    """SELECT 실행 → dict 리스트 반환."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # 컬럼명으로 접근 가능
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
```

모든 도구는 이 `query()` 함수를 사용하여 SQLite에서 데이터를 조회합니다. 쓰기 작업은 하지 않으므로 동시 접근에 안전합니다.

---

## 9. 트러블슈팅

### 포트 충돌

```
[Errno 48] address already in use
```

이미 8501 포트를 사용하는 프로세스가 있습니다.

```bash
# 포트 사용 프로세스 확인
lsof -i :8501

# 강제 종료
kill $(lsof -ti:8501)
```

### Open WebUI에서 도구가 안 보임

1. MCP 서버가 실행 중인지 확인:
   ```bash
   curl http://localhost:8501/mcp \
     -X POST \
     -H "Content-Type: application/json" \
     -H "Accept: application/json, text/event-stream" \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
   ```

2. Docker 네트워크 확인 — `host.docker.internal`이 작동하는지:
   ```bash
   docker exec factory-open-webui curl http://host.docker.internal:8501/mcp
   ```

3. Open WebUI Admin → Settings → Tools에서 URL을 다시 확인

### factory.db가 없을 때

```bash
python -m db.seed
```

이 명령어로 가상 생산 데이터가 포함된 `factory.db`를 생성합니다.

### 로그 확인

```bash
# launchd로 실행한 경우
tail -f logs/mcp.log        # 표준 출력
tail -f logs/mcp-err.log    # 에러 로그
```

---

## 부록: 포트 요약

| 서비스 | 포트 | 설명 |
|--------|------|------|
| FastAPI (LangGraph) | 8500 | 기존 자연어 질의 서버 |
| **MCP (FastMCP)** | **8501** | **신규 — 도구 직접 노출** |
| Open WebUI | 3006 | 채팅 UI (Docker) |
| Pipelines | 9099 | Open WebUI Pipeline (Docker) |
