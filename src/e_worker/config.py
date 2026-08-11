from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

logger = logging.getLogger("e_worker.config")

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config.json"

SafetyMode = Literal["whitelist", "blacklist"]


@dataclass
class SafetyConfig:
    mode: SafetyMode = "whitelist"
    allow_rules: list[str] = field(default_factory=list)
    deny_rules: list[str] = field(default_factory=list)
    trash_dir: str = ".trash"


def load_config(path: Path | None = None) -> SafetyConfig:
    path = path or DEFAULT_CONFIG_PATH
    if not path.exists():
        logger.warning("config missing at %s, fallback to whitelist + empty rules", path)
        return SafetyConfig()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        safety = data.get("safety", {})
        mode = safety.get("mode", "whitelist")
        if mode not in ("whitelist", "blacklist"):
            logger.warning("invalid mode %r, fallback to whitelist", mode)
            mode = "whitelist"
        file_cfg = data.get("file", {})
        return SafetyConfig(
            mode=mode,
            allow_rules=[str(r) for r in safety.get("allow_rules", [])],
            deny_rules=[str(r) for r in safety.get("deny_rules", [])],
            trash_dir=str(file_cfg.get("trash_dir", ".trash")),
        )
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("config load failed (%s), fallback to whitelist + empty rules", exc)
        return SafetyConfig()
