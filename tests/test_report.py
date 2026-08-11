from __future__ import annotations

import sqlite3

import pytest

from e_worker.services.report_service import ReportService
from e_worker.services.time_service import TimeService
from e_worker.services.todo_service import TodoService
from e_worker.storage.db import apply_migrations, get_connection


@pytest.fixture()
def conn(tmp_path) -> sqlite3.Connection:
    c = get_connection(tmp_path / "test.db")
    apply_migrations(c)
    yield c
    c.close()


def _complete_on(conn, todo, title, category, completed_at):
    item = todo.create_item(title, category=category)
    todo.transition_item(item.id, "todo")
    todo.transition_item(item.id, "done")
    conn.execute(
        "UPDATE items SET completed_at=? WHERE id=?", (completed_at, item.id))
    conn.commit()
    return item


def test_daily_report_with_data(conn):
    todo = TodoService(conn)
    _complete_on(conn, todo, "写周报", "work", "2026-08-11T10:00:00Z")
    _complete_on(conn, todo, "读论文", "study", "2026-08-11T12:00:00Z")
    TimeService(conn).log_time("_", "2026-08-11", 0) if False else None
    svc = ReportService(conn)
    report = svc.generate_daily_report("2026-08-11")
    assert report["date"] == "2026-08-11"
    assert len(report["completed"]) == 2
    assert report["by_category"] == {"work": 1, "study": 1}


def test_daily_report_empty_day(conn):
    svc = ReportService(conn)
    report = svc.generate_daily_report("2026-01-01")
    assert report["completed"] == []
    assert report["by_category"] == {}
    assert report["total_minutes"] == 0


def test_daily_report_with_time(conn):
    todo = TodoService(conn)
    item = _complete_on(conn, todo, "编码", "work", "2026-08-11T09:00:00Z")
    TimeService(conn).log_time(item.id, "2026-08-11", 120)
    report = ReportService(conn).generate_daily_report("2026-08-11")
    assert report["total_minutes"] == 120


def test_daily_only_counts_same_day(conn):
    todo = TodoService(conn)
    _complete_on(conn, todo, "昨天任务", "work", "2026-08-10T23:00:00Z")
    report = ReportService(conn).generate_daily_report("2026-08-11")
    assert len(report["completed"]) == 0


def test_weekly_report(conn):
    todo = TodoService(conn)
    _complete_on(conn, todo, "任务A", "work", "2026-08-10T10:00:00Z")
    _complete_on(conn, todo, "任务B", "study", "2026-08-12T10:00:00Z")
    report = ReportService(conn).generate_weekly_report("2026-08-10")
    assert report["week_start"] == "2026-08-10"
    assert report["week_end"] == "2026-08-16"
    assert report["total_completed"] == 2
    assert report["by_category"] == {"work": 1, "study": 1}
    assert report["by_day"]["2026-08-10"] == 1
    assert report["by_day"]["2026-08-12"] == 1


def test_weekly_empty(conn):
    report = ReportService(conn).generate_weekly_report("2026-01-05")
    assert report["total_completed"] == 0
    assert report["total_minutes"] == 0
