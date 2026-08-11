from __future__ import annotations

import fnmatch
import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from e_worker.config import SafetyConfig

logger = logging.getLogger("e_worker.security")

SECURITY_LOG_DIR = Path(__file__).resolve().parent.parent.parent.parent / "logs" / "e-worker"


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    NEEDS_HUMAN = "needs_human"


@dataclass
class Adjudication:
    decision: Decision
    reason: str = ""
    missing_rule: str | None = None


SENSITIVE_DOMAINS = ("file", "env")


def _matches(rules: list[str], operation: str) -> bool:
    return any(fnmatch.fnmatch(operation, rule) for rule in rules)


def _sensitive(operation: str) -> bool:
    return any(operation == d or operation.startswith(f"{d}.") for d in SENSITIVE_DOMAINS)


def _log(operation: str, cfg: SafetyConfig, decision: Decision, rule: str | None) -> None:
    try:
        SECURITY_LOG_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "operation": operation,
            "mode": cfg.mode,
            "decision": decision.value,
            "matched_rule": rule,
        }
        with open(SECURITY_LOG_DIR / "security.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def check(operation: str, cfg: SafetyConfig) -> Adjudication:
    if cfg.mode == "whitelist":
        if _matches(cfg.allow_rules, operation):
            _log(operation, cfg, Decision.ALLOW, _matched(cfg.allow_rules, operation))
            return Adjudication(Decision.ALLOW)
        if _sensitive(operation):
            _log(operation, cfg, Decision.NEEDS_HUMAN, None)
            return Adjudication(
                Decision.NEEDS_HUMAN,
                reason="敏感操作类未被白名单覆盖，需人工确认",
                missing_rule=f"{operation.split('.')[0]}.*",
            )
        _log(operation, cfg, Decision.DENY, None)
        domain = operation.split(".", 1)[0]
        return Adjudication(
            Decision.DENY,
            reason=f"未授权操作：需在 config.json allow_rules 添加 {domain}.*",
            missing_rule=f"{domain}.*",
        )

    if _matches(cfg.deny_rules, operation):
        _log(operation, cfg, Decision.DENY, _matched(cfg.deny_rules, operation))
        return Adjudication(Decision.DENY, reason="命中黑名单规则，拒绝执行")
    if _sensitive(operation) and not _matches(cfg.allow_rules, operation):
        _log(operation, cfg, Decision.NEEDS_HUMAN, None)
        return Adjudication(
            Decision.NEEDS_HUMAN,
            reason="敏感操作类需人工确认",
            missing_rule=f"{operation.split('.')[0]}.*",
        )
    _log(operation, cfg, Decision.ALLOW, None)
    return Adjudication(Decision.ALLOW)


def _matched(rules: list[str], operation: str) -> str | None:
    for rule in rules:
        if fnmatch.fnmatch(operation, rule):
            return rule
    return None


def ensure_log_dir() -> None:
    SECURITY_LOG_DIR.mkdir(parents=True, exist_ok=True)
