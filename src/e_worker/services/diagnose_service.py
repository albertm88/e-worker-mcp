from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

PORT_CONTRACT = {
    5433: "add-env-post（add-coder 治理库独占，禁止抢占）",
    14433: "已废弃（禁止复活）",
    15433: "dockerd 占用（禁止用于业务）",
}


def _tool_version(tool: str) -> dict | None:
    try:
        proc = subprocess.run(
            [tool, "--version"], capture_output=True, text=True, timeout=5
        )
        version = (proc.stdout or proc.stderr).strip().splitlines()
        return {"version": version[0] if version else "", "path": shutil.which(tool)}
    except (OSError, subprocess.SubprocessError):
        return None


def _listening_ports() -> list[dict]:
    ports: list[dict] = []
    try:
        proc = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=10
        )
        for line in proc.stdout.splitlines():
            line = line.strip()
            if "LISTENING" not in line:
                continue
            parts = line.split()
            if len(parts) < 5:
                continue
            addr = parts[1]
            if not addr.endswith(":0") and ":" in addr:
                port_str = addr.rsplit(":", 1)[-1]
                if port_str.isdigit():
                    ports.append({
                        "port": int(port_str),
                        "pid": parts[-1],
                        "process": _pid_name(parts[-1]),
                    })
    except (OSError, subprocess.SubprocessError):
        pass
    dedup: dict[int, dict] = {}
    for p in ports:
        dedup.setdefault(p["port"], p)
    return sorted(dedup.values(), key=lambda p: p["port"])


def _pid_name(pid: str) -> str:
    try:
        proc = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=5,
        )
        line = proc.stdout.strip().splitlines()
        if line:
            return line[0].split(",")[0].strip('"')
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


class DiagnoseService:
    def collect(self) -> dict[str, Any]:
        python_info = _tool_version("python")
        node_info = _tool_version("node")
        go_info = _tool_version("go")
        path_entries = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
        disk = shutil.disk_usage(Path.home())
        ports = _listening_ports()
        return {
            "python": python_info,
            "node": node_info,
            "go": go_info,
            "path_count": len(path_entries),
            "path_sample": path_entries[:5],
            "ports": ports,
            "disk": {
                "total_bytes": disk.total,
                "free_bytes": disk.free,
                "free_percent": round(disk.free / disk.total * 100, 1) if disk.total else 0,
            },
        }

    def report(self) -> dict[str, Any]:
        env = self.collect()
        issues: list[dict] = []
        if env["disk"]["free_percent"] < 10:
            issues.append({
                "severity": "high",
                "title": "磁盘余量不足",
                "detail": f"当前剩余 {env['disk']['free_percent']}%（{env['disk']['free_bytes'] // (1024**3)} GB）",
                "suggested_action": "清理临时文件或扩容磁盘；可先使用 e-worker file_scan/file_clean 整理",
            })
        for tool, label in (("python", "Python"), ("node", "Node.js"), ("go", "Go")):
            if env[tool] is None:
                issues.append({
                    "severity": "medium",
                    "title": f"{label} 未安装或不可用",
                    "detail": f"`{tool}` 命令无法执行",
                    "suggested_action": f"安装 {label} 或将其加入 PATH",
                })
        for p in env["ports"]:
            port = p["port"]
            if port in PORT_CONTRACT:
                issues.append({
                    "severity": "high",
                    "title": f"契约端口 {port} 被占用",
                    "detail": f"{PORT_CONTRACT[port]}；当前占用进程 {p['process']} (PID {p['pid']})",
                    "suggested_action": "按 docs/端口契约.md 处理：违反者让位，禁止改契约端口",
                })
        return {
            "environment": env,
            "issues": issues,
            "note": "建议动作需人工确认后执行，e-worker 不会自动执行任何修复",
        }
