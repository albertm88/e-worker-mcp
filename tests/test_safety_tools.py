from __future__ import annotations

from e_worker.config import SafetyConfig
from e_worker.tools import safety_tools
from e_worker.tools.common import ToolContext


def test_safety_policy_returns_policy():
    ctx = ToolContext(
        conn=None,
        config=SafetyConfig(
            mode="whitelist",
            allow_rules=["todo.*"],
            deny_rules=["file.delete"],
            auto_approve=["todo.*", "time.*"],
        ),
    )
    r = safety_tools.safety_policy(ctx=ctx)
    assert r["mode"] == "whitelist"
    assert r["allow_rules"] == ["todo.*"]
    assert r["deny_rules"] == ["file.delete"]
    assert r["auto_approve"] == ["todo.*", "time.*"]
    assert "note" in r


def test_safety_policy_readonly():
    ctx = ToolContext(conn=None, config=SafetyConfig(mode="whitelist"))
    r = safety_tools.safety_policy(ctx=ctx)
    assert r["auto_approve"] == []
    assert r["mode"] == "whitelist"
