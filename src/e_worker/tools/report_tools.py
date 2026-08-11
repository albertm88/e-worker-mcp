from __future__ import annotations

from typing import Any

from e_worker.services.report_service import ReportService
from e_worker.tools.common import ToolContext, resolve_context


def report_daily(day: str | None = None, ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = resolve_context(ctx)
    service = ReportService(ctx.conn)
    return service.generate_daily_report(day)


def report_weekly(start_day: str | None = None,
                  ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = resolve_context(ctx)
    service = ReportService(ctx.conn)
    return service.generate_weekly_report(start_day)
