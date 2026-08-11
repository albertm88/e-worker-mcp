from __future__ import annotations

import sqlite3

import pytest

from e_worker.config import SafetyConfig
from e_worker.services.time_service import TimeService, TimeServiceError
from e_worker.services.todo_service import TodoService
from e_worker.storage.db import apply_migrations, get_connection
from e_worker.tools import time_tools
from e_worker.tools.common import ToolContext, ToolError


@pytest.fixture()
def conn(tmp_path) -> sqlite3.Connection:
    c = get_connection(tmp_path / "test.db")
    apply_migrations(c)
    yield c
    c.close()


@pytest.fixture()
def item_id(conn) -> str:
    return TodoService(conn).create_item("t", category="work").id


def test_log_time_ok(conn, item_id):
    svc = TimeService(conn)
    e = svc.log_time(item_id, "2026-08-11", 60, "编码")
    assert e.duration_minutes == 60
    assert e.date == "2026-08-11"
    assert svc.total_minutes(date_from="2026-08-11", date_to="2026-08-11") == 60


def test_log_time_negative_rejected(conn, item_id):
    svc = TimeService(conn)
    with pytest.raises(TimeServiceError):
        svc.log_time(item_id, "2026-08-11", 0)


def test_log_time_bad_date_rejected(conn, item_id):
    svc = TimeService(conn)
    with pytest.raises(TimeServiceError):
        svc.log_time(item_id, "2026/08/11", 30)


def test_log_time_missing_item_rejected(conn):
    svc = TimeService(conn)
    with pytest.raises(TimeServiceError):
        svc.log_time("missing", "2026-08-11", 30)


def test_list_time_range(conn, item_id):
    svc = TimeService(conn)
    svc.log_time(item_id, "2026-08-10", 30)
    svc.log_time(item_id, "2026-08-11", 90)
    assert len(svc.list_time(date_from="2026-08-11", date_to="2026-08-11")) == 1
    assert len(svc.list_time()) == 2


def test_time_tool_preview_no_write(conn, item_id):
    ctx = ToolContext(conn=conn, config=SafetyConfig(mode="whitelist", allow_rules=["time.*"]))
    r = time_tools.time_log_preview(item_id, "2026-08-11", 45, ctx=ctx)
    assert r["dry_run"] is True
    assert time_tools.time_list(ctx=ctx)["count"] == 0


def test_time_tool_apply_and_deny(conn, item_id):
    allow = ToolContext(conn=conn, config=SafetyConfig(mode="whitelist", allow_rules=["time.*"]))
    r = time_tools.time_log_apply(item_id, "2026-08-11", 45, ctx=allow)
    assert r["applied"] is True
    assert time_tools.time_list(ctx=allow)["total_minutes"] == 45
    strict = ToolContext(conn=conn, config=SafetyConfig(mode="whitelist", allow_rules=[]))
    with pytest.raises(ToolError):
        time_tools.time_log_apply(item_id, "2026-08-11", 30, ctx=strict)


def test_time_tool_missing_item(conn):
    ctx = ToolContext(conn=conn, config=SafetyConfig(mode="whitelist", allow_rules=["time.*"]))
    with pytest.raises(ToolError):
        time_tools.time_log_apply("missing", "2026-08-11", 30, ctx=ctx)
