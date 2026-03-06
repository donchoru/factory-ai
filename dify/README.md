# Dify Chatflow 설정 가이드 (선택)

> **현재 기본 구성은 Pipeline → LangGraph 직접 SSE 연동입니다.**
> Dify를 추가하면 질문 분류(일반/조회/분석)를 Dify가 처리합니다.

---

## 사전 준비

1. **Dify 실행 중** (Docker 또는 클라우드)
2. **MCP 서버**: `python mcp_server.py` (:8501)
3. **factory.db 생성**: `python -m db.seed` (최초 1회)
4. **LangGraph 서버** (3분류만): `python server.py` (:8500)

---

## MCP 서버 연결

1. Dify 대시보드 → **Tools** → **MCP**
2. **Add MCP Server** 클릭
3. 설정:
   - **Name**: `Factory AI`
   - **URL**: `http://host.docker.internal:8501/mcp`
4. **Save** → 8개 도구 자동 인식

---

## 구성 1: 2분류 Chatflow

> Dify가 **일반 대화 vs 데이터 조회**를 분류. LangGraph 불필요.

```
[시작] → [질문 분류기] ─┬─ 일반 대화  → [LLM 노드] ──────────────→ [끝]
                        └─ 데이터 조회 → [Agent 노드 + MCP 8개 도구] → [끝]
```

### 질문 분류기

| 클래스 | 설명 | 예시 |
|--------|------|------|
| `일반 대화` | 공장과 무관한 질문 | "안녕", "MCP가 뭐야?" |
| `데이터 조회` | 생산 데이터 관련 | "생산 현황", "왜 높아?", "개선 방안" |

### Agent 노드 시스템 프롬프트

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

## 구성 2: 3분류 Chatflow

> Dify가 **3가지로 분류**. 복잡한 질문은 LangGraph가 멀티스텝 추론.

```
[시작] → [질문 분류기] ─┬─ 일반 대화   → [LLM 노드] ──────────────→ [끝]
                        ├─ 간단한 조회 → [Agent 노드 + MCP 도구] ──→ [끝]
                        └─ 복잡한 분석 → [HTTP Request :8500] ────→ [끝]
```

### 추가 설정: Custom Tool 등록

1. Dify → **Tools** → **Custom** → **Create Custom Tool**
2. `dify/openapi.yaml` 내용 붙여넣기
3. Server URL: `http://host.docker.internal:8500`

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

**출력**: HTTP Response의 `response` 필드를 End 노드에 연결.

---

## Pipeline 전환

Dify를 사용하려면 Pipeline을 Dify 프록시 모드로 변경해야 합니다.

`open-webui/docker-compose.yml`에서:
```yaml
environment:
  - DIFY_API_URL=http://host.docker.internal    # Dify 서버
  - DIFY_API_KEY=app-xxxxxxxxxxxx               # Dify API 키
```

Pipeline 코드(`pipelines/factory_agent.py`)도 Dify SSE 파싱으로 변경 필요.

---

## 2분류 vs 3분류

| | 2분류 | 3분류 |
|---|---|---|
| 클래스 | 일반 / 데이터 | 일반 / 간단 / 복잡 |
| 복잡한 질문 | Agent 다회 호출 | LangGraph 멀티에이전트 |
| 추가 서버 | 불필요 | LangGraph :8500 |
| 장점 | 설정 간단 | 분석 품질 우수 |
