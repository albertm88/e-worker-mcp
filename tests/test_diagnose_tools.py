from __future__ import annotations

from e_worker.services.diagnose_service import DiagnoseService
from e_worker.tools import diagnose_tools


def test_collect_structure():
    r = diagnose_tools.diagnose_collect()
    assert set(["python", "node", "go", "path_count", "ports", "disk"]) <= set(r.keys())
    assert r["python"] is None or "version" in r["python"]
    assert r["disk"]["free_percent"] >= 0
    assert isinstance(r["ports"], list)


def test_collect_no_write(tmp_path, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        "e_worker.services.diagnose_service._tool_version",
        lambda t: calls.append(t) or {"version": "1.0", "path": "/x"},
    )
    monkeypatch.setattr(
        "e_worker.services.diagnose_service._listening_ports",
        lambda: calls.append("netstat") or [],
    )
    r = DiagnoseService().collect()
    assert calls  # 只读探测执行过
    assert isinstance(r, dict)


def test_report_empty_issues(monkeypatch):
    svc = DiagnoseService()
    monkeypatch.setattr(
        "e_worker.services.diagnose_service._tool_version",
        lambda t: {"version": "1.0", "path": "/x"},
    )
    monkeypatch.setattr("e_worker.services.diagnose_service._listening_ports", lambda: [])
    monkeypatch.setattr(
        "e_worker.services.diagnose_service.shutil.disk_usage",
        lambda p: type("D", (), {"total": 1000, "free": 500})(),
    )
    r = svc.report()
    assert r["issues"] == []
    assert "人工确认" in r["note"]


def test_report_disk_low(monkeypatch):
    svc = DiagnoseService()
    monkeypatch.setattr(
        "e_worker.services.diagnose_service._tool_version",
        lambda t: {"version": "1.0", "path": "/x"},
    )
    monkeypatch.setattr("e_worker.services.diagnose_service._listening_ports", lambda: [])
    monkeypatch.setattr(
        "e_worker.services.diagnose_service.shutil.disk_usage",
        lambda p: type("D", (), {"total": 1000, "free": 50})(),
    )
    r = svc.report()
    titles = [i["title"] for i in r["issues"]]
    assert "磁盘余量不足" in titles
    issue = next(i for i in r["issues"] if i["title"] == "磁盘余量不足")
    assert issue["suggested_action"]


def test_report_contract_port(monkeypatch):
    svc = DiagnoseService()
    monkeypatch.setattr(
        "e_worker.services.diagnose_service._tool_version",
        lambda t: {"version": "1.0", "path": "/x"},
    )
    monkeypatch.setattr(
        "e_worker.services.diagnose_service._listening_ports",
        lambda: [{"port": 5433, "pid": "123", "process": "evil"}],
    )
    monkeypatch.setattr(
        "e_worker.services.diagnose_service.shutil.disk_usage",
        lambda p: type("D", (), {"total": 1000, "free": 500})(),
    )
    r = svc.report()
    titles = [i["title"] for i in r["issues"]]
    assert any("5433" in t for t in titles)
    issue = next(i for i in r["issues"] if "5433" in i["title"])
    assert "端口契约" in issue["suggested_action"]


def test_report_tool_missing(monkeypatch):
    svc = DiagnoseService()
    monkeypatch.setattr(
        "e_worker.services.diagnose_service._tool_version",
        lambda t: None if t == "node" else {"version": "1.0", "path": "/x"},
    )
    monkeypatch.setattr("e_worker.services.diagnose_service._listening_ports", lambda: [])
    monkeypatch.setattr(
        "e_worker.services.diagnose_service.shutil.disk_usage",
        lambda p: type("D", (), {"total": 1000, "free": 500})(),
    )
    r = svc.report()
    titles = [i["title"] for i in r["issues"]]
    assert any("Node.js" in t for t in titles)
