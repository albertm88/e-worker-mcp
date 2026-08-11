from __future__ import annotations

from pathlib import Path

import pytest

from e_worker.config import SafetyConfig
from e_worker.services.file_service import FileService, FileServiceError
from e_worker.tools import file_tools
from e_worker.tools.common import ToolContext, ToolError


@pytest.fixture()
def workdir(tmp_path) -> Path:
    (tmp_path / "a.pdf").write_bytes(b"pdf")
    (tmp_path / "b.txt").write_text("txt", encoding="utf-8")
    (tmp_path / "c.tmp").write_text("tmp", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    return tmp_path


@pytest.fixture()
def ctx(workdir) -> ToolContext:
    return ToolContext(
        conn=None,
        config=SafetyConfig(
            mode="whitelist",
            allow_rules=["todo.*", "meeting.*", "time.*", "report.*", "file.*"],
            trash_dir=".trash",
        ),
    )


def test_scan_readonly(workdir):
    svc = FileService()
    r = svc.scan(str(workdir))
    assert r["count"] == 3
    names = {f["name"] for f in r["files"]}
    assert names == {"a.pdf", "b.txt", "c.tmp"}
    pdf = next(f for f in r["files"] if f["name"] == "a.pdf")
    assert pdf["ext"] == ".pdf"
    assert pdf["size_bytes"] == 3


def test_scan_pattern(workdir):
    r = FileService().scan(str(workdir), pattern="*.tmp")
    assert r["count"] == 1
    assert r["files"][0]["name"] == "c.tmp"


def test_scan_missing_dir(workdir):
    with pytest.raises(FileServiceError):
        FileService().scan(str(workdir / "nope"))


def test_organize_preview_no_write(workdir):
    svc = FileService()
    rules = [{"pattern": "*.pdf", "target": "documents"}]
    r = svc.organize_preview(str(workdir), rules)
    assert r["dry_run"] is True
    assert r["move_count"] == 1
    assert (workdir / "a.pdf").exists()
    assert not (workdir / "documents").exists()


def test_organize_apply_moves(workdir):
    svc = FileService()
    rules = [{"pattern": "*.pdf", "target": "documents"}]
    r = svc.organize_apply(str(workdir), rules)
    assert r["moved_count"] == 1
    assert (workdir / "documents" / "a.pdf").exists()
    assert not (workdir / "a.pdf").exists()


def test_organize_conflict_skipped(workdir):
    svc = FileService()
    (workdir / "documents").mkdir()
    (workdir / "documents" / "a.pdf").write_bytes(b"keep")
    r = svc.organize_preview(str(workdir), [{"pattern": "*.pdf", "target": "documents"}])
    assert r["move_count"] == 0
    assert len(r["skipped"]) == 1


def test_organize_invalid_rule(workdir):
    svc = FileService()
    with pytest.raises(FileServiceError):
        svc.organize_preview(str(workdir), [{"pattern": "*.pdf"}])
    with pytest.raises(FileServiceError):
        svc.organize_preview(str(workdir), [{"pattern": "*.pdf", "target": "../evil"}])


def test_clean_moves_to_trash_not_delete(workdir):
    svc = FileService()
    r = svc.clean_apply(str(workdir), "*.tmp")
    assert r["moved_count"] == 1
    assert (workdir / ".trash" / "c.tmp").exists()
    assert not (workdir / "c.tmp").exists()
    assert (workdir / "a.pdf").exists()


def test_clean_trash_collision_renames(workdir):
    svc = FileService()
    svc.clean_apply(str(workdir), "*.tmp")
    (workdir / "d.tmp").write_text("d", encoding="utf-8")
    (workdir / ".trash" / "d.tmp").write_text("existing", encoding="utf-8")
    r = svc.clean_apply(str(workdir), "*.tmp")
    assert r["moved_count"] == 1
    trashed = list((workdir / ".trash").glob("d_*.tmp"))
    assert len(trashed) == 1
    assert (workdir / ".trash" / "d.tmp").read_text(encoding="utf-8") == "existing"


def test_no_physical_delete_call():
    import inspect

    from e_worker.services import file_service

    src = inspect.getsource(file_service)
    assert "os.remove" not in src
    assert "os.unlink" not in src
    assert "shutil.rmtree" not in src


def test_tool_scan_readonly(workdir, ctx):
    r = file_tools.file_scan(str(workdir), ctx=ctx)
    assert r["count"] == 3


def test_tool_organize_preview_no_write(workdir, ctx):
    r = file_tools.file_organize_preview(str(workdir), [{"pattern": "*.pdf", "target": "d"}], ctx=ctx)
    assert r["dry_run"] is True
    assert not (workdir / "d").exists()


def test_tool_organize_apply_moves(workdir, ctx):
    r = file_tools.file_organize_apply(str(workdir), [{"pattern": "*.pdf", "target": "d"}], ctx=ctx)
    assert r["applied"] is True
    assert (workdir / "d" / "a.pdf").exists()


def test_tool_denied_without_rule(workdir):
    strict = ToolContext(
        conn=None,
        config=SafetyConfig(mode="whitelist", allow_rules=[], trash_dir=".trash"),
    )
    with pytest.raises(ToolError) as exc:
        file_tools.file_organize_apply(str(workdir), [{"pattern": "*.pdf", "target": "d"}], ctx=strict)
    assert "file.*" in str(exc.value)


def test_tool_needs_human_sensitive(workdir):
    strict = ToolContext(
        conn=None,
        config=SafetyConfig(mode="blacklist", deny_rules=[], trash_dir=".trash"),
    )
    with pytest.raises(ToolError) as exc:
        file_tools.file_clean_apply(str(workdir), "*.tmp", ctx=strict)
    assert "人工" in str(exc.value)
