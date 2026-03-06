"""Oracle 백엔드 — oracledb + 플레이스홀더/LIMIT 자동 변환."""

import re

from db.backends.base import DatabaseBackend


def _convert_placeholders(sql: str, params: tuple) -> tuple[str, dict]:
    """? → :1, :2, :3 변환 + params를 dict로 변환."""
    converted = sql
    bind_vars = {}
    idx = 0
    while "?" in converted:
        idx += 1
        converted = converted.replace("?", f":{idx}", 1)
        bind_vars[str(idx)] = params[idx - 1]
    return converted, bind_vars


def _convert_limit(sql: str) -> str:
    """LIMIT :N → FETCH FIRST :N ROWS ONLY 변환."""
    pattern = r"LIMIT\s+:(\d+)"
    match = re.search(pattern, sql, re.IGNORECASE)
    if match:
        bind_name = match.group(1)
        sql = re.sub(
            pattern,
            f"FETCH FIRST :{bind_name} ROWS ONLY",
            sql,
            flags=re.IGNORECASE,
        )
    return sql


class OracleBackend(DatabaseBackend):

    def __init__(self, dsn: str, user: str, password: str, min_conn: int = 2, max_conn: int = 10):
        import oracledb

        self._pool = oracledb.create_pool(
            dsn=dsn, user=user, password=password,
            min=min_conn, max=max_conn,
        )

    def _to_oracle(self, sql: str, params: tuple) -> tuple[str, dict]:
        """SQLite SQL → Oracle SQL 변환."""
        converted, bind_vars = _convert_placeholders(sql, params)
        converted = _convert_limit(converted)
        return converted, bind_vars

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        ora_sql, bind_vars = self._to_oracle(sql, params)
        with self._pool.acquire() as conn:
            with conn.cursor() as cur:
                cur.execute(ora_sql, bind_vars)
                columns = [col[0].lower() for col in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]

    def execute(self, sql: str, params: tuple = ()) -> None:
        ora_sql, bind_vars = self._to_oracle(sql, params)
        with self._pool.acquire() as conn:
            with conn.cursor() as cur:
                cur.execute(ora_sql, bind_vars)
            conn.commit()

    def execute_script(self, script: str) -> None:
        statements = [s.strip() for s in script.split(";") if s.strip()]
        with self._pool.acquire() as conn:
            with conn.cursor() as cur:
                for stmt in statements:
                    cur.execute(stmt)
            conn.commit()
