"""메시지 히스토리 토큰 관리 — ToolMessage 비대화 방지.

전략:
  1. ToolMessage 개별 트리밍: 결과가 MAX_TOOL_RESULT_CHARS를 넘으면 잘라냄
  2. 히스토리 윈도우: messages가 MAX_MESSAGES를 넘으면 오래된 것부터 제거
  3. 잘린 데이터에는 "[...truncated]" 마커 추가
"""
from copy import deepcopy
from langchain_core.messages import BaseMessage, ToolMessage, AIMessage

MAX_TOOL_RESULT_CHARS = 3000
MAX_MESSAGES = 12
MAX_TOTAL_CHARS = 30000


def _estimate_chars(messages: list[BaseMessage]) -> int:
    return sum(len(getattr(m, "content", "") or "") for m in messages)


def _truncate_content(content: str, max_chars: int) -> str:
    if len(content) <= max_chars:
        return content
    truncated = content[:max_chars]
    return truncated + f"\n\n[...truncated: 원본 {len(content):,}자 중 {max_chars:,}자만 표시]"


def trim_tool_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    result = []
    for msg in messages:
        if isinstance(msg, ToolMessage) and len(msg.content or "") > MAX_TOOL_RESULT_CHARS:
            trimmed = deepcopy(msg)
            trimmed.content = _truncate_content(msg.content, MAX_TOOL_RESULT_CHARS)
            result.append(trimmed)
        else:
            result.append(msg)
    return result


def trim_history(messages: list[BaseMessage]) -> list[BaseMessage]:
    if len(messages) <= MAX_MESSAGES and _estimate_chars(messages) <= MAX_TOTAL_CHARS:
        return messages

    if len(messages) > MAX_MESSAGES:
        first_ai = None
        for i, msg in enumerate(messages):
            if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                first_ai = (i, msg)
                break

        trimmed = messages[-MAX_MESSAGES:]

        if first_ai and first_ai[1] not in trimmed:
            trimmed = [first_ai[1]] + trimmed[-(MAX_MESSAGES - 1):]

        messages = trimmed

    while _estimate_chars(messages) > MAX_TOTAL_CHARS:
        longest_idx = -1
        longest_len = 0
        for i, msg in enumerate(messages):
            if isinstance(msg, ToolMessage):
                content_len = len(msg.content or "")
                if content_len > longest_len:
                    longest_len = content_len
                    longest_idx = i

        if longest_idx == -1 or longest_len <= 500:
            break

        msg = messages[longest_idx]
        new_max = max(500, longest_len // 2)
        trimmed_msg = deepcopy(msg)
        trimmed_msg.content = _truncate_content(msg.content, new_max)
        messages = messages[:longest_idx] + [trimmed_msg] + messages[longest_idx + 1:]

    return messages


def prepare_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    trimmed = trim_tool_messages(messages)
    windowed = trim_history(trimmed)
    return windowed
