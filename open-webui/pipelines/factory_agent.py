"""Open WebUI Pipeline — Dify Chatflow SSE 프록시.

Open WebUI → Pipeline → Dify Chatflow (질문 분류, SSE)
  ├─ 일반 대화   → IF/ELSE → 즉시 응답 (빠름)
  └─ 공장 질문   → IF/ELSE → HTTP Request → LangGraph (:8500) → JSON → Pipeline 파싱
"""

import json
import os
import queue
import threading
from typing import Generator

import httpx


# 진행 상태 메시지: node_type → 표시 메시지
NODE_STATUS = {
    "http-request": "\n> 🔍 데이터를 종합 분석하고 있습니다...\n\n",
}

# 분석 중 진행 표시 (3초마다)
PROGRESS_DOTS = " ·"
PROGRESS_INTERVAL = 3  # 초


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

        # 큐 기반 스트리밍: SSE 리더 쓰레드 + 진행 표시
        result_queue = queue.Queue()
        stop_event = threading.Event()
        analyzing = threading.Event()  # HTTP Request 진행 중 플래그

        def sse_reader():
            """Dify SSE를 읽어 큐에 넣는 백그라운드 쓰레드."""
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
                            if stop_event.is_set():
                                break
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

                            # Dify conversation_id 캡처
                            if not conv_id_captured and chat_id:
                                new_conv_id = event.get("conversation_id", "")
                                if new_conv_id:
                                    self.conversation_map[chat_id] = new_conv_id
                                    conv_id_captured = True

                            # 복잡한 분석 경로 감지
                            if event_type == "node_started":
                                node_type = event.get("data", {}).get("node_type", "")
                                status_msg = NODE_STATUS.get(node_type)
                                if status_msg:
                                    analyzing.set()
                                    result_queue.put(status_msg)

                            elif event_type == "node_finished":
                                node_type = event.get("data", {}).get("node_type", "")
                                if node_type == "http-request":
                                    analyzing.clear()

                            # LLM / Agent 토큰 스트리밍
                            elif event_type in ("message", "agent_message"):
                                chunk = event.get("answer", "")
                                if not chunk:
                                    continue
                                buffer += chunk
                                if is_json is None:
                                    stripped = buffer.lstrip()
                                    if stripped:
                                        is_json = stripped[0] == "{"
                                if is_json is False:
                                    result_queue.put(chunk)

                            elif event_type == "message_end":
                                break

                            elif event_type == "error":
                                result_queue.put(
                                    f"\n오류: {event.get('message', '알 수 없는 오류')}"
                                )

                        # JSON 응답 (LangGraph) → response 추출
                        if is_json and buffer:
                            try:
                                data = json.loads(buffer)
                                result_queue.put(data.get("response", buffer))
                            except json.JSONDecodeError:
                                result_queue.put(buffer)

            except httpx.HTTPStatusError as e:
                result_queue.put(
                    f"Dify 응답 오류 (HTTP {e.response.status_code}): {e.response.text[:200]}"
                )
            except httpx.ConnectError:
                result_queue.put("Dify 서버 연결 실패. Dify가 실행 중인지 확인하세요.")
            except Exception as e:
                result_queue.put(f"오류 발생: {e}")
            finally:
                stop_event.set()

        # SSE 리더 쓰레드 시작
        reader_thread = threading.Thread(target=sse_reader, daemon=True)
        reader_thread.start()

        # 메인 제너레이터: 큐에서 읽기 + 분석 중이면 진행 표시
        dot_count = 0
        try:
            while not stop_event.is_set() or not result_queue.empty():
                try:
                    item = result_queue.get(timeout=PROGRESS_INTERVAL)
                    dot_count = 0  # 새 데이터 오면 카운터 리셋
                    yield item
                except queue.Empty:
                    # 분석 중이면 진행 표시
                    if analyzing.is_set():
                        dot_count += 1
                        yield PROGRESS_DOTS
        finally:
            stop_event.set()
            reader_thread.join(timeout=5)
