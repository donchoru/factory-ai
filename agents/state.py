from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, ToolMessage


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    intent: str
    intent_detail: str
    trace_log: list[str]
    user_input: str
    final_answer: str
    conversation_history: list[dict]
    tool_call_round: int


def _fmt_message(msg: BaseMessage) -> str:
    if isinstance(msg, HumanMessage):
        tag = "HumanMessage"
    elif isinstance(msg, AIMessage):
        tag = "AIMessage"
        if msg.tool_calls:
            calls = ", ".join(f"{tc['name']}({tc['args']})" for tc in msg.tool_calls)
            return f"  - **{tag}** [tool_calls]: `{calls}`"
        content = msg.content[:300] + ("..." if len(msg.content) > 300 else "")
        return f"  - **{tag}**: {content}"
    elif isinstance(msg, ToolMessage):
        tag = "ToolMessage"
        content = msg.content[:300] + ("..." if len(msg.content) > 300 else "")
        return f"  - **{tag}** (tool=`{msg.name}`): `{content}`"
    else:
        tag = type(msg).__name__
    content = msg.content[:300] + ("..." if len(msg.content) > 300 else "")
    return f"  - **{tag}**: {content}"


def dump_state(state: AgentState) -> list[str]:
    history = state.get("conversation_history", [])
    lines = [
        "### State Snapshot",
        f"- **user_input**: `{state.get('user_input', '')}`",
        f"- **intent**: `{state.get('intent', '')}`",
        f"- **intent_detail**: `{state.get('intent_detail', '')}`",
        f"- **final_answer**: `{(state.get('final_answer', '') or '')[:200]}`",
        f"- **conversation_history** ({len(history)}턴):",
    ]
    for h in history[-3:]:
        lines.append(f"  - Q: `{h.get('user', '')}` → A: `{h.get('answer', '')[:80]}...` ({h.get('intent', '')})")
    lines.append(f"- **messages** ({len(state.get('messages', []))}건):")
    for msg in state.get("messages", []):
        lines.append(_fmt_message(msg))
    return lines
