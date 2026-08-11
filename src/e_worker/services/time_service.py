from __future__ import annotations

import sqlite3
from datetime import date

from e_worker.models import TimeEntry
from e_worker.services.todo_service import TodoServiceError
from e_worker.storage.repository import TimeEntryRepository


class TimeServiceError(ValueError):
    pass


class TimeService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.repo = TimeEntryRepository(conn)
        self._conn = conn

    def log_time(self, item_id: str, date_str: str, duration_minutes: int,
                 note: str = "") -> TimeEntry:
        if not item_id:
            raise TimeServiceError("item_id 不能为空")
        if duration_minutes <= 0:
            raise TimeServiceError("duration_minutes 必须为正整数")
        try:
            date.fromisoformat(date_str)
        except ValueError as exc:
            raise TimeServiceError(f"date 格式非法: {date_str}（应为 YYYY-MM-DD）") from exc
        exists = self._conn.execute(
            "SELECT 1 FROM items WHERE id=?", (item_id,)).fetchone()
        if not exists:
            raise TimeServiceError(f"事项不存在: {item_id}")
        entry = TimeEntry(item_id=item_id, date=date_str,
                          duration_minutes=duration_minutes, note=note)
        return self.repo.create(entry)

    def list_time(self, *, item_id: str | None = None,
                  date_from: str | None = None, date_to: str | None = None) -> list[TimeEntry]:
        return self.repo.list(item_id=item_id, date_from=date_from, date_to=date_to)

    def total_minutes(self, *, date_from: str | None = None,
                      date_to: str | None = None) -> int:
        return sum(e.duration_minutes for e in self.list_time(date_from=date_from, date_to=date_to))
