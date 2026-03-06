"""Open WebUI Pipeline — LangGraph 직접 SSE 스트리밍.

Open WebUI → Pipeline → LangGraph (:8500/chat/stream) → SSE 스트리밍
"""

import json
import os
from typing import Generator

import httpx


class Pipeline:
    def __init__(self):
        self.name = "Factory AI"
        self.langgraph_url = os.getenv(
            "LANGGRAPH_URL", "http://host.docker.internal:8500"
        )

    async def on_startup(self):
        print(f"Factory AI Pipeline started. LangGraph: {self.langgraph_url}")

    async def on_shutdown(self):
        print("Factory AI Pipeline stopped.")

    def pipe(self, user_message: str, model_id: str = "", messages: list = None, body: dict = None) -> Generator:
        session_id = body.get("chat_id", "default") if body else "default"

        try:
            with httpx.Client(timeout=120) as client:
                with client.stream(
                    "POST",
                    f"{self.langgraph_url}/chat/stream",
                    headers={"Content-Type": "application/json"},
                    json={
                        "message": user_message,
                        "session_id": session_id,
                    },
                ) as resp:
                    resp.raise_for_status()
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
                        if event.get("event") == "message":
                            chunk = event.get("answer", "")
                            if chunk:
                                yield chunk
                        elif event.get("event") == "done":
                            break
                        elif event.get("event") == "error":
                            yield f"\n\n오류: {event.get('message', '')}"
        except httpx.HTTPError as e:
            yield f"서버 연결 실패: {e}"
        except Exception as e:
            yield f"오류 발생: {e}"
