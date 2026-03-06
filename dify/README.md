# Dify 연동 가이드

## 1. Custom Tool 등록

1. Dify 대시보드 → **Tools** → **Custom** → **Create Custom Tool**
2. **Import from URL** 또는 직접 붙여넣기:
   - `openapi.yaml` 내용 복사하여 붙여넣기
3. **Server URL** 설정:
   - Dify가 Docker 내부: `http://host.docker.internal:8500`
   - Dify가 로컬: `http://localhost:8500`
4. **Test Connection** → `/health` 엔드포인트 확인

## 2. Chatflow 구성

```
시작 → LLM 노드 (선택사항) → HTTP Request → 끝
```

### 간단 구성 (HTTP Request만)

1. **Chatflow** 생성
2. **HTTP Request** 노드 추가:
   - Method: `POST`
   - URL: `http://host.docker.internal:8500/chat`
   - Body:
     ```json
     {
       "message": "{{#sys.query#}}",
       "session_id": "{{#sys.conversation_id#}}"
     }
     ```
   - Headers: `Content-Type: application/json`
3. **End** 노드에서 HTTP Response의 `response` 필드 출력

### 고급 구성 (LLM + Tool)

1. **Chatflow** 생성
2. **LLM** 노드: Gemini/GPT로 1차 의도 파악 (선택)
3. **Tool** 노드: `chatWithFactoryAI` 도구 호출
4. **LLM** 노드: Tool 결과를 정리하여 최종 응답 생성

## 3. 테스트 질문 예시

| 질문 | 예상 의도 |
|------|----------|
| 오늘 생산 현황 | production_query |
| 이번 달 소나타 몇 대? | production_query |
| 3라인 불량률 | defect_query |
| 어제 라인 정지 이력 | downtime_query |
| 교대별 생산량 비교 | trend_analysis |
| 어떤 라인이 제일 잘 돌아가? | line_status |

## 4. 사전 요구사항

- Factory AI 서버 실행: `cd /workspace/factory-ai && python server.py`
- DB 시드: `python -m db.seed` (최초 1회)
