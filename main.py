"""CLI 대화 진입점 — LangGraph 멀티에이전트 자동차 공장 생산 질의."""

from datetime import datetime
from pathlib import Path

from config import TRACES_DIR
from graph.workflow import build_graph


def save_trace(user_input: str, intent: str, trace_lines: list[str]) -> Path:
    """트레이스 로그를 Markdown 파일로 저장."""
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
    return path


def main():
    print("=" * 60)
    print("  Factory AI — 자동차 공장 생산 질의 시스템")
    print("  종료: quit | 이력 초기화: clear")
    print("=" * 60)

    app = build_graph()
    history: list[dict] = []

    while True:
        try:
            user_input = input("\n🏭 질문> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료합니다.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "q", "exit"):
            print("종료합니다.")
            break
        if user_input.lower() == "clear":
            history.clear()
            print("🗑️ 대화 이력 초기화.")
            continue

        print(f"\n⏳ 처리 중...")

        try:
            result = app.invoke({
                "messages": [],
                "intent": "",
                "intent_detail": "",
                "trace_log": [],
                "user_input": user_input,
                "final_answer": "",
                "conversation_history": list(history[-10:]),
                "tool_call_round": 0,
            })

            answer = result.get("final_answer", "응답을 생성하지 못했습니다.")
            intent = result.get("intent", "unknown")
            trace_log = result.get("trace_log", [])

            # 응답 출력
            print(f"\n📋 [의도: {intent}]")
            print("-" * 40)
            print(answer)
            print("-" * 40)

            # 대화 이력
            history.append({
                "user": user_input,
                "answer": answer[:300],
                "intent": intent,
            })
            if len(history) > 10:
                history = history[-10:]

            # 트레이스 저장
            trace_path = save_trace(user_input, intent, trace_log)
            print(f"📝 Trace 저장: {trace_path.name}")

        except Exception as e:
            print(f"\n❌ 오류: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
