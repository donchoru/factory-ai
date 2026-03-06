"""CLI 대화 진입점 — 로컬 테스트용."""

from graph.workflow import build_graph


def _build_state(message: str, history: list[dict]) -> dict:
    return {
        "messages": [],
        "user_input": message,
        "intent": "",
        "intent_detail": "",
        "trace_log": [],
        "final_answer": "",
        "conversation_history": history[-10:],
        "tool_call_round": 0,
    }


def main():
    graph = build_graph()
    history: list[dict] = []
    print("=== Factory AI — 자동차 공장 생산 질의 시스템 ===")
    print("종료: quit | 이력 초기화: clear\n")

    while True:
        try:
            user_input = input("질문> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료합니다.")
            break

        if not user_input:
            continue
        if user_input.lower() == "quit":
            print("종료합니다.")
            break
        if user_input.lower() == "clear":
            history.clear()
            print("대화 이력 초기화.\n")
            continue

        try:
            result = graph.invoke(_build_state(user_input, history))
        except Exception as e:
            print(f"\n오류: {e}\n")
            continue

        answer = result.get("final_answer", "응답 생성 실패")
        intent = result.get("intent", "unknown")

        print(f"\n[{intent}]")
        print(answer)
        print()

        history.append({"user": user_input, "answer": answer[:500], "intent": intent})


if __name__ == "__main__":
    main()
