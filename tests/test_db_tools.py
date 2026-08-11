from __future__ import annotations

import json
import sqlite3

import pytest

from e_worker.config import SafetyConfig
from e_worker.services.todo_service import TodoService
from e_worker.storage.db import apply_migrations, get_connection
from e_worker.tools import db_tools
from e_worker.tools.common import ToolContext, ToolError


@pytest.fixture()
def conn(tmp_path) -> sqlite3.Connection:
    c = get_connection(tmp_path / "test.db")
    apply_migrations(c)
    yield c
    c.close()


@pytest.fixture()
def ctx(conn) -> ToolContext:
    return ToolContext(conn=conn, config=SafetyConfig(mode="whitelist", allow_rules=["db.*", "todo.*"]))


def test_export_json_roundtrip(conn, ctx, tmp_path):
    todo = TodoService(conn)
    item = todo.create_item("带标签任务", category="work", tags=["a", "b"], metadata={"k": "v"})
    target = tmp_path / "export.json"
    r = db_tools.db_export(str(target), "json", ctx=ctx)
    assert r["items"] == 1
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert payload["items"][0]["tags"] == '["a", "b"]'

    conn2 = get_connection(tmp_path / "import.db")
    apply_migrations(conn2)
    ctx2 = ToolContext(conn=conn2, config=SafetyConfig(mode="whitelist", allow_rules=["db.*"]))
    applied = db_tools.db_import_apply(str(target), "json", ctx=ctx2)
    assert applied["inserted_items"] == 1
    row = conn2.execute("SELECT * FROM items WHERE id=?", (item.id,)).fetchone()
    assert row["tags"] == '["a", "b"]'
    assert row["metadata"] == '{"k": "v"}'
    conn2.close()


def test_export_rejects_existing(conn, ctx, tmp_path):
    target = tmp_path / "exists.json"
    target.write_text("old", encoding="utf-8")
    with pytest.raises(ToolError):
        db_tools.db_export(str(target), "json", ctx=ctx)


def test_import_denied_without_rule(conn, tmp_path):
    target = tmp_path / "x.json"
    target.write_text('{"items": [], "time_entries": []}', encoding="utf-8")
    strict = ToolContext(conn=conn, config=SafetyConfig(mode="whitelist", allow_rules=[]))
    with pytest.raises(ToolError):
        db_tools.db_import_apply(str(target), "json", ctx=strict)


def test_import_merge_false_nonempty_rejected(conn, ctx, tmp_path):
    TodoService(conn).create_item("已有", category="work")
    target = tmp_path / "x.json"
    target.write_text('{"items": [], "time_entries": []}', encoding="utf-8")
    with pytest.raises(ToolError):
        db_tools.db_import_apply(str(target), "json", merge=False, ctx=ctx)


def test_import_preview_conflicts(conn, ctx, tmp_path):
    todo = TodoService(conn)
    item = todo.create_item("冲突任务", category="work")
    target = tmp_path / "x.json"
    payload = {"schema_version": 2, "exported_at": "x",
               "items": [{"id": item.id, "title": "同名", "status": "inbox",
                          "category": "work", "priority": 3, "due": None, "tags": "[]",
                          "notes": "", "metadata": "{}", "created_at": "a",
                          "updated_at": "b", "completed_at": None}],
               "time_entries": []}
    target.write_text(json.dumps(payload), encoding="utf-8")
    preview = db_tools.db_import_preview(str(target), "json", merge=True, ctx=ctx)
    assert preview["impact"]["conflict_count"] == 1
    assert preview["impact"]["conflict_ids"] == [item.id]


def test_import_missing_file(conn, ctx):
    with pytest.raises(ToolError):
        db_tools.db_import_apply(str(conn.__class__), "json", ctx=ctx)


def test_export_csv(conn, ctx, tmp_path):
    TodoService(conn).create_item("csv任务", category="work")
    target = tmp_path / "export.csv"
    r = db_tools.db_export(str(target), "csv", ctx=ctx)
    assert r["items"] == 1
    content = target.read_text(encoding="utf-8")
    assert "csv任务" in content
