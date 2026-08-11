from __future__ import annotations

import fnmatch
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


class FileServiceError(ValueError):
    pass


@dataclass
class FileMeta:
    name: str
    path: str
    size_bytes: int
    mtime: str
    ext: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "size_bytes": self.size_bytes,
            "mtime": self.mtime,
            "ext": self.ext,
        }


def _mtime_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class FileService:
    def __init__(self, base_dir: Path | None = None, trash_dir: str = ".trash") -> None:
        self.trash_dir = trash_dir
        self._base = base_dir

    def _resolve(self, path: str | Path) -> Path:
        p = Path(path)
        if self._base is not None and not p.is_absolute():
            p = self._base / p
        return p

    def scan(self, path: str, pattern: str = "*") -> dict:
        root = self._resolve(path)
        if not root.exists():
            raise FileServiceError(f"目录不存在: {root}")
        if not root.is_dir():
            raise FileServiceError(f"不是目录: {root}")
        files: list[FileMeta] = []
        dirs: list[str] = []
        try:
            entries = list(root.iterdir())
        except PermissionError as exc:
            raise FileServiceError(f"无权限访问目录: {root}") from exc
        for entry in sorted(entries, key=lambda e: e.name.lower()):
            if entry.is_dir():
                dirs.append(str(entry))
            elif entry.is_file() and fnmatch.fnmatch(entry.name, pattern):
                stat = entry.stat()
                files.append(FileMeta(
                    name=entry.name,
                    path=str(entry),
                    size_bytes=stat.st_size,
                    mtime=_mtime_iso(stat.st_mtime),
                    ext=entry.suffix.lower(),
                ))
        return {
            "root": str(root),
            "files": [f.to_dict() for f in files],
            "dirs": dirs,
            "count": len(files),
        }

    def organize_preview(self, path: str, rules: list[dict]) -> dict:
        root = self._resolve(path)
        if not root.is_dir():
            raise FileServiceError(f"不是目录: {root}")
        moves: list[dict] = []
        skipped: list[dict] = []
        for rule in rules:
            pattern = rule.get("pattern", "")
            target = rule.get("target", "")
            if not pattern or not target:
                raise FileServiceError("规则必须含 pattern 与 target")
            if "/" in target or "\\" in target or ".." in target:
                raise FileServiceError(f"非法 target（禁止路径穿越）: {target}")
        for rule in rules:
            pattern = rule["pattern"]
            target_dir = root / rule["target"]
            for entry in sorted(root.iterdir(), key=lambda e: e.name.lower()):
                if not entry.is_file() or not fnmatch.fnmatch(entry.name, pattern):
                    continue
                dest = target_dir / entry.name
                if dest.exists():
                    skipped.append({"name": entry.name, "reason": "目标已存在"})
                    continue
                moves.append({
                    "from": str(entry),
                    "to": str(dest),
                    "rule": pattern,
                })
        return {
            "dry_run": True,
            "operation": "file.organize",
            "moves": moves,
            "skipped": skipped,
            "move_count": len(moves),
        }

    def organize_apply(self, path: str, rules: list[dict]) -> dict:
        preview = self.organize_preview(path, rules)
        moved: list[dict] = []
        errors: list[dict] = []
        for m in preview["moves"]:
            src = Path(m["from"])
            dest = Path(m["to"])
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dest))
                moved.append({"from": m["from"], "to": str(dest)})
            except OSError as exc:
                errors.append({"from": m["from"], "error": str(exc)})
        return {
            "applied": True,
            "operation": "file.organize",
            "moved": moved,
            "moved_count": len(moved),
            "skipped": preview["skipped"],
            "errors": errors,
        }

    def clean_preview(self, path: str, pattern: str) -> dict:
        root = self._resolve(path)
        if not root.is_dir():
            raise FileServiceError(f"不是目录: {root}")
        to_trash: list[dict] = []
        for entry in sorted(root.iterdir(), key=lambda e: e.name.lower()):
            if entry.is_file() and fnmatch.fnmatch(entry.name, pattern):
                if entry.name == self.trash_dir:
                    continue
                to_trash.append({"name": entry.name, "path": str(entry)})
        return {
            "dry_run": True,
            "operation": "file.clean",
            "to_trash": to_trash,
            "count": len(to_trash),
        }

    def clean_apply(self, path: str, pattern: str) -> dict:
        preview = self.clean_preview(path, pattern)
        root = self._resolve(path)
        trash = root / self.trash_dir
        trash.mkdir(parents=True, exist_ok=True)
        moved: list[dict] = []
        errors: list[dict] = []
        for item in preview["to_trash"]:
            src = Path(item["path"])
            dest = trash / src.name
            if dest.exists():
                stamp = time.strftime("%Y%m%d%H%M%S")
                dest = trash / f"{src.stem}_{stamp}{src.suffix}"
            try:
                shutil.move(str(src), str(dest))
                moved.append({"from": item["path"], "to": str(dest)})
            except OSError as exc:
                errors.append({"from": item["path"], "error": str(exc)})
        return {
            "applied": True,
            "operation": "file.clean",
            "moved_to_trash": moved,
            "moved_count": len(moved),
            "errors": errors,
        }
