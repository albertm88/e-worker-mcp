from __future__ import annotations

import sqlite3

import pytest

from e_worker.services.todo_service import TodoService, TodoServiceError
from e_worker.storage.db import apply_migrations, get_connection


@pytest.fixture()
def svc(tmp_path) -> TodoService:
    conn: sqlite3.Connection = get_connection(tmp_path / "test.db")
    apply_migrations(conn)
    yield TodoService(conn)
    conn.close()


def test_create_requires_category(svc):
    with pytest.raises(TodoServiceError):
        svc.create_item("task", "bogus")


def test_create_defaults(svc):
    item = svc.create_item(" 买菜  ", category="work")
    assert item.title == "买菜"
    assert item.status == "inbox"
    assert item.category == "work"
    assert item.priority == 3
    assert item.completed_at is None


def test_create_with_metadata_json(svc):
    item = svc.create_item("t", category="study", metadata={"source": "book"})
    fetched = svc.get_item(item.id)
    assert fetched.metadata == {"source": "book"}


def test_create_empty_title_rejected(svc):
    with pytest.raises(TodoServiceError):
        svc.create_item("   ", category="work")


def test_create_invalid_priority(svc):
    with pytest.raises(TodoServiceError):
        svc.create_item("t", category="work", priority=9)


def test_transition_flow(svc):
    item = svc.create_item("t", category="work")
    svc.transition_item(item.id, "todo")
    svc.transition_item(item.id, "doing")
    done = svc.transition_item(item.id, "done")
    assert done.status == "done"
    assert done.completed_at is not None


def test_transition_invalid_rejected(svc):
    item = svc.create_item("t", category="work")
    with pytest.raises(TodoServiceError):
        svc.transition_item(item.id, "doing")
    with pytest.raises(TodoServiceError):
        svc.transition_item(item.id, "bogus")
    svc.transition_item(item.id, "archived")
    with pytest.raises(TodoServiceError):
        svc.transition_item(item.id, "todo")


def test_transition_done_to_archived_then_locked(svc):
    item = svc.create_item("t", category="work")
    svc.transition_item(item.id, "todo")
    svc.transition_item(item.id, "done")
    svc.transition_item(item.id, "archived")
    with pytest.raises(TodoServiceError):
        svc.transition_item(item.id, "done")


def test_update_item(svc):
    item = svc.create_item("t", category="work")
    updated = svc.update_item(item.id, title="t2", priority=1, due="2026-08-15T00:00:00Z")
    assert updated.title == "t2"
    assert updated.priority == 1
    assert updated.due == "2026-08-15T00:00:00Z"


def test_update_missing_item(svc):
    with pytest.raises(TodoServiceError):
        svc.update_item("nope", title="x")


def test_list_filters(svc):
    a = svc.create_item("买牛奶", category="work", tags=["daily"])
    b = svc.create_item("读论文", category="study", tags=["paper"])
    svc.create_item("写周报", category="work")
    assert len(svc.list_items(category="work")) == 2
    assert len(svc.list_items(status="inbox")) == 3
    assert len(svc.list_items(keyword="牛奶")) == 1
    assert len(svc.list_items(tag="paper")) == 1
    svc.transition_item(b.id, "todo")
    svc.transition_item(b.id, "done")
    assert len(svc.list_items(status="done")) == 1


def test_list_order_desc(svc):
    svc.create_item("a", category="work")
    svc.create_item("b", category="work")
    items = svc.list_items()
    assert items[0].title == "b"


def test_archive_done_items(svc):
    item = svc.create_item("t", category="work")
    svc.transition_item(item.id, "todo")
    svc.transition_item(item.id, "done")
    svc.repo.conn.execute(
        "UPDATE items SET completed_at='2020-01-01T00:00:00Z' WHERE id=?", (item.id,))
    svc.repo.conn.commit()
    count = svc.archive_done_items(days=7)
    assert count == 1
    assert svc.get_item(item.id).status == "archived"
