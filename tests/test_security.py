from __future__ import annotations

import pytest

from e_worker.config import SafetyConfig, load_config
from e_worker.security import Decision, check, is_auto_approved


def test_whitelist_allows_matching():
    cfg = SafetyConfig(mode="whitelist", allow_rules=["todo.*"])
    assert check("todo.create", cfg).decision == Decision.ALLOW
    assert check("todo.update", cfg).decision == Decision.ALLOW


def test_whitelist_denies_unmatched_with_missing_rule():
    cfg = SafetyConfig(mode="whitelist", allow_rules=["todo.*"])
    r = check("time.log", cfg)
    assert r.decision == Decision.DENY
    assert r.missing_rule == "time.*"
    assert "time.*" in r.reason


def test_whitelist_sensitive_needs_human():
    cfg = SafetyConfig(mode="whitelist", allow_rules=["todo.*"])
    r = check("file.delete", cfg)
    assert r.decision == Decision.NEEDS_HUMAN
    assert r.missing_rule == "file.*"


def test_blacklist_denies_matching():
    cfg = SafetyConfig(mode="blacklist", deny_rules=["file.delete", "env.*"])
    assert check("file.delete", cfg).decision == Decision.DENY
    assert check("env.modify", cfg).decision == Decision.DENY


def test_blacklist_allows_unmatched():
    cfg = SafetyConfig(mode="blacklist", deny_rules=["file.delete"])
    assert check("todo.create", cfg).decision == Decision.ALLOW
    assert check("time.log", cfg).decision == Decision.ALLOW


def test_blacklist_sensitive_uncovered_needs_human():
    cfg = SafetyConfig(mode="blacklist", deny_rules=[])
    r = check("env.modify", cfg)
    assert r.decision == Decision.NEEDS_HUMAN


def test_same_operation_opposite_decisions():
    whitelist = SafetyConfig(mode="whitelist", allow_rules=["file.read"])
    blacklist = SafetyConfig(mode="blacklist", deny_rules=["file.delete"])
    assert check("time.log", whitelist).decision == Decision.DENY
    assert check("time.log", blacklist).decision == Decision.ALLOW


def test_config_missing_falls_back(tmp_path):
    cfg = load_config(tmp_path / "nope.json")
    assert cfg.mode == "whitelist"
    assert cfg.allow_rules == []


def test_config_invalid_mode_falls_back(tmp_path):
    p = tmp_path / "config.json"
    p.write_text('{"safety": {"mode": "bogus"}}', encoding="utf-8")
    cfg = load_config(p)
    assert cfg.mode == "whitelist"


def test_config_bad_json_falls_back(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{not json", encoding="utf-8")
    cfg = load_config(p)
    assert cfg.mode == "whitelist"


def test_security_log_written(tmp_path, monkeypatch):
    from e_worker import security

    monkeypatch.setattr(security, "SECURITY_LOG_DIR", tmp_path / "logs" / "e-worker")
    cfg = SafetyConfig(mode="whitelist", allow_rules=["todo.*"])
    check("todo.create", cfg)
    log_file = tmp_path / "logs" / "e-worker" / "security.log"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "todo.create" in content
    assert "whitelist" in content


def test_auto_approve_matching():
    cfg = SafetyConfig(mode="whitelist", auto_approve=["todo.*", "time.*"])
    assert is_auto_approved("todo.create", cfg) is True
    assert is_auto_approved("time.log", cfg) is True
    assert is_auto_approved("file.organize", cfg) is False
    assert is_auto_approved("db.import", cfg) is False


def test_auto_approve_empty_default():
    cfg = SafetyConfig(mode="whitelist")
    assert cfg.auto_approve == []
    assert is_auto_approved("todo.create", cfg) is False


def test_config_loads_auto_approve(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(
        '{"safety": {"mode": "whitelist", "auto_approve": ["todo.*"]}}',
        encoding="utf-8",
    )
    cfg = load_config(p)
    assert cfg.auto_approve == ["todo.*"]
    assert is_auto_approved("todo.create", cfg) is True


def test_config_without_auto_approve_backward_compatible(tmp_path):
    p = tmp_path / "config.json"
    p.write_text('{"safety": {"mode": "whitelist"}}', encoding="utf-8")
    cfg = load_config(p)
    assert cfg.auto_approve == []
