from __future__ import annotations

import inspect
import logging
import typing
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from e_worker.config import load_config
from e_worker.security import ensure_log_dir
from e_worker.storage.db import apply_migrations, get_connection
from e_worker.tools import (
    db_tools,
    diagnose_tools,
    file_tools,
    meeting_tools,
    report_tools,
    time_tools,
    todo_tools,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "db" / "e-worker.db"


class App:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        self.conn = get_connection(db_path)
        apply_migrations(self.conn)
        self.config = load_config()

    def close(self) -> None:
        self.conn.close()


def _ctx_of(app: App) -> todo_tools.ToolContext:
    return todo_tools.ToolContext(conn=app.conn, config=app.config)


def _bind_context(fn, ctx):
    """返回保留原始业务签名的包装函数；ctx 从闭包注入，不暴露在 MCP schema 中。"""
    sig = inspect.signature(fn)
    params = [p for name, p in sig.parameters.items() if name != "ctx"]
    new_sig = sig.replace(parameters=params)
    hints = typing.get_type_hints(fn)
    hints.pop("ctx", None)

    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs, ctx=ctx)

    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    wrapper.__signature__ = new_sig
    wrapper.__annotations__ = hints
    return wrapper


def register_tools(mcp: MCPServer, app: App) -> None:
    ctx = _ctx_of(app)

    def make(fn):
        return _bind_context(fn, ctx)

    mcp.add_tool(make(todo_tools.todo_create_preview), name="todo_create_preview",
                 description="预览创建事项的影响（dry-run，不写库）。先调用本工具展示影响清单，再调用 todo_create_apply 执行。")
    mcp.add_tool(make(todo_tools.todo_create_apply), name="todo_create_apply",
                 description="实际创建事项（需先 preview 且通过白/黑名单裁决）。category 必填：work/study。")
    mcp.add_tool(make(todo_tools.todo_update_preview), name="todo_update_preview",
                 description="预览更新事项的影响（dry-run，不写库）。")
    mcp.add_tool(make(todo_tools.todo_update_apply), name="todo_update_apply",
                 description="实际更新事项（需先 preview 且通过裁决）。")
    mcp.add_tool(make(todo_tools.todo_transition_preview), name="todo_transition_preview",
                 description="预览事项状态流转的影响（dry-run）。状态机：inbox→todo→doing→done→archived。")
    mcp.add_tool(make(todo_tools.todo_transition_apply), name="todo_transition_apply",
                 description="实际流转事项状态（需先 preview 且通过裁决）。流转到 done 自动写 completed_at。")
    mcp.add_tool(make(todo_tools.todo_list), name="todo_list",
                 description="查询事项列表，支持 status/category/keyword/tag 组合过滤，按创建时间倒序。")
    mcp.add_tool(make(todo_tools.todo_get), name="todo_get",
                 description="按 id 查询单个事项详情。")

    mcp.add_tool(make(meeting_tools.meeting_extract), name="meeting_extract",
                 description="从会议纪要文本提取待办草案（动作词扫描+日期转截止时间），仅返回草案不写库；确认后调用 todo_create_apply 落库。")
    mcp.add_tool(make(time_tools.time_log_preview), name="time_log_preview",
                 description="预览记录工时的影响（dry-run，不写库）。")
    mcp.add_tool(make(time_tools.time_log_apply), name="time_log_apply",
                 description="实际记录工时（需先 preview 且通过裁决）。duration_minutes 为正整数。")
    mcp.add_tool(make(time_tools.time_list), name="time_list",
                 description="查询工时记录，支持按 item_id/日期范围过滤，返回总分钟数。")
    mcp.add_tool(make(report_tools.report_daily), name="report_daily",
                 description="生成日报：当日完成事项（work/study 分列）+ 当日工时总分钟。")
    mcp.add_tool(make(report_tools.report_weekly), name="report_weekly",
                 description="生成周报：按日分组完成数 + 分类汇总 + 工时总分钟。")
    mcp.add_tool(make(db_tools.db_export), name="db_export",
                 description="导出数据库为 JSON/CSV（只读操作），拒绝覆盖已存在路径。")
    mcp.add_tool(make(db_tools.db_import_preview), name="db_import_preview",
                 description="预览导入影响：来源文件、将导入条数、id 冲突检测、是否需清库（dry-run）。")
    mcp.add_tool(make(db_tools.db_import_apply), name="db_import_apply",
                 description="实际导入数据（需先 preview 且通过裁决）；merge=false 且库非空会被拒绝。")

    mcp.add_tool(make(file_tools.file_scan), name="file_scan",
                 description="只读扫描目录，返回文件元数据（名称/路径/大小/mtime/扩展名）与子目录列表。")
    mcp.add_tool(make(file_tools.file_organize_preview), name="file_organize_preview",
                 description="预览按规则归档的影响清单（dry-run，不移动文件）。rules 每项含 pattern(glob) 与 target(目标子目录)。")
    mcp.add_tool(make(file_tools.file_organize_apply), name="file_organize_apply",
                 description="实际执行归档移动（需先 preview 且通过裁决）；目标冲突跳过，不物理删除。")
    mcp.add_tool(make(file_tools.file_clean_preview), name="file_clean_preview",
                 description="预览清理匹配文件的影响（dry-run）：文件将移入 .trash/ 而非删除。")
    mcp.add_tool(make(file_tools.file_clean_apply), name="file_clean_apply",
                 description="实际清理（需先 preview 且通过裁决）：移入 .trash/ 回收区，绝不物理删除。")
    mcp.add_tool(make(diagnose_tools.diagnose_collect), name="diagnose_collect",
                 description="只读采集本机环境信息：Python/Node/Go 版本、PATH、端口监听列表、磁盘余量。不监听不绑定端口。")
    mcp.add_tool(make(diagnose_tools.diagnose_report), name="diagnose_report",
                 description="生成环境诊断报告：问题清单（磁盘不足/工具缺失/契约端口异常占用）+ 建议动作（不自动执行，需人工确认）。")


def build_mcp(app: App | None = None) -> MCPServer:
    ensure_log_dir()
    app = app or App()
    mcp = MCPServer(
        name="e-worker-mcp",
        title="e-worker-mcp",
        description="解决工作琐事的 MCP 工具：待办/工时/日报/纪要提取，双模式白黑名单安全裁决",
        version="0.0.0.1",
    )
    register_tools(mcp, app)
    return mcp


def main() -> None:
    app = App()
    mcp = build_mcp(app)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
