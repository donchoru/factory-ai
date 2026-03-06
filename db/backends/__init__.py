"""DB 백엔드 팩토리 — DB_TYPE 환경변수로 SQLite/Oracle 자동 선택."""

from db.backends.base import DatabaseBackend

_backend: DatabaseBackend | None = None


def get_backend() -> DatabaseBackend:
    """싱글톤 백엔드 인스턴스 반환."""
    global _backend
    if _backend is not None:
        return _backend

    from config import DB_TYPE

    if DB_TYPE == "oracle":
        from config import ORACLE_DSN, ORACLE_PASSWORD, ORACLE_USER
        from db.backends.oracle import OracleBackend

        _backend = OracleBackend(
            dsn=ORACLE_DSN, user=ORACLE_USER, password=ORACLE_PASSWORD,
        )
    else:
        from db.backends.sqlite import SQLiteBackend

        _backend = SQLiteBackend()

    return _backend
