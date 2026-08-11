from __future__ import annotations

from typing import Any

from e_worker.services.todo_service import TodoService
from e_worker.tools.common import (
    ToolContext,
    ToolError,
    preview_result,
    require_allow,
    resolve_context,
)


def todo_create_preview(title: str, category: str, *, priority: int = 3,
                        due: str | None = None, tags: list[str] | None = None,
                        notes: str = "", metadata: dict | None = None,
                        ctx: ToolContext | None = None) -> dict[str, Any]:
    operation = "todo.create"
    require_allow(operation, ctx)
    return preview_result(operation, {
        "action": "创建事项",
        "title": title,
        "category": category,
        "priority": priority,
        "due": due,
        "tags": tags or [],
        "notes": notes,
        "status": "inbox",
    })


def todo_create_apply(title: str, category: str, *, priority: int = 3,
                      due: str | None = None, tags: list[str] | None = None,
                      notes: str = "", metadata: dict | None = None,
                      ctx: ToolContext | None = None) -> dict[str, Any]:
    operation = "todo.create"
    require_allow(operation, ctx)
    ctx = resolve_context(ctx)
    service = TodoService(ctx.conn)
    item = service.create_item(
        title=title, category=category, priority=priority, due=due,
        tags=tags, notes=notes, metadata=metadata,
    )
    return {"applied": True, "operation": operation, "result": item.to_row()}


def todo_update_preview(item_id: str, *, title: str | None = None, priority: int | None = None,
                        due: str | None = None, tags: list[str] | None = None,
                        notes: str | None = None, metadata: dict | None = None,
                        ctx: ToolContext | None = None) -> dict[str, Any]:
    operation = "todo.update"
    require_allow(operation, ctx)
    ctx = resolve_context(ctx)
    service = TodoService(ctx.conn)
    item = service.get_item(item_id)
    changes: dict[str, Any] = {"item_id": item_id, "title": item.title}
    if title is not None:
        changes["title→"] = title
    if priority is not None:
        changes["priority→"] = priority
    if due is not None:
        changes["due→"] = due or None
    if tags is not None:
        changes["tags→"] = tags
    if notes is not None:
        changes["notes→"] = notes
    if metadata is not None:
        changes["metadata→"] = metadata
    return preview_result(operation, {"action": "更新事项", **changes})


def todo_update_apply(item_id: str, *, title: str | None = None, priority: int | None = None,
                      due: str | None = None, tags: list[str] | None = None,
                      notes: str | None = None, metadata: dict | None = None,
                      ctx: ToolContext | None = None) -> dict[str, Any]:
    operation = "todo.update"
    require_allow(operation, ctx)
    ctx = resolve_context(ctx)
    service = TodoService(ctx.conn)
    item = service.update_item(
        item_id, title=title, priority=priority, due=due,
        tags=tags, notes=notes, metadata=metadata,
    )
    return {"applied": True, "operation": operation, "result": item.to_row()}


def todo_transition_preview(item_id: str, new_status: str,
                            ctx: ToolContext | None = None) -> dict[str, Any]:
    operation = "todo.update"
    require_allow(operation, ctx)
    ctx = resolve_context(ctx)
    service = TodoService(ctx.conn)
    item = service.get_item(item_id)
    return preview_result(operation, {
        "action": "状态流转",
        "item_id": item_id,
        "title": item.title,
        "status→": new_status,
        "completed_at 更新": "是" if new_status == "done" else "否",
    })


def todo_transition_apply(item_id: str, new_status: str,
                          ctx: ToolContext | None = None) -> dict[str, Any]:
    operation = "todo.update"
    require_allow(operation, ctx)
    ctx = resolve_context(ctx)
    service = TodoService(ctx.conn)
    item = service.transition_item(item_id, new_status)
    return {"applied": True, "operation": operation, "result": item.to_row()}


def todo_list(*, status: str | None = None, category: str | None = None,
              keyword: str | None = None, tag: str | None = None,
              limit: int = 100, offset: int = 0,
              ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = resolve_context(ctx)
    service = TodoService(ctx.conn)
    items = service.list_items(
        status=status, category=category, keyword=keyword, tag=tag,
        limit=limit, offset=offset,
    )
    return {"items": [i.to_row() for i in items], "count": len(items)}


def todo_get(item_id: str, ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = resolve_context(ctx)
    service = TodoService(ctx.conn)
    try:
        item = service.get_item(item_id)
    except Exception as exc:
        raise ToolError(str(exc)) from exc
    return {"item": item.to_row()}
