"""Open WebUI Pipeline — Factory AI 연동."""
import os
import json
import httpx
from typing import Generator


class Pipeline:
    def __init__(self):
        self.name = "Factory AI"
        self.factory_url = os.getenv("FACTORY_AI_URL", "http://host.docker.internal:8500")

    async def on_startup(self):
        print(f"Factory AI Pipeline started. Backend: {self.factory_url}")

    async def on_shutdown(self):
        print("Factory AI Pipeline stopped.")

    def pipe(self, user_message: str, model_id: str = "", messages: list = None, body: dict = None) -> str | Generator:
        session_id = body.get("chat_id", "default") if body else "default"

        try:
            with httpx.Client(timeout=60) as client:
                resp = client.post(
                    f"{self.factory_url}/chat",
                    json={"message": user_message, "session_id": session_id},
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("response", "응답을 받지 못했습니다.")
        except httpx.HTTPError as e:
            return f"Factory AI 서버 연결 실패: {e}"
        except Exception as e:
            return f"오류 발생: {e}"
