from __future__ import annotations

import sqlite3
from typing import Any

from e_worker.models import Item, TimeEntry, utc_now_iso


class ItemRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create(self, item: Item) -> Item:
        cols = [
            "id", "title", "status", "category", "priority", "due",
            "tags", "notes", "metadata", "created_at", "updated_at", "completed_at",
        ]
        row = item.to_row()
        placeholders = ", ".join("?" for _ in cols)
        self.conn.execute(
            f"INSERT INTO items ({', '.join(cols)}) VALUES ({placeholders})",
            [row[c] for c in cols],
        )
        self.conn.commit()
        return item

    def update(self, item: Item) -> Item:
        item.updated_at = utc_now_iso()
        row = item.to_row()
        self.conn.execute(
            """UPDATE items SET title=?, status=?, category=?, priority=?, due=?,
               tags=?, notes=?, metadata=?, updated_at=?, completed_at=? WHERE id=?""",
            [row["title"], row["status"], row["category"], row["priority"], row["due"],
             row["tags"], row["notes"], row["metadata"], row["updated_at"], row["completed_at"],
             item.id],
        )
        self.conn.commit()
        return item

    def get(self, item_id: str) -> Item | None:
        row = self.conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        return Item.from_row(dict(row)) if row else None

    def list(self, *, status: str | None = None, category: str | None = None,
             keyword: str | None = None, tag: str | None = None,
             limit: int = 100, offset: int = 0) -> list[Item]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status=?")
            params.append(status)
        if category:
            clauses.append("category=?")
            params.append(category)
        if keyword:
            clauses.append("(title LIKE ? OR notes LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        if tag:
            clauses.append("tags LIKE ?")
            params.append(f'%"{tag}"%')
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM items {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self.conn.execute(sql, params).fetchall()
        return [Item.from_row(dict(r)) for r in rows]

    def delete(self, item_id: str) -> bool:
        cur = self.conn.execute("DELETE FROM items WHERE id=?", (item_id,))
        self.conn.commit()
        return cur.rowcount > 0


class TimeEntryRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create(self, entry: TimeEntry) -> TimeEntry:
        self.conn.execute(
            """INSERT INTO time_entries (id, item_id, date, duration_minutes, note, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (entry.id, entry.item_id, entry.date, entry.duration_minutes, entry.note, entry.created_at),
        )
        self.conn.commit()
        return entry

    def list(self, *, item_id: str | None = None,
             date_from: str | None = None, date_to: str | None = None) -> list[TimeEntry]:
        clauses: list[str] = []
        params: list[Any] = []
        if item_id:
            clauses.append("item_id=?")
            params.append(item_id)
        if date_from:
            clauses.append("date>=?")
            params.append(date_from)
        if date_to:
            clauses.append("date<=?")
            params.append(date_to)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.conn.execute(f"SELECT * FROM time_entries {where} ORDER BY date DESC, created_at DESC", params).fetchall()
        return [TimeEntry.from_row(dict(r)) for r in rows]
