from __future__ import annotations

from typing import Any

from e_worker.tools.common import ToolContext, resolve_context


def safety_policy(ctx: ToolContext | None = None) -> dict[str, Any]:
    """只读返回当前安全策略：mode/allow_rules/deny_rules/auto_approve。

    AI 在会话开始时调用一次，据此决定哪些操作可一步直达（auto_approve 命中域
    免逐次确认），哪些必须先展示影响清单征求用户确认。
    """
    ctx = resolve_context(ctx)
    cfg = ctx.config
    return {
        "mode": cfg.mode,
        "allow_rules": list(cfg.allow_rules),
        "deny_rules": list(cfg.deny_rules),
        "auto_approve": list(cfg.auto_approve),
        "note": (
            "auto_approve 命中域可直接执行（一步直达）；未命中域（如 file.*/env.*/db.import）"
            "必须先 preview 展示影响并征求用户确认后再 apply"
        ),
    }
