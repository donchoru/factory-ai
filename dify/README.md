# Dify Chatflow 설정 가이드

이 문서는 Dify에서 Factory AI Chatflow를 만드는 방법을 설명합니다.

**핵심 아이디어**: 간단한 질문은 Dify의 LLM이 직접 답하고, 공장 데이터 조회가 필요한 질문은 LangGraph 서버(:8500)로 보냅니다.

```
사용자 질문
    ↓
질문 분류기 (Question Classifier)
    ├─ "일반 대화"  →  LLM 노드  →  직접 응답
    └─ "공장 조회"  →  HTTP Request (:8500)  →  LangGraph  →  응답
```

---

## 사전 준비

1. **Dify 실행 중** (Docker 또는 클라우드)
2. **LangGraph 서버 실행 중**: `cd /workspace/factory-ai && python server.py` (:8500)
3. **factory.db 생성 완료**: `python -m db.seed`

---

## Step 1: Custom Tool 등록

1. Dify 대시보드 → **Tools** → **Custom** → **Create Custom Tool**
2. `openapi.yaml` 내용을 복사하여 붙여넣기
3. **Server URL** 설정:
   - Dify가 Docker 안에 있으면: `http://host.docker.internal:8500`
   - Dify가 로컬이면: `http://localhost:8500`
4. **Test Connection** → `/health` 엔드포인트로 확인

---

## Step 2: Chatflow 만들기

### 2-1. Chatflow 생성

1. Dify 대시보드 → **Create App** → **Chatflow** 선택
2. 이름: `Factory AI`

### 2-2. 노드 구성

완성된 Chatflow는 이런 모양입니다:

```
[시작] → [질문 분류기] ─┬─ 일반 대화 → [LLM: 일반 응답] → [끝]
                        │
                        └─ 공장 조회 → [HTTP Request] → [끝]
```

#### 노드 1: 질문 분류기 (Question Classifier)

**타입**: Question Classifier

**모델**: Gemini 2.0 Flash (또는 아무 LLM)

**클래스 2개**:

| 클래스 | 설명 | 예시 |
|--------|------|------|
| `일반 대화` | 공장과 무관한 일반 질문 | "안녕", "오늘 날씨", "MCP가 뭐야?" |
| `공장 데이터 조회` | 생산/불량/정지/라인/차종 관련 | "이번 달 생산 현황", "3라인 불량률" |

#### 노드 2-A: LLM (일반 대화 경로)

**타입**: LLM

**모델**: Gemini 2.0 Flash

**시스템 프롬프트**:
```
당신은 자동차 공장 생산 관리 어시스턴트입니다.
공장과 무관한 질문에는 간단히 답하세요.
생산 관련 질문을 할 수 있다고 안내해주세요.

안내 예시:
- 생산 현황, 불량 통계, 라인 상태 등을 질문해보세요.
- "이번 달 생산 현황", "3라인 불량률" 같은 질문이 가능합니다.
```

**입력 변수**: `{{#sys.query#}}`

#### 노드 2-B: HTTP Request (공장 조회 경로)

**타입**: HTTP Request

**설정**:
- **Method**: `POST`
- **URL**: `http://host.docker.internal:8500/chat`
- **Headers**: `Content-Type: application/json`
- **Body**:
```json
{
  "message": "{{#sys.query#}}",
  "session_id": "{{#sys.conversation_id#}}"
}
```

#### 노드 3: 끝 (End)

- 일반 대화 경로: LLM 출력을 그대로 반환
- 공장 조회 경로: HTTP Response에서 `response` 필드를 출력 변수로 설정

### 2-3. 엣지 연결

```
시작 → 질문 분류기
질문 분류기 → (일반 대화) → LLM → 끝
질문 분류기 → (공장 데이터 조회) → HTTP Request → 끝
```

---

## Step 3: 테스트

Chatflow 우측 상단 **Preview** 버튼으로 테스트합니다.

### 일반 대화 (Dify가 직접 답함)

```
사용자: 안녕하세요!
AI: 안녕하세요! 자동차 공장 생산 관리 어시스턴트입니다.
    생산 현황, 불량 통계, 라인 상태 등을 질문해보세요.
```

### 공장 데이터 조회 (LangGraph로 라우팅)

```
사용자: 이번 달 생산 현황 알려줘
AI: 📊 2026년 2월 생산 현황입니다.
    | 라인 | 목표 | 실적 | 달성률 | 불량률 |
    | ... | ... | ... | ... | ... |
```

### 테스트 질문 모음

| 질문 | 기대 경로 | 기대 의도 |
|------|----------|----------|
| 안녕하세요 | 일반 대화 | - |
| MCP가 뭐야? | 일반 대화 | - |
| 오늘 생산 현황 | 공장 조회 | production_query |
| 이번 달 소나타 몇 대? | 공장 조회 | production_query |
| 3라인 불량률 | 공장 조회 | defect_query |
| 어제 라인 정지 이력 | 공장 조회 | downtime_query |
| 교대별 생산량 비교 | 공장 조회 | trend_analysis |
| 어떤 라인이 제일 잘 돌아가? | 공장 조회 | line_status |

---

## Step 4: API 키 발급 (Open WebUI 연동용)

1. Chatflow 상단 **Publish** 클릭
2. 좌측 메뉴 **API Access** 클릭
3. **API Key** 생성 → `app-xxxxxxxxxxxx` 형태의 키 복사
4. 이 키를 Open WebUI Pipeline의 `DIFY_API_KEY` 환경변수에 설정

---

## 고급: 3분류 Chatflow

더 정교하게 3개 경로로 나눌 수도 있습니다:

```
[질문 분류기] ─┬─ 일반 대화   → LLM 직접 응답
              ├─ 간단 조회   → HTTP Request (:8500)
              └─ 심층 분석   → HTTP Request (:8500) + LLM 후처리
```

| 클래스 | 예시 | 처리 |
|--------|------|------|
| 일반 대화 | "안녕", "뭐 할 수 있어?" | Dify LLM |
| 간단 조회 | "오늘 생산 현황", "라인 상태" | LangGraph 응답 그대로 |
| 심층 분석 | "불량률이 왜 높아?", "개선 방안은?" | LangGraph 응답 + Dify LLM이 추가 분석 |

심층 분석 경로에서는 LangGraph 응답을 받은 뒤, Dify의 LLM 노드가 "이 데이터를 바탕으로 개선 방안을 제시하세요" 같은 추가 프롬프트로 한 번 더 처리합니다.
