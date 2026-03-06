"""정보조회 Agent — 의도 기반으로 Tool 호출 후 응답 생성."""
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from agents.state import AgentState, dump_state
from agents.prompts import INFO_SYSTEM_PROMPT
from agents.message_trimmer import prepare_messages
from tools.factory_tools import ALL_TOOLS
from config import GEMINI_API_KEY, GEMINI_MODEL

MAX_TOOL_ROUNDS = 3

llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,
    google_api_key=GEMINI_API_KEY,
    temperature=0,
).bind_tools(ALL_TOOLS)


def info_node(state: AgentState) -> dict:
    intent = state["intent"]
    intent_detail = state["intent_detail"]
    user_input = state["user_input"]
    messages = state.get("messages", [])
    tool_call_round = state.get("tool_call_round", 0)

    reentry = bool(messages)
    round_label = f" (Round {tool_call_round})" if reentry else ""
    step_label = f"InfoAgent 재진입 (Tool 결과 수신){round_label}" if reentry else "InfoAgent (정보조회)"

    trace = [
        f"\n---\n## Step 2: {step_label}",
        f"### State BEFORE",
    ]
    trace += dump_state(state)

    if reentry:
        trimmed = prepare_messages(list(messages))

        if tool_call_round < MAX_TOOL_ROUNDS:
            guide_msg = HumanMessage(content=(
                "도구 실행 결과를 분석하세요. "
                "사용자의 질문에 완전히 답하기 위해 추가 조회가 필요하면 도구를 더 호출하고, "
                "충분한 정보가 모였으면 최종 응답을 생성하세요."
            ))
        else:
            guide_msg = HumanMessage(content=(
                "더 이상 도구를 호출하지 말고 현재까지의 결과로 최종 응답을 생성하세요."
            ))

        llm_messages = [SystemMessage(content=INFO_SYSTEM_PROMPT)] + trimmed + [guide_msg]
        trim_note = (f"원본 {len(messages)}건 → 트리밍 {len(trimmed)}건"
                     if len(trimmed) < len(messages)
                     else f"메시지 히스토리 {len(messages)}건 포함")
        trace += [
            f"### 🔷 FM 입력 (→ Gemini {GEMINI_MODEL}, 재진입 Round {tool_call_round})",
            f"- **System**: INFO_SYSTEM_PROMPT ({len(INFO_SYSTEM_PROMPT)}자)",
            f"- **Messages**: {trim_note}",
            f"- **Guide**: \"{guide_msg.content}\"",
        ]
        for m in trimmed[-3:]:
            role = type(m).__name__
            content_preview = str(getattr(m, 'content', ''))[:200]
            trace.append(f"  - `{role}`: {content_preview}")
    else:
        history = state.get("conversation_history", [])
        history_ctx = ""
        if history:
            ctx_lines = ["[이전 대화 이력]"]
            for h in history[-3:]:
                ctx_lines.append(f"- Q: {h['user']} → intent: {h.get('intent', '')}, 응답: {h.get('answer', '')[:200]}")
            history_ctx = "\n".join(ctx_lines) + "\n\n"

        prompt = (
            f"{history_ctx}"
            f"사용자 질문: {user_input}\n"
            f"의도: {intent}\n"
            f"상세: {intent_detail}\n\n"
            f"위 의도에 맞는 도구를 호출하여 정보를 조회하세요."
        )
        llm_messages = [
            SystemMessage(content=INFO_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
        trace += [
            f"### 🔷 FM 입력 (→ Gemini {GEMINI_MODEL}, 첫 호출)",
            f"- **System**: INFO_SYSTEM_PROMPT ({len(INFO_SYSTEM_PROMPT)}자)",
            f"- **Human**:",
            f"```",
            f"{prompt}",
            f"```",
        ]

    try:
        response = llm.invoke(llm_messages)
    except Exception as e:
        error_msg = f"LLM 호출 실패: {type(e).__name__}: {e}"
        trace.append(f"### ERROR\n- `{error_msg}`")
        fallback = AIMessage(content="죄송합니다. 정보 조회 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
        return {
            "messages": [fallback],
            "trace_log": state.get("trace_log", []) + trace,
        }

    result = {
        "messages": [response],
        "trace_log": state.get("trace_log", []) + trace,
    }

    if response.tool_calls:
        trace += [
            f"### 🔶 FM 출력 (← Gemini) → Tool 호출 요청 (Round {tool_call_round + 1})",
        ]
        for tc in response.tool_calls:
            trace.append(f"- `{tc['name']}({tc['args']})`")
        trace.append(f"### 다음: ToolNode로 이동")
        result["tool_call_round"] = tool_call_round + 1
    else:
        trace += [
            f"### 🔶 FM 출력 (← Gemini) → 텍스트 응답",
            f"```",
            f"{response.content[:500]}",
            f"```",
            f"### 다음: ResponseAgent로 이동",
        ]

    updated = dict(state)
    updated_msgs = list(state.get("messages", [])) + [response]
    updated["messages"] = updated_msgs
    trace += [f"### State AFTER"]
    trace += dump_state(updated)

    result["trace_log"] = state.get("trace_log", []) + trace
    return result


def respond_node(state: AgentState) -> dict:
    intent = state["intent"]
    messages = state["messages"]
    user_input = state["user_input"]

    step_num = "2" if intent == "general_chat" else "3"
    trace = [
        f"\n---\n## Step {step_num}: ResponseAgent (응답생성)",
        f"### State BEFORE",
    ]
    trace += dump_state(state)

    if intent == "general_chat":
        chat_system = "당신은 친절한 자동차 공장 생산 관리 어시스턴트입니다. 공장과 무관한 질문에는 간단히 답하고, 생산 관련 질문을 유도하세요."
        simple_llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            google_api_key=GEMINI_API_KEY,
            temperature=0.7,
        )
        response = simple_llm.invoke([
            SystemMessage(content=chat_system),
            HumanMessage(content=user_input),
        ])
        answer = response.content
        trace += [
            f"### 🔷 FM 입력 (→ Gemini {GEMINI_MODEL}, 일반대화)",
            f"- **System**: \"{chat_system[:80]}...\" ({len(chat_system)}자)",
            f"- **Human**: \"{user_input}\"",
            f"### 🔶 FM 출력 (← Gemini)",
            f"```",
            f"{answer}",
            f"```",
        ]
    else:
        last_ai = None
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and not msg.tool_calls:
                last_ai = msg
                break

        if last_ai and last_ai.content:
            answer = last_ai.content
        else:
            answer = "조회 결과를 처리하지 못했습니다. 다시 시도해주세요."
        trace.append(f"### 처리: InfoAgent 재진입에서 생성된 최종 AI 응답 추출")

    trace += [
        f"### 최종 응답 (final_answer)",
        f"```\n{answer}\n```",
    ]

    updated = dict(state)
    updated["final_answer"] = answer
    trace += [f"### State AFTER"]
    trace += dump_state(updated)

    return {
        "final_answer": answer,
        "trace_log": state.get("trace_log", []) + trace,
    }
