from __future__ import annotations

from typing import Any

from e_worker.services.meeting_service import extract_todos
from e_worker.tools.common import ToolContext, resolve_context


def meeting_extract(text: str, *, category: str = "work",
                    ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = resolve_context(ctx)
    result = extract_todos(text, category=category)
    return {
        "todo_drafts": [
            {
                "title": d.title,
                "assignee": d.assignee,
                "due": d.due,
                "priority": d.priority,
                "category": d.category,
            }
            for d in result.todo_drafts
        ],
        "summary": result.summary,
        "note": "仅提取草案，未写入数据库；确认后请调用 todo_create_apply 逐条落库",
    }
