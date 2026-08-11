from __future__ import annotations

import sqlite3

import pytest

from e_worker.config import SafetyConfig
from e_worker.storage.db import apply_migrations, get_connection
from e_worker.tools import todo_tools
from e_worker.tools.common import ToolContext, ToolError


@pytest.fixture()
def ctx(tmp_path) -> ToolContext:
    conn: sqlite3.Connection = get_connection(tmp_path / "test.db")
    apply_migrations(conn)
    return ToolContext(
        conn=conn,
        config=SafetyConfig(mode="whitelist", allow_rules=["todo.*", "time.*"]),
    )


def test_preview_does_not_write(ctx):
    r = todo_tools.todo_create_preview("任务", "work", ctx=ctx)
    assert r["dry_run"] is True
    assert r["operation"] == "todo.create"
    assert todo_tools.todo_list(ctx=ctx)["count"] == 0


def test_apply_writes(ctx):
    r = todo_tools.todo_create_apply("任务", "work", ctx=ctx)
    assert r["applied"] is True
    assert todo_tools.todo_list(ctx=ctx)["count"] == 1


def test_apply_denied_without_rule(tmp_path):
    conn: sqlite3.Connection = get_connection(tmp_path / "test.db")
    apply_migrations(conn)
    strict = ToolContext(
        conn=conn,
        config=SafetyConfig(mode="whitelist", allow_rules=[]),
    )
    with pytest.raises(ToolError) as exc:
        todo_tools.todo_create_apply("任务", "work", ctx=strict)
    assert "todo.*" in str(exc.value)


def test_transition_preview_then_apply(ctx):
    item = todo_tools.todo_create_apply("任务", "work", ctx=ctx)["result"]
    preview = todo_tools.todo_transition_preview(item["id"], "todo", ctx=ctx)
    assert preview["impact"]["status→"] == "todo"
    assert todo_tools.todo_get(item["id"], ctx=ctx)["item"]["status"] == "inbox"
    applied = todo_tools.todo_transition_apply(item["id"], "todo", ctx=ctx)
    assert applied["result"]["status"] == "todo"
    done = todo_tools.todo_transition_apply(item["id"], "done", ctx=ctx)
    assert done["result"]["completed_at"] is not None


def test_update_preview_shows_changes(ctx):
    item = todo_tools.todo_create_apply("任务", "work", ctx=ctx)["result"]
    preview = todo_tools.todo_update_preview(item["id"], title="新标题", ctx=ctx)
    assert preview["impact"]["title→"] == "新标题"
    assert todo_tools.todo_get(item["id"], ctx=ctx)["item"]["title"] == "任务"


def test_list_and_get(ctx):
    a = todo_tools.todo_create_apply("a", "work", ctx=ctx)["result"]
    b = todo_tools.todo_create_apply("b", "study", ctx=ctx)["result"]
    assert todo_tools.todo_list(category="work", ctx=ctx)["count"] == 1
    assert todo_tools.todo_get(a["id"], ctx=ctx)["item"]["id"] == a["id"]
    assert todo_tools.todo_list(keyword="b", ctx=ctx)["count"] == 1
    with pytest.raises(ToolError):
        todo_tools.todo_get("missing", ctx=ctx)
