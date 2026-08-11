from __future__ import annotations

import re
from dataclasses import dataclass, field

ACTION_WORDS = (
    "待办", "需要", "负责", "跟进", "记得", "要", "必须", "尽快",
    "安排", "整理", "完成", "提交", "确认", "通知", "协调", "修复",
    "调研", "输出", "准备", "更新", "回复", "发送", "创建", "关闭",
)

DATE_PATTERNS = [
    (re.compile(r"(今天|今日)"), 0),
    (re.compile(r"(明天|明日)"), 1),
    (re.compile(r"后天"), 2),
    (re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})"), None),
    (re.compile(r"(\d{1,2})月(\d{1,2})日"), None),
    (re.compile(r"下周一|下周二|下周三|下周四|下周五"), None),
    (re.compile(r"本周内"), None),
    (re.compile(r"截止\s*(?:到)?\s*(今天|明天|后天|\d{1,2}月\d{1,2}日)"), None),
]

ACTION_PATTERN = re.compile("|".join(ACTION_WORDS))


@dataclass
class TodoDraft:
    title: str
    assignee: str | None = None
    due: str | None = None
    priority: int = 3
    category: str = "work"


@dataclass
class MeetingExtractResult:
    todo_drafts: list[TodoDraft] = field(default_factory=list)
    summary: str = ""


def _extract_due(line: str, base_date: str | None = None) -> str | None:
    for pattern, offset in DATE_PATTERNS:
        m = pattern.search(line)
        if not m:
            continue
        if offset is not None:
            from datetime import datetime, timedelta, timezone

            base = datetime.now(timezone.utc)
            due = (base + timedelta(days=offset)).strftime("%Y-%m-%dT%H:%M:%SZ")
            return due
        groups = m.groups()
        if pattern.pattern.startswith(r"(\d{4})-"):
            y, mo, d = int(groups[0]), int(groups[1]), int(groups[2])
            return f"{y:04d}-{mo:02d}-{d:02d}T00:00:00Z"
        if pattern.pattern.startswith(r"(\d{1,2})月"):
            mo, d = int(groups[0]), int(groups[1])
            return f"2026-{mo:02d}-{d:02d}T00:00:00Z"
        if m.group(0).startswith("下周"):
            from datetime import datetime, timedelta, timezone

            base = datetime.now(timezone.utc)
            days_ahead = 7 - base.weekday()
            due = (base + timedelta(days=days_ahead)).strftime("%Y-%m-%dT%H:%M:%SZ")
            return due
        if "本周内" in m.group(0):
            from datetime import datetime, timedelta, timezone

            base = datetime.now(timezone.utc)
            due = (base + timedelta(days=6 - base.weekday())).strftime("%Y-%m-%dT%H:%M:%SZ")
            return due
    return None


ASSIGNEE_STOP_WORDS = (
    "负责", "处理", "跟进", "完成", "更新", "整理", "提交", "确认", "通知",
    "协调", "修复", "调研", "输出", "准备", "回复", "发送", "创建", "关闭", "安排",
)

ASSIGNEE_PATTERN = re.compile(
    r"(?:由|让|请|@)([\u4e00-\u9fa5A-Za-z0-9_]{2,8}?)"
    r"(?=" + "|".join(ASSIGNEE_STOP_WORDS) + r")"
)


def _extract_assignee(line: str) -> str | None:
    m = ASSIGNEE_PATTERN.search(line)
    return m.group(1) if m else None


def _clean_title(line: str) -> str:
    line = re.sub(r"^(会议纪要|纪要|记录)[:：]\s*", "", line)
    line = line.strip(" 　-•·，,。：:；;")
    return line


def extract_todos(text: str, *, category: str = "work") -> MeetingExtractResult:
    if not text or not text.strip():
        return MeetingExtractResult(todo_drafts=[], summary="")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    drafts: list[TodoDraft] = []
    summary_lines: list[str] = []
    for line in lines:
        if ACTION_PATTERN.search(line) and len(line) >= 4:
            title = _clean_title(line)
            if len(title) >= 3:
                drafts.append(
                    TodoDraft(
                        title=title,
                        assignee=_extract_assignee(line),
                        due=_extract_due(line),
                        category=category,
                    )
                )
        else:
            summary_lines.append(_clean_title(line))
    summary = "；".join(s for s in summary_lines if s)[:500]
    return MeetingExtractResult(todo_drafts=drafts, summary=summary)
