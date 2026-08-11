from __future__ import annotations

from typing import Any

from e_worker.services.file_service import FileService, FileServiceError
from e_worker.tools.common import (
    ToolContext,
    ToolError,
    preview_result,
    require_allow,
    resolve_context,
)


def _service(ctx: ToolContext | None = None) -> FileService:
    ctx = resolve_context(ctx)
    trash = getattr(ctx.config, "trash_dir", None) or ".trash"
    return FileService(trash_dir=trash)


def _guard(fn, ctx):
    try:
        return fn()
    except FileServiceError as exc:
        raise ToolError(str(exc)) from exc


def file_scan(path: str, pattern: str = "*",
              ctx: ToolContext | None = None) -> dict[str, Any]:
    ctx = resolve_context(ctx)
    return _guard(lambda: _service(ctx).scan(path, pattern), ctx)


def file_organize_preview(path: str, rules: list[dict],
                          ctx: ToolContext | None = None) -> dict[str, Any]:
    operation = "file.organize"
    require_allow(operation, ctx)
    ctx = resolve_context(ctx)
    return _guard(lambda: _service(ctx).organize_preview(path, rules), ctx)


def file_organize_apply(path: str, rules: list[dict],
                        ctx: ToolContext | None = None) -> dict[str, Any]:
    operation = "file.organize"
    require_allow(operation, ctx)
    ctx = resolve_context(ctx)
    return _guard(lambda: _service(ctx).organize_apply(path, rules), ctx)


def file_clean_preview(path: str, pattern: str,
                       ctx: ToolContext | None = None) -> dict[str, Any]:
    operation = "file.clean"
    require_allow(operation, ctx)
    ctx = resolve_context(ctx)
    return _guard(lambda: _service(ctx).clean_preview(path, pattern), ctx)


def file_clean_apply(path: str, pattern: str,
                     ctx: ToolContext | None = None) -> dict[str, Any]:
    operation = "file.clean"
    require_allow(operation, ctx)
    ctx = resolve_context(ctx)
    return _guard(lambda: _service(ctx).clean_apply(path, pattern), ctx)
