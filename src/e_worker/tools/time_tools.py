from __future__ import annotations

from typing import Any

from e_worker.services.time_service import TimeService
from e_worker.tools.common import (
    ToolContext,
    ToolError,
    preview_result,
    require_allow,
    resolve_context,
)


def time_log_preview(item_id: str, date: str, duration_minutes: int, note: str = "",
                     ctx: ToolContext | None = None) -> dict[str, Any]:
    operation = "time.log"
    require_allow(operation, ctx)
    return preview_result(operation, {
        "action": "记录工时",
        "item_id": item_id,
        "date": date,
        "duration_minutes": duration_minutes,
        "note": note,
    })


def time_log_apply(item_id: str, date: str, duration_minutes: int, note: str = "",
                   ctx: ToolContext | None = None) -> dict[str, Any]:
    operation = "time.log"
    require_allow(operation, ctx)
    ctx = resolve_context(ctx)
    service = TimeService(ctx.conn)
    try:
        entry = service.log_time(item_id, date, duration_minutes, note)
    except Exception as exc:
        raise ToolError(str(exc)) from exc
    return {"applied": True, "operation": operation, "result": entry.to_row()}


def time_list(*, item_id: str | None = None, date_from: str | None = None,
              date_to: str | None = None,
              ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = resolve_context(ctx)
    service = TimeService(ctx.conn)
    entries = service.list_time(item_id=item_id, date_from=date_from, date_to=date_to)
    return {
        "time_entries": [e.to_row() for e in entries],
        "count": len(entries),
        "total_minutes": sum(e.duration_minutes for e in entries),
    }
