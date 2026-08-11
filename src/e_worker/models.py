from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ItemStatus(str, Enum):
    INBOX = "inbox"
    TODO = "todo"
    DOING = "doing"
    DONE = "done"
    ARCHIVED = "archived"


class ItemCategory(str, Enum):
    WORK = "work"
    STUDY = "study"


ALLOWED_TRANSITIONS: dict[ItemStatus, set[ItemStatus]] = {
    ItemStatus.INBOX: {ItemStatus.TODO, ItemStatus.ARCHIVED},
    ItemStatus.TODO: {ItemStatus.DOING, ItemStatus.DONE, ItemStatus.ARCHIVED, ItemStatus.INBOX},
    ItemStatus.DOING: {ItemStatus.DONE, ItemStatus.TODO},
    ItemStatus.DONE: {ItemStatus.ARCHIVED, ItemStatus.TODO},
    ItemStatus.ARCHIVED: set(),
}

VALID_STATUSES = {s.value for s in ItemStatus}
VALID_CATEGORIES = {c.value for c in ItemCategory}


@dataclass
class Item:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    status: str = ItemStatus.INBOX.value
    category: str = ItemCategory.WORK.value
    priority: int = 3
    due: str | None = None
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    completed_at: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Item":
        data = dict(row)
        tags = data.get("tags", "[]")
        metadata = data.get("metadata", "{}")
        if isinstance(tags, str):
            data["tags"] = json.loads(tags) if tags else []
        if isinstance(metadata, str):
            data["metadata"] = json.loads(metadata) if metadata else {}
        return cls(**data)

    def to_row(self) -> dict[str, Any]:
        data = asdict(self)
        data["tags"] = json.dumps(self.tags, ensure_ascii=False)
        data["metadata"] = json.dumps(self.metadata, ensure_ascii=False)
        return data


@dataclass
class TimeEntry:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    item_id: str = ""
    date: str = ""
    duration_minutes: int = 0
    note: str = ""
    created_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "TimeEntry":
        return cls(**row)

    def to_row(self) -> dict[str, Any]:
        return asdict(self)
