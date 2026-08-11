from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from e_worker.models import (
    ALLOWED_TRANSITIONS,
    Item,
    ItemStatus,
    VALID_CATEGORIES,
    VALID_STATUSES,
    utc_now_iso,
)
from e_worker.storage.repository import ItemRepository


class TodoServiceError(ValueError):
    pass


def _require_category(category: str) -> None:
    if category not in VALID_CATEGORIES:
        raise TodoServiceError(f"category 必填且须为 {'/'.join(sorted(VALID_CATEGORIES))}")


def _require_status(status: str) -> None:
    if status not in VALID_STATUSES:
        raise TodoServiceError(f"非法 status: {status}")


class TodoService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.repo = ItemRepository(conn)

    def create_item(self, title: str, category: str, *, priority: int = 3,
                    due: str | None = None, tags: list[str] | None = None,
                    notes: str = "", metadata: dict | None = None) -> Item:
        if not title or not title.strip():
            raise TodoServiceError("title 不能为空")
        _require_category(category)
        if not 1 <= int(priority) <= 4:
            raise TodoServiceError("priority 须为 1-4")
        item = Item(
            title=title.strip(),
            status=ItemStatus.INBOX.value,
            category=category,
            priority=int(priority),
            due=due,
            tags=tags or [],
            notes=notes,
            metadata=metadata or {},
        )
        return self.repo.create(item)

    def update_item(self, item_id: str, *, title: str | None = None, priority: int | None = None,
                    due: str | None = None, tags: list[str] | None = None,
                    notes: str | None = None, metadata: dict | None = None) -> Item:
        item = self.repo.get(item_id)
        if item is None:
            raise TodoServiceError(f"事项不存在: {item_id}")
        if title is not None:
            if not title.strip():
                raise TodoServiceError("title 不能为空")
            item.title = title.strip()
        if priority is not None:
            if not 1 <= int(priority) <= 4:
                raise TodoServiceError("priority 须为 1-4")
            item.priority = int(priority)
        if due is not None:
            item.due = due or None
        if tags is not None:
            item.tags = tags
        if notes is not None:
            item.notes = notes
        if metadata is not None:
            item.metadata = metadata
        return self.repo.update(item)

    def transition_item(self, item_id: str, new_status: str) -> Item:
        _require_status(new_status)
        item = self.repo.get(item_id)
        if item is None:
            raise TodoServiceError(f"事项不存在: {item_id}")
        current = ItemStatus(item.status)
        target = ItemStatus(new_status)
        allowed = ALLOWED_TRANSITIONS[current]
        if target not in allowed:
            raise TodoServiceError(
                f"非法流转 {current.value} → {target.value}，允许: {sorted(s.value for s in allowed)}"
            )
        item.status = target.value
        item.completed_at = utc_now_iso() if target == ItemStatus.DONE else None
        return self.repo.update(item)

    def list_items(self, *, status: str | None = None, category: str | None = None,
                   keyword: str | None = None, tag: str | None = None,
                   limit: int = 100, offset: int = 0) -> list[Item]:
        return self.repo.list(
            status=status, category=category, keyword=keyword, tag=tag,
            limit=limit, offset=offset,
        )

    def get_item(self, item_id: str) -> Item:
        item = self.repo.get(item_id)
        if item is None:
            raise TodoServiceError(f"事项不存在: {item_id}")
        return item

    def archive_done_items(self, days: int = 7) -> int:
        from datetime import timedelta

        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff = cutoff_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        count = 0
        for item in self.repo.list(status=ItemStatus.DONE.value, limit=10000):
            completed = item.completed_at or item.updated_at
            if completed < cutoff:
                self.transition_item(item.id, ItemStatus.ARCHIVED.value)
                count += 1
        return count
