"""FastAPI 서버 — Dify/Open WebUI 연동용."""
import time
from collections import defaultdict
from fastapi import FastAPI
from pydantic import BaseModel
from graph.workflow import build_graph
from db.connection import query
from config import SERVER_PORT

app = FastAPI(title="Factory AI", version="1.0.0")
graph = build_graph()

# 인메모리 세션 저장소
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


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    history = sessions[req.session_id]

    state = {
        "messages": [],
        "user_input": req.message,
        "intent": "",
        "intent_detail": "",
        "trace_log": [],
        "final_answer": "",
        "conversation_history": history[-MAX_HISTORY:],
        "tool_call_round": 0,
    }

    start = time.time()
    result = graph.invoke(state)
    elapsed = time.time() - start

    answer = result.get("final_answer", "응답 생성 실패")
    intent = result.get("intent", "unknown")

    # 이력 저장
    history.append({
        "user": req.message,
        "answer": answer[:500],
        "intent": intent,
    })
    if len(history) > MAX_HISTORY:
        sessions[req.session_id] = history[-MAX_HISTORY:]

    trace = result.get("trace_log", [])
    trace.append(f"\n---\n## 처리 시간: {elapsed:.2f}초")

    return ChatResponse(
        response=answer,
        intent=intent,
        session_id=req.session_id,
        trace=trace,
    )


@app.get("/health")
async def health():
    stats = {}
    for table in ["production_lines", "models", "shifts", "daily_production", "defects", "downtime"]:
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
