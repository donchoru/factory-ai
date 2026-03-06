"""FastAPI 서버 — LangGraph 멀티에이전트 + SSE 스트리밍."""

import asyncio
import json
import time
from collections import defaultdict
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import SERVER_PORT, TRACES_DIR
from db.connection import query
from graph.workflow import build_graph

app = FastAPI(title="Factory AI", version="1.0.0")
graph = build_graph()

sessions: dict[str, list[dict]] = defaultdict(list)
MAX_HISTORY = 10


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    response: str
    intent: str
    session_id: str
    trace: list[str] | None = None


def _build_state(message: str, history: list[dict]) -> dict:
    return {
        "messages": [],
        "user_input": message,
        "intent": "",
        "intent_detail": "",
        "trace_log": [],
        "final_answer": "",
        "conversation_history": history[-MAX_HISTORY:],
        "tool_call_round": 0,
    }


def _save_history(
    history: list[dict], session_id: str, message: str, answer: str, intent: str,
) -> None:
    history.append({"user": message, "answer": answer[:500], "intent": intent})
    if len(history) > MAX_HISTORY:
        sessions[session_id] = history[-MAX_HISTORY:]


def _save_trace(user_input: str, intent: str, trace_lines: list[str]) -> str:
    """트레이스 로그를 Markdown 파일로 저장. 파일명 반환."""
    TRACES_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = TRACES_DIR / f"trace_{ts}.md"

    header = [
        "# Agent Trace Log",
        f"- **시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **사용자 입력**: {user_input}",
        f"- **최종 의도**: {intent}",
        "",
        "---",
    ]

    path.write_text("\n".join(header + trace_lines), encoding="utf-8")
    return path.name


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """JSON 응답 — Dify Custom Tool / 직접 API 호출용."""
    history = sessions[req.session_id]
    state = _build_state(req.message, history)

    start = time.time()
    result = graph.invoke(state)
    elapsed = time.time() - start

    answer = result.get("final_answer", "응답 생성 실패")
    intent = result.get("intent", "unknown")
    _save_history(history, req.session_id, req.message, answer, intent)

    trace = result.get("trace_log", [])
    trace.append(f"\n---\n## 처리 시간: {elapsed:.2f}초")

    # 트레이스 파일 저장
    _save_trace(req.message, intent, trace)

    return ChatResponse(
        response=answer, intent=intent, session_id=req.session_id, trace=trace,
    )


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """SSE 스트리밍 — Open WebUI Pipeline 직접 연동."""
    history = sessions[req.session_id]
    state = _build_state(req.message, history)

    async def generate():
        start = time.time()
        result = await asyncio.to_thread(graph.invoke, state)
        elapsed = time.time() - start

        answer = result.get("final_answer", "응답 생성 실패")
        intent = result.get("intent", "unknown")
        _save_history(history, req.session_id, req.message, answer, intent)

        # 트레이스 파일 저장
        trace = result.get("trace_log", [])
        trace.append(f"\n---\n## 처리 시간: {elapsed:.2f}초")
        _save_trace(req.message, intent, trace)

        for i in range(0, len(answer), 4):
            chunk = answer[i : i + 4]
            data = json.dumps(
                {"event": "message", "answer": chunk}, ensure_ascii=False,
            )
            yield f"data: {data}\n\n"
            await asyncio.sleep(0.02)

        done = json.dumps(
            {"event": "done", "intent": intent, "elapsed": f"{elapsed:.2f}s"},
            ensure_ascii=False,
        )
        yield f"data: {done}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/health")
async def health():
    tables = [
        "production_lines", "models", "shifts",
        "daily_production", "defects", "downtime",
    ]
    stats = {}
    for table in tables:
        rows = query(f"SELECT COUNT(*) as cnt FROM {table}")
        stats[table] = rows[0]["cnt"]
    return {"status": "ok", "db_stats": stats}


@app.post("/reset")
async def reset(session_id: str = "default"):
    if session_id in sessions:
        del sessions[session_id]
    return {"status": "ok", "session_id": session_id}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)
