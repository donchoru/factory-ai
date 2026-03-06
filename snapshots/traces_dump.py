"""트레이스 MD 파일들을 snapshots/traces/ 에 복사.

실행: python -m snapshots.traces_dump
출력: snapshots/traces/*.md + snapshots/traces/README.md (인덱스)

traces/*.md 는 gitignore라 GitHub에서 안 보임.
snapshots/traces/ 에 복사하면 GitHub에서 마크다운 렌더링으로 바로 확인 가능.
"""

import re
import shutil
from pathlib import Path

TRACES_DIR = Path(__file__).parent.parent / "traces"
OUTPUT_DIR = Path(__file__).parent / "traces"


def _parse_trace_header(content: str) -> dict:
    """트레이스 MD에서 시간, 사용자 입력, 최종 의도를 추출."""
    header = {}
    for line in content.split("\n")[:5]:
        if "**시간**" in line:
            m = re.search(r"\*\*시간\*\*:\s*(.+)", line)
            if m:
                header["timestamp"] = m.group(1).strip()
        elif "**사용자 입력**" in line:
            m = re.search(r"\*\*사용자 입력\*\*:\s*(.+)", line)
            if m:
                header["user_input"] = m.group(1).strip()
        elif "**최종 의도**" in line:
            m = re.search(r"\*\*최종 의도\*\*:\s*(.+)", line)
            if m:
                header["intent"] = m.group(1).strip()
    return header


def dump():
    OUTPUT_DIR.mkdir(exist_ok=True)

    # 기존 복사본 삭제
    for old in OUTPUT_DIR.glob("trace_*.md"):
        old.unlink()

    trace_files = sorted(TRACES_DIR.glob("trace_*.md"))

    # MD 파일 그대로 복사
    for tf in trace_files:
        shutil.copy2(tf, OUTPUT_DIR / tf.name)

    # 인덱스 README 생성
    lines = [
        "# 에이전트 실행 트레이스",
        "",
        f"> 총 {len(trace_files)}건 | `python -m snapshots.traces_dump` 으로 재생성",
        "",
        "| # | 파일 | 시간 | 사용자 입력 | 의도 |",
        "|---|------|------|------------|------|",
    ]

    for i, tf in enumerate(trace_files, 1):
        content = tf.read_text(encoding="utf-8")
        h = _parse_trace_header(content)
        ts = h.get("timestamp", "?")
        ui = h.get("user_input", "?")
        intent = h.get("intent", "?")
        lines.append(f"| {i} | [{tf.name}](./{tf.name}) | {ts} | {ui} | `{intent}` |")

    (OUTPUT_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"트레이스 복사 완료: {OUTPUT_DIR}/")
    print(f"  총 {len(trace_files)}건 + README.md (인덱스)")
    for tf in trace_files:
        h = _parse_trace_header(tf.read_text(encoding="utf-8"))
        print(f"  - {tf.name}: {h.get('user_input', '?')}")


if __name__ == "__main__":
    dump()
