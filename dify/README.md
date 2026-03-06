# Dify Chatflow 설정 가이드

> **기본 구성: Pipeline → Dify Chatflow (3분류) → LLM / Agent+MCP / LangGraph**
> Dify가 질문을 분류하고 각 경로에 맞는 처리를 수행합니다.

---

## 목표 아키텍처

```
User → Open WebUI (:3006) → Pipeline (:9099) → Dify Chatflow (3분류, SSE)
  ├─ 일반 대화   → Dify LLM 노드        → message 이벤트 (진짜 스트리밍, 빠름)
  ├─ 간단한 조회 → Dify Agent + MCP 도구 → agent_message 이벤트 (진짜 스트리밍)
  └─ 복잡한 분석 → HTTP Request → LangGraph (:8500) → JSON → Pipeline이 파싱
```

각 컴포넌트 역할:

| 컴포넌트 | 역할 |
|----------|------|
| Open WebUI | 채팅 UI |
| Pipeline | 프로토콜 변환 + 진행상태 표시 |
| Dify | 질문 분류 + 오케스트레이션 + 간단한 작업 |
| MCP | 공유 도구 레이어 (Dify Agent가 호출) |
| LangGraph | 복잡한 멀티스텝 분석만 |

---

## 사전 준비

1. **Dify 실행 중** (Docker 또는 클라우드)
2. **MCP 서버**: `python mcp_server.py` (:8501)
3. **factory.db 생성**: `python -m db.seed` (최초 1회)
4. **LangGraph 서버**: `python server.py` (:8500)

---

## Step 1: MCP 서버 연결

1. Dify 대시보드 → **Tools** → **MCP**
2. **Add MCP Server** 클릭
3. 설정:
   - **Name**: `Factory AI`
   - **URL**: `http://host.docker.internal:8501/mcp`
4. **Save** → 8개 도구 자동 인식:

| 도구 | 설명 |
|------|------|
| get_daily_production | 일별 생산 실적 |
| get_production_summary | 기간별 요약 |
| get_defect_stats | 불량 통계 |
| get_line_status | 라인 현황 |
| get_downtime_history | 정지 이력 |
| get_model_comparison | 차종별 비교 |
| get_shift_analysis | 교대별 분석 |
| get_production_trend | 생산 추이 |

---

## Step 2: Chatflow 생성

Dify 대시보드 → **Studio** → **Create App** → **Chatflow**

### 2-1. 질문 분류기 (Question Classifier)

시작 노드 바로 다음에 **Question Classifier** 노드를 추가합니다.

**모델**: Gemini 2.0 Flash (또는 사용 가능한 LLM)

**분류 클래스**:

| 클래스 | 설명 | 예시 키워드 |
|--------|------|------------|
| `일반 대화` | 공장 데이터와 무관한 대화, 인사, 일반 지식 | "안녕", "MCP가 뭐야?", "날씨" |
| `간단한 조회` | 단일 도구로 답변 가능한 데이터 질의 | "오늘 생산 현황", "1라인 상태", "불량 통계" |
| `복잡한 분석` | 여러 데이터를 종합해야 하는 분석/비교/원인추론 | "불량률이 왜 높아?", "라인별 효율 비교해서 개선 방안 제시", "추이 분석하고 예측" |

**분류 프롬프트** (Advanced Settings):
```
자동차 공장 생산 데이터 질의 시스템입니다.

분류 기준:
- "일반 대화": 공장/생산 데이터와 무관한 질문 (인사, 일반 지식, 잡담)
- "간단한 조회": 하나의 도구 호출로 바로 답변 가능한 직접적인 데이터 질문
  예: "오늘 생산량", "1라인 상태", "불량 현황", "정지 이력"
- "복잡한 분석": 여러 데이터를 조합해야 하거나, 원인 분석/비교/추세/개선안이 필요한 질문
  예: "불량률이 왜 높아?", "라인별 효율 비교", "추이 분석하고 개선안 제시해줘"
```

### 2-2. 일반 대화 경로 → LLM 노드

**LLM 노드** 추가 → 질문 분류기의 "일반 대화" 출력에 연결

| 설정 | 값 |
|------|-----|
| Model | Gemini 2.0 Flash |
| Temperature | 0.7 |

**시스템 프롬프트**:
```
당신은 Factory AI 어시스턴트입니다.
자동차 공장 관련 일반 질문에 친절하게 답하세요.
공장 데이터 조회가 필요한 질문은 "데이터를 조회해 볼까요?"라고 안내하세요.
```

→ **End** 노드에 연결

### 2-3. 간단한 조회 경로 → Agent 노드

**Agent 노드** 추가 → 질문 분류기의 "간단한 조회" 출력에 연결

| 설정 | 값 |
|------|-----|
| Model | Gemini 2.0 Flash |
| Temperature | 0 |
| Tools | Factory AI MCP 8개 전체 선택 |
| Max Iterations | 3 |

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

→ **End** 노드에 연결

### 2-4. 복잡한 분석 경로 → HTTP Request 노드

**HTTP Request 노드** 추가 → 질문 분류기의 "복잡한 분석" 출력에 연결

| 설정 | 값 |
|------|-----|
| Method | `POST` |
| URL | `http://host.docker.internal:8500/chat` |
| Headers | `Content-Type: application/json` |
| **Timeout** | **120초** (기본 60초 → 반드시 증가) |

**Body** (JSON):
```json
{
  "message": "{{#sys.query#}}",
  "session_id": "{{#sys.conversation_id#}}"
}
```

#### End 노드 출력 설정 (2가지 방식)

**방식 A (권장)**: End 노드에서 `response` 필드만 추출
```
{{#http_request_node.body.response#}}
```
→ Pipeline이 텍스트를 직접 스트리밍. 가장 빠르고 깔끔.

**방식 B (폴백)**: End 노드에서 전체 JSON body 출력
```
{{#http_request_node.body#}}
```
→ Pipeline이 JSON을 감지하고 자동으로 `response` 필드를 추출. 방식 A 설정이 안 될 때 사용.

> **주의**: HTTP Request 노드 Timeout을 **반드시 120초 이상**으로 설정하세요.
> LangGraph 복잡한 분석은 5~10초 소요되며, 기본 60초면 대부분 OK이지만
> 여유를 두는 것이 좋습니다.

---

## Step 3: API 키 발급

1. Chatflow 저장 후 **Publish**
2. 왼쪽 **API Access** 클릭
3. **API Key** 생성 → 복사 (예: `app-factoryai2026`)

---

## Step 4: Pipeline + docker-compose 설정

`open-webui/docker-compose.yml`의 pipelines 서비스:
```yaml
environment:
  - DIFY_API_URL=http://host.docker.internal       # Dify 서버
  - DIFY_API_KEY=app-factoryai2026                  # Step 3에서 발급한 키
  - PIPELINES_API_KEY=factory-ai-key
```

Pipeline(`pipelines/factory_agent.py`)은 이미 Dify SSE 프록시 모드로 설정되어 있습니다.

---

## Step 5: 재시작 & 테스트

```bash
cd open-webui && docker compose down && docker compose up -d
```

Open WebUI (:3006) 에서 테스트:

| 입력 | 예상 경로 | 예상 동작 |
|------|----------|----------|
| "안녕" | 일반 대화 → LLM | 빠른 스트리밍 응답 |
| "오늘 생산 현황" | 간단한 조회 → Agent+MCP | MCP 도구 호출 후 스트리밍 |
| "불량률이 왜 높아?" | 복잡한 분석 → LangGraph | "🔍 분석 중..." → 상세 답변 |

---

## 진행 상태 표시 (Pipeline 자동 처리)

Dify SSE의 `node_started` 이벤트에 `node_type`이 포함됩니다:

```json
{"event": "node_started", "data": {"node_type": "http-request", "title": "LangGraph 분석"}}
```

Pipeline이 이를 감지하면 즉시 사용자에게:
```
> 🔍 데이터를 종합 분석하고 있습니다...
```

LLM/Agent 노드는 Dify가 토큰 단위 스트리밍 → 별도 처리 불필요.

---

## 트러블슈팅

### Dify 연결 실패
```bash
# Dify 상태 확인
curl http://localhost/v1/chat-messages -H "Authorization: Bearer app-factoryai2026"
# 403이면 API 키 확인, 연결 거부면 Dify 서버 확인
```

### MCP 도구 안 보임
```bash
# MCP 서버 상태
curl -X POST http://localhost:8501/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

### LangGraph 응답 없음
```bash
curl localhost:8500/health
# factory.db 존재 + 6테이블 확인
```

### Docker 내부에서 호스트 접근
- `host.docker.internal`이 안 되면 docker-compose.yml의 `extra_hosts` 확인
- Linux: `extra_hosts: ["host.docker.internal:host-gateway"]` 필수

---

## 부록: 2분류 Chatflow (간소 버전)

> LangGraph 없이 Dify + MCP만으로 운영하는 간단한 구성.

```
[시작] → [질문 분류기] ─┬─ 일반 대화  → [LLM 노드] ──────────────→ [끝]
                        └─ 데이터 조회 → [Agent 노드 + MCP 8개 도구] → [끝]
```

| 클래스 | 설명 | 예시 |
|--------|------|------|
| `일반 대화` | 공장과 무관한 질문 | "안녕", "MCP가 뭐야?" |
| `데이터 조회` | 생산 데이터 관련 전체 | "생산 현황", "왜 높아?", "개선 방안" |

이 구성은 LangGraph 서버(:8500)가 불필요하며 설정이 간단합니다.
복잡한 분석도 Agent가 다회 호출로 처리하지만, 3분류 대비 분석 품질이 낮을 수 있습니다.
