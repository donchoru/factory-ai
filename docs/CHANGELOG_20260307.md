# 2026-03-07 개선 사항 — Dify 질문 분류 + Pipeline 진행 표시 + 도구 필터

## 요약

| 변경 | 파일 | 효과 |
|------|------|------|
| Dify Chatflow에 IF/ELSE 질문 분류기 추가 | Dify UI (API로 수정) | "안녕" 같은 일반 대화는 LangGraph를 거치지 않음 |
| Pipeline에 분석 중 진행 표시 추가 | `open-webui/pipelines/factory_agent.py` | 3초마다 ` ·` 표시 → 사용자가 진행 상태 인지 |
| get_production_summary에 line/model 필터 추가 | `tools/factory_tools.py` | "LINE-1 현황"에 LINE-1만 응답 |
| Open WebUI 신규 유저 자동 활성화 | `open-webui/docker-compose.yml` | 외부 접속 시 회원가입 후 바로 사용 가능 |

---

## 1. Dify Chatflow — IF/ELSE 질문 분류기

### 변경 전
```
시작 → HTTP Request (LangGraph) → 응답
```
**모든 질문**이 LangGraph로 전달 → "안녕"에도 "🔍 분석 중..." 표시 (2~3초 소요)

### 변경 후
```
시작 → IF/ELSE (키워드 분류) ─┬─ 공장 키워드 → HTTP Request (LangGraph) → 분석 응답
                              └─ ELSE       → 일반 응답 (즉시)
```

### 분류 키워드 (25개)
`생산`, `불량`, `달성률`, `라인`, `정지`, `교대`, `추이`, `차종`, `실적`, `공장`, `수율`,
`LINE`, `SUV`, `EV`, `세단`, `소나타`, `투싼`, `아이오닉`, `분석`, `현황`, `오늘`, `이번`,
`설비`, `야간`, `주간`

### 동작
- **키워드 포함** → `http_request_1` (LangGraph) → `answer_factory` (분석 결과)
- **키워드 미포함** → `answer_general` (안내 메시지 즉시 응답)

### 수정 방법
Dify Console API를 통해 Chatflow 워크플로우를 직접 업데이트:
```bash
# 1. 로그인 (password는 base64 인코딩)
curl -c cookies -X POST http://localhost/console/api/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@factory.ai","password":"ZmFjdG9yeTIwMjY="}'

# 2. 워크플로우 draft 업데이트
curl -b cookies -H "X-CSRF-Token: <csrf>" \
  -X POST http://localhost/console/api/apps/<app_id>/workflows/draft \
  -H "Content-Type: application/json" \
  -d '{"graph": <new_graph>, "features": <features>, "hash": "<current_hash>"}'

# 3. 퍼블리시
curl -b cookies -H "X-CSRF-Token: <csrf>" \
  -X POST http://localhost/console/api/apps/<app_id>/workflows/publish \
  -H "Content-Type: application/json" -d '{}'
```

---

## 2. Pipeline — 분석 중 진행 표시 (쓰레드 기반)

### 변경 전
- `node_started(http-request)` 감지 시 "🔍 분석 중..." 한 번 표시
- 이후 LangGraph 응답까지 **아무 표시 없음** (5~15초 무응답)

### 변경 후
- 쓰레드 기반 큐 패턴으로 변경
- SSE 리더가 백그라운드 쓰레드에서 Dify 이벤트를 읽어 큐에 넣음
- 메인 제너레이터는 큐에서 읽되, **3초간 데이터 없으면 ` ·` 진행 표시** 출력
- `node_finished(http-request)` 감지 시 진행 표시 중단

### 핵심 코드
```python
# 백그라운드: Dify SSE → 큐
def sse_reader():
    for line in resp.iter_lines():
        if event_type == "node_started" and node_type == "http-request":
            analyzing.set()      # 분석 시작 플래그
            result_queue.put(status_msg)
        elif event_type == "node_finished" and node_type == "http-request":
            analyzing.clear()    # 분석 종료 플래그

# 메인: 큐 → yield (진행 표시 포함)
while not stop_event.is_set():
    try:
        item = result_queue.get(timeout=3)  # 3초 대기
        yield item
    except queue.Empty:
        if analyzing.is_set():
            yield " ·"  # 진행 표시
```

### 사용자 경험
```
🔍 데이터를 종합 분석하고 있습니다...
 · · ·
[분석 결과 표시]
```

---

## 3. get_production_summary — line/model 필터 추가

### 변경 전
```python
def get_production_summary(period: str = "this_month") -> str:
```
- `period`만 필터 가능
- "이번 주 LINE-1 생산 현황" → **전체 라인 데이터 반환**

### 변경 후
```python
def get_production_summary(
    period: str = "this_month",
    line: str = "",
    model: str = "",
) -> str:
```
- `line`, `model` 필터 추가
- "이번 주 LINE-1 생산 현황" → **LINE-1 데이터만 반환**

### SQL 변경
```sql
-- 변경 전
WHERE production_date >= '2026-02-23' AND production_date <= '2026-02-28'

-- 변경 후 (line='LINE-1' 일 때)
WHERE production_date >= '2026-02-23' AND production_date <= '2026-02-28'
  AND p.line_id = 'LINE-1'
```

---

## 4. Open WebUI — 신규 유저 자동 활성화

### 변경 (`docker-compose.yml`)
```yaml
environment:
  - DEFAULT_USER_ROLE=user      # 신규 가입자 → 바로 user 권한
  - ENABLE_SIGNUP=true           # 회원가입 허용
```

### 이유
- Cloudflare Tunnel로 외부 접속 시 (`factory.latebloomerdev.kr`)
- 새 계정 가입하면 기본 `pending` 상태 → 관리자 승인 필요했음
- `DEFAULT_USER_ROLE=user`로 바로 사용 가능하도록 변경

---

## 외부 접속 설정 (Cloudflare Tunnel)

`~/.cloudflared/config.yml`에 추가:
```yaml
- hostname: factory.latebloomerdev.kr
  service: http://127.0.0.1:3006
- hostname: dify.latebloomerdev.kr
  service: http://127.0.0.1:80
```

**주의**: Cloudflare Dashboard에서 원격 관리되는 터널은 로컬 config 변경이 무시됨.
→ Cloudflare Zero Trust Dashboard > Networks > Tunnels > Public Hostname에서 직접 추가.
→ Service Type은 반드시 **HTTP** (HTTPS 아님).
