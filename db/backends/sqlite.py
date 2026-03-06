"""SQLite 백엔드 — 기존 db/connection.py 로직."""

import sqlite3

from config import DB_PATH
from db.backends.base import DatabaseBackend


class SQLiteBackend(DatabaseBackend):

    def __init__(self):
        self._db_path = str(DB_PATH)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple = ()) -> None:
        conn = self._connect()
        try:
            conn.execute(sql, params)
            conn.commit()
        finally:
            conn.close()

    def execute_script(self, script: str) -> None:
        conn = self._connect()
        try:
            conn.executescript(script)
        finally:
            conn.close()
