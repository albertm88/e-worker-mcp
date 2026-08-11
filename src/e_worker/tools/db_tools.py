from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from e_worker.models import Item, TimeEntry
from e_worker.tools.common import (
    ToolContext,
    ToolError,
    preview_result,
    require_allow,
    resolve_context,
)


def _read_all(conn: sqlite3.Connection) -> tuple[list[dict], list[dict]]:
    items = [dict(r) for r in conn.execute("SELECT * FROM items ORDER BY created_at").fetchall()]
    entries = [dict(r) for r in conn.execute("SELECT * FROM time_entries ORDER BY created_at").fetchall()]
    return items, entries


def db_export(path: str | None = None, format: str = "json",
              ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = resolve_context(ctx)
    conn = ctx.conn
    items, entries = _read_all(conn)
    version = conn.execute(
        "SELECT MAX(version) AS v FROM schema_version").fetchone()["v"] or 0
    target = Path(path) if path else Path(__file__).resolve().parent.parent.parent.parent / "db" / f"e-worker-export-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.{format}"
    if target.exists():
        raise ToolError(f"导出目标已存在，拒绝覆盖: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if format == "json":
        payload = {
            "schema_version": version,
            "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "items": items,
            "time_entries": entries,
        }
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    elif format == "csv":
        if items:
            with open(target, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(items[0].keys()))
                writer.writeheader()
                writer.writerows(items)
    else:
        raise ToolError(f"不支持的导出格式: {format}（json/csv）")
    return {"exported_to": str(target), "format": format,
            "items": len(items), "time_entries": len(entries)}


def db_import_preview(path: str, format: str = "json", merge: bool = False,
                      ctx: ToolContext | None = None) -> dict[str, Any]:
    operation = "db.import"
    require_allow(operation, ctx)
    ctx = resolve_context(ctx)
    source = Path(path)
    if not source.exists():
        raise ToolError(f"导入文件不存在: {path}")
    items, entries = _read_all(ctx.conn)
    existing_ids = {i["id"] for i in items}
    if format == "json":
        payload = json.loads(source.read_text(encoding="utf-8"))
        incoming = [i["id"] for i in payload.get("items", [])]
    elif format == "csv":
        with open(source, newline="", encoding="utf-8") as f:
            incoming = [r["id"] for r in csv.DictReader(f)]
    else:
        raise ToolError(f"不支持的导入格式: {format}（json/csv）")
    conflicts = sorted(set(incoming) & existing_ids)
    return preview_result(operation, {
        "action": "导入数据",
        "source": str(source),
        "incoming_count": len(incoming),
        "conflict_ids": conflicts[:20],
        "conflict_count": len(conflicts),
        "will_clear_existing": (not merge and len(items) > 0),
        "提示": "merge=false 且库非空会被拒绝；请确认",
    })


def db_import_apply(path: str, format: str = "json", merge: bool = False,
                    ctx: ToolContext | None = None) -> dict[str, Any]:
    operation = "db.import"
    require_allow(operation, ctx)
    ctx = resolve_context(ctx)
    source = Path(path)
    if not source.exists():
        raise ToolError(f"导入文件不存在: {path}")
    items, _ = _read_all(ctx.conn)
    if not merge and items:
        raise ToolError("merge=false 且目标库非空，拒绝导入（防误清空）；请使用 merge=true 或先清库")
    conn = ctx.conn
    if format == "json":
        payload = json.loads(source.read_text(encoding="utf-8"))
        raw_items = payload.get("items", [])
        raw_entries = payload.get("time_entries", [])
    elif format == "csv":
        with open(source, newline="", encoding="utf-8") as f:
            raw_items = [dict(r) for r in csv.DictReader(f)]
        raw_entries = []
    else:
        raise ToolError(f"不支持的导入格式: {format}（json/csv）")
    inserted_items = 0
    inserted_entries = 0
    conn.execute("BEGIN")
    try:
        for raw in raw_items:
            try:
                item = Item.from_row(raw)
            except (TypeError, KeyError, ValueError) as exc:
                raise ToolError(f"事项数据非法: {exc}") from exc
            exists = conn.execute("SELECT 1 FROM items WHERE id=?", (item.id,)).fetchone()
            if exists:
                continue
            conn.execute(
                """INSERT INTO items (id, title, status, category, priority, due, tags,
                   notes, metadata, created_at, updated_at, completed_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (item.id, item.title, item.status, item.category, item.priority, item.due,
                 item.to_row()["tags"], item.notes, item.to_row()["metadata"],
                 item.created_at, item.updated_at, item.completed_at),
            )
            inserted_items += 1
        for raw in raw_entries:
            try:
                entry = TimeEntry.from_row(raw)
            except (TypeError, KeyError, ValueError) as exc:
                raise ToolError(f"工时数据非法: {exc}") from exc
            exists = conn.execute("SELECT 1 FROM time_entries WHERE id=?", (entry.id,)).fetchone()
            if exists:
                continue
            conn.execute(
                """INSERT INTO time_entries (id, item_id, date, duration_minutes, note, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (entry.id, entry.item_id, entry.date, entry.duration_minutes, entry.note, entry.created_at),
            )
            inserted_entries += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"applied": True, "operation": operation,
            "inserted_items": inserted_items, "inserted_entries": inserted_entries}
