from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from e_worker.config import SafetyConfig, load_config
from e_worker.security import Adjudication, Decision, check


@dataclass
class ToolContext:
    conn: Any = None
    config: SafetyConfig = field(default_factory=load_config)


class ToolError(Exception):
    pass


def resolve_context(ctx: ToolContext | None = None) -> ToolContext:
    return ctx or ToolContext()


def adjudicate(operation: str, ctx: ToolContext | None = None) -> Adjudication:
    ctx = resolve_context(ctx)
    return check(operation, ctx.config)


def require_allow(operation: str, ctx: ToolContext | None = None) -> None:
    result = adjudicate(operation, ctx)
    if result.decision == Decision.DENY:
        raise ToolError(result.reason)
    if result.decision == Decision.NEEDS_HUMAN:
        raise ToolError(f"需要人工确认：{result.reason}（缺少规则 {result.missing_rule}）")


def preview_result(operation: str, impact: dict[str, Any]) -> dict[str, Any]:
    return {
        "dry_run": True,
        "operation": operation,
        "impact": impact,
        "authorized": True,
    }
