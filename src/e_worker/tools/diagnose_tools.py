from __future__ import annotations

from typing import Any

from e_worker.services.diagnose_service import DiagnoseService
from e_worker.tools.common import ToolContext, resolve_context


def diagnose_collect(ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = resolve_context(ctx)
    return DiagnoseService().collect()


def diagnose_report(ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = resolve_context(ctx)
    return DiagnoseService().report()
