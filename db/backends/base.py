"""DB 백엔드 추상 클래스."""

from abc import ABC, abstractmethod


class DatabaseBackend(ABC):
    """SQLite / Oracle 공통 인터페이스."""

    @abstractmethod
    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        """SELECT 쿼리 → list[dict] 반환."""

    @abstractmethod
    def execute(self, sql: str, params: tuple = ()) -> None:
        """INSERT/UPDATE/DELETE 실행."""

    @abstractmethod
    def execute_script(self, script: str) -> None:
        """SQL 스크립트 일괄 실행."""
