from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Any

from e_worker.services.time_service import TimeService
from e_worker.services.todo_service import TodoService


class ReportService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.todo = TodoService(conn)
        self.time = TimeService(conn)

    def generate_daily_report(self, day: str | None = None) -> dict[str, Any]:
        day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        day_start = f"{day}T00:00:00Z"
        day_end = f"{day}T23:59:59Z"
        completed = [
            i for i in self.todo.list_items(status="done", limit=10000)
            if i.completed_at and day_start <= i.completed_at <= day_end
        ]
        by_category: dict[str, int] = {}
        for i in completed:
            by_category[i.category] = by_category.get(i.category, 0) + 1
        entries = self.time.list_time(date_from=day, date_to=day)
        return {
            "date": day,
            "completed": [i.to_row() for i in completed],
            "by_category": by_category,
            "total_minutes": sum(e.duration_minutes for e in entries),
        }

    def generate_weekly_report(self, start_day: str | None = None) -> dict[str, Any]:
        if start_day:
            start = date.fromisoformat(start_day)
        else:
            today = datetime.now(timezone.utc).date()
            start = today - timedelta(days=today.weekday())
        days = [start + timedelta(days=i) for i in range(7)]
        by_day: dict[str, int] = {}
        by_category: dict[str, int] = {}
        total_minutes = 0
        for d in days:
            day_str = d.strftime("%Y-%m-%d")
            report = self.generate_daily_report(day_str)
            by_day[day_str] = len(report["completed"])
            total_minutes += report["total_minutes"]
            for cat, n in report["by_category"].items():
                by_category[cat] = by_category.get(cat, 0) + n
        return {
            "week_start": days[0].strftime("%Y-%m-%d"),
            "week_end": days[-1].strftime("%Y-%m-%d"),
            "by_day": by_day,
            "by_category": by_category,
            "total_completed": sum(by_day.values()),
            "total_minutes": total_minutes,
        }
