"""Open WebUI Pipeline — Dify Chatflow 연동.

Open WebUI → Pipeline → Dify → (간단: 직접 응답 / 복잡: LangGraph)
"""

import os
import httpx
from typing import Generator


class Pipeline:
    def __init__(self):
        self.name = "Factory AI"
        self.dify_url = os.getenv("DIFY_API_URL", "http://host.docker.internal")
        self.dify_api_key = os.getenv("DIFY_API_KEY", "")

    async def on_startup(self):
        print(f"Factory AI Pipeline started. Dify: {self.dify_url}")

    async def on_shutdown(self):
        print("Factory AI Pipeline stopped.")

    def pipe(self, user_message: str, model_id: str = "", messages: list = None, body: dict = None) -> str | Generator:
        conversation_id = body.get("chat_id", "") if body else ""

        try:
            with httpx.Client(timeout=120) as client:
                resp = client.post(
                    f"{self.dify_url}/v1/chat-messages",
                    headers={
                        "Authorization": f"Bearer {self.dify_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "inputs": {},
                        "query": user_message,
                        "response_mode": "blocking",
                        "conversation_id": conversation_id,
                        "user": "open-webui-user",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("answer", "응답을 받지 못했습니다.")
        except httpx.HTTPError as e:
            return f"Dify 서버 연결 실패: {e}"
        except Exception as e:
            return f"오류 발생: {e}"
