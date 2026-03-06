"""Open WebUI Pipeline — Dify Chatflow SSE 프록시.

Open WebUI → Pipeline → Dify Chatflow (3분류, SSE)
  ├─ 일반 대화   → Dify LLM 노드        → message (진짜 스트리밍)
  ├─ 간단한 조회 → Dify Agent + MCP 도구 → agent_message (진짜 스트리밍)
  └─ 복잡한 분석 → HTTP Request → LangGraph (:8500) → JSON → Pipeline 파싱
"""

import json
import os
from typing import Generator

import httpx


# 진행 상태 메시지: node_type → 표시 메시지
NODE_STATUS = {
    "http-request": "\n> 🔍 데이터를 종합 분석하고 있습니다...\n\n",
}


class Pipeline:
    def __init__(self):
        self.name = "Factory AI"
        self.dify_url = os.getenv("DIFY_API_URL", "http://host.docker.internal")
        self.dify_key = os.getenv("DIFY_API_KEY", "app-factoryai2026")
        # Open WebUI chat_id → Dify conversation_id 매핑
        self.conversation_map: dict[str, str] = {}

    async def on_startup(self):
        print(f"Factory AI Pipeline started. Dify: {self.dify_url}")

    async def on_shutdown(self):
        print("Factory AI Pipeline stopped.")

    def pipe(
        self,
        user_message: str,
        model_id: str = "",
        messages: list = None,
        body: dict = None,
    ) -> Generator:
        chat_id = body.get("chat_id", "") if body else ""
        # Open WebUI chat_id → Dify conversation_id 변환
        dify_conv_id = self.conversation_map.get(chat_id, "") if chat_id else ""

        payload = {
            "inputs": {},
            "query": user_message,
            "response_mode": "streaming",
            "user": "open-webui",
        }
        if dify_conv_id:
            payload["conversation_id"] = dify_conv_id

        headers = {
            "Authorization": f"Bearer {self.dify_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=120) as client:
                with client.stream(
                    "POST",
                    f"{self.dify_url}/v1/chat-messages",
                    headers=headers,
                    json=payload,
                ) as resp:
                    resp.raise_for_status()

                    buffer = ""
                    is_json = None
                    conv_id_captured = False

                    for line in resp.iter_lines():
                        if not line.startswith("data: "):
                            continue
                        raw = line[6:]
                        if not raw:
                            continue

                        try:
                            event = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        event_type = event.get("event", "")

                        # Dify conversation_id 캡처 (첫 이벤트에서)
                        if not conv_id_captured and chat_id:
                            new_conv_id = event.get("conversation_id", "")
                            if new_conv_id:
                                self.conversation_map[chat_id] = new_conv_id
                                conv_id_captured = True

                        # 복잡한 분석 경로 감지 → 진행 상태 즉시 표시
                        if event_type == "node_started":
                            node_type = event.get("data", {}).get("node_type", "")
                            status_msg = NODE_STATUS.get(node_type)
                            if status_msg:
                                yield status_msg

                        # LLM / Agent 토큰 스트리밍
                        elif event_type in ("message", "agent_message"):
                            chunk = event.get("answer", "")
                            if not chunk:
                                continue
                            buffer += chunk
                            # 첫 실질 문자로 JSON 여부 판단
                            if is_json is None:
                                stripped = buffer.lstrip()
                                if stripped:
                                    is_json = stripped[0] == "{"
                            # JSON이 아니면 실시간 스트리밍
                            if is_json is False:
                                yield chunk

                        # 완료
                        elif event_type == "message_end":
                            break

                        # 에러
                        elif event_type == "error":
                            yield f"\n오류: {event.get('message', '알 수 없는 오류')}"

                    # JSON 응답 (LangGraph 경유) → response 필드 추출
                    if is_json and buffer:
                        try:
                            data = json.loads(buffer)
                            yield data.get("response", buffer)
                        except json.JSONDecodeError:
                            yield buffer

        except httpx.HTTPStatusError as e:
            yield f"Dify 응답 오류 (HTTP {e.response.status_code}): {e.response.text[:200]}"
        except httpx.ConnectError:
            yield "Dify 서버 연결 실패. Dify가 실행 중인지 확인하세요."
        except Exception as e:
            yield f"오류 발생: {e}"
