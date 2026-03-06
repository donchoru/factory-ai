"""DB 연결 — 브릿지 패턴.

기존 import 유지: from db.connection import query, execute, execute_script
내부적으로 get_backend()에 위임하여 SQLite/Oracle 자동 전환.
"""

from db.backends import get_backend


def query(sql: str, params: tuple = ()) -> list[dict]:
    """SELECT 쿼리 → list[dict] 반환."""
    return get_backend().query(sql, params)


def execute(sql: str, params: tuple = ()) -> None:
    """INSERT/UPDATE/DELETE 실행."""
    get_backend().execute(sql, params)


def execute_script(script: str) -> None:
    """SQL 스크립트 일괄 실행."""
    get_backend().execute_script(script)
