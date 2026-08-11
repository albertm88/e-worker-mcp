from __future__ import annotations

from e_worker.services.meeting_service import extract_todos


def test_extract_action_lines():
    text = (
        "今天开会讨论了项目进度。\n"
        "小明负责跟进数据库迁移，明天完成。\n"
        "需要整理测试报告，截止周五。\n"
        "大家辛苦了。"
    )
    r = extract_todos(text)
    assert len(r.todo_drafts) == 2
    assert any("数据库迁移" in d.title for d in r.todo_drafts)
    assert any(d.due is not None for d in r.todo_drafts)
    assert "项目进度" in r.summary


def test_extract_due_date_phrases():
    r = extract_todos("需要提交报销单，明天完成。")
    assert r.todo_drafts[0].due is not None
    r2 = extract_todos("需要提交报销单，后天完成。")
    assert r2.todo_drafts[0].due is not None


def test_extract_assignee():
    r = extract_todos("由张三负责更新部署文档。")
    assert r.todo_drafts[0].assignee == "张三"


def test_empty_input():
    r = extract_todos("")
    assert r.todo_drafts == []
    assert r.summary == ""


def test_no_action_words():
    r = extract_todos("这是一个没有动作词的普通记录。")
    assert r.todo_drafts == []
    assert len(r.summary) > 0


def test_short_lines_ignored():
    r = extract_todos("好。\n收到。\n需要明天开会。")
    assert len(r.todo_drafts) >= 1
    assert all(len(d.title) >= 3 for d in r.todo_drafts)
