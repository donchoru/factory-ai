"""SQLite factory.db 내용을 JSON으로 덤프.

실행: python -m snapshots.db_dump
출력: snapshots/db_snapshot.json

GitHub에서 factory.db에 어떤 데이터가 들어있는지 확인할 수 있도록 스냅샷을 생성한다.
python -m db.seed 실행 후 이 스크립트를 돌리면 최신 상태가 반영됨.
"""

import json
from pathlib import Path

from db.connection import query

OUTPUT_PATH = Path(__file__).parent / "db_snapshot.json"

TABLES = [
    "production_lines", "models", "shifts",
    "daily_production", "defects", "downtime",
]


def dump():
    snapshot = {
        "_info": {
            "description": "SQLite factory.db의 전체 데이터 스냅샷",
            "note": "*.db 는 바이너리라 Git에 안 올림. 이 파일로 GitHub에서 확인 가능",
            "regenerate": "python -m db.seed && python -m snapshots.db_dump",
        },
        "tables": {},
    }

    for table in TABLES:
        rows = query(f"SELECT * FROM {table}")
        snapshot["tables"][table] = {
            "count": len(rows),
            "rows": rows,
        }

    snapshot["_info"]["summary"] = {
        t: snapshot["tables"][t]["count"] for t in TABLES
    }

    OUTPUT_PATH.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    print(f"DB 스냅샷 저장: {OUTPUT_PATH}")
    for t in TABLES:
        print(f"  {t}: {snapshot['tables'][t]['count']}건")


if __name__ == "__main__":
    dump()
