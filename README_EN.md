<div align="center">

# e-worker-mcp

**A local-first MCP server that takes care of your daily work chores.**

Turn meeting notes into todos, track time, generate daily reports, tidy up files, and diagnose your dev environment — all through your AI assistant, with every write operation gated by a human-controlled safety policy.

[中文文档](./README.md) · [Features](#features) · [Quick Start](#quick-start) · [Tools](#tools) · [Security Model](#security-model) · [Architecture](#architecture)

</div>

---

## What is this?

`e-worker-mcp` is a **Model Context Protocol (MCP) server** that gives AI assistants a safe, local toolkit for everyday work tasks:

- **Meeting notes → todos**: extract action items from meeting transcripts
- **Todo management**: full lifecycle with a 5-state state machine
- **Time tracking**: log hours against todos, aggregated into reports
- **Daily / weekly reports**: automatically summarized by category (work / study)
- **File organization**: rule-based sorting that *moves* files — never deletes
- **Environment diagnostics**: read-only inspection with actionable suggestions

It runs as a **pure stdio process** — no HTTP daemon, no open ports, data stays in a local SQLite database on your machine.

---

## Features

| Area | Capability |
|------|-----------|
| 📋 Todo | Create / update / transition / query with filters (status, category, keyword, tag) |
| 🗂 Category | Every item is `work` or `study`; reports break down by category |
| 🕐 Time | Per-todo time entries with date-range queries and totals |
| 📊 Reports | Daily & weekly aggregation of completed items + time |
| 📝 Meeting notes | Action-word detection → todo drafts (date phrases → due dates) |
| 🗃 Files | Scan, rule-based organize (move-only), cleanup into a `.trash/` recovery area |
| 🔍 Diagnostics | Read-only env collection (toolchain versions, PATH, listening ports, disk) + issue report with suggested actions |
| 🔐 Safety | Whitelist / blacklist dual-mode adjudication; sensitive domains (`file.*`, `env.*`) require human approval by default |
| 💾 Portability | Schema versioning + migrations, JSON/CSV export & import, storage abstraction layer |

---

## Quick Start

### Requirements

- Python ≥ 3.11
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Install

```bash
cd e-worker-mcp
uv venv --python 3.12
uv pip install -e ".[dev]"
```

> On Windows: `uv pip install --python .venv\Scripts\python.exe -e ".[dev]"`

### Register in your MCP client

Add a stdio server entry to your MCP client configuration (Claude Desktop, Kilo, Qoder, etc.):

```json
{
  "mcpServers": {
    "e-worker-mcp": {
      "command": "/absolute/path/to/e-worker-mcp/.venv/bin/python",
      "args": ["-m", "e_worker.server"],
      "cwd": "/absolute/path/to/e-worker-mcp"
    }
  }
}
```

> Windows example: `command: "D:\\path\\to\\e-worker-mcp\\.venv\\Scripts\\python.exe"`

### Try it

Once connected, ask your assistant in natural language:

- *"Add a todo: submit the expense report tomorrow (work)"*
- *"Show me my open todos"*
- *"Summarize this meeting: ..."*
- *"Log 2 hours of coding on the report item today"*
- *"Generate today's report"*
- *"Scan my downloads folder"*
- *"Check my dev environment"*

---

## Tools

24 tools in total. Every **write** tool ships as a `preview` / `apply` pair — the preview shows the impact (dry-run, no side effects), the apply executes after adjudication.

### Todos & Reports

| Tool | Description |
|------|-------------|
| `todo_create_preview` / `todo_create_apply` | Create an item (`category` is required: `work` / `study`) |
| `todo_update_preview` / `todo_update_apply` | Update an item |
| `todo_transition_preview` / `todo_transition_apply` | State transition: `inbox → todo → doing → done → archived` |
| `todo_list` / `todo_get` | Query with filters (`status` / `category` / `keyword` / `tag`) |
| `meeting_extract` | Meeting transcript → todo drafts (never writes to DB) |
| `time_log_preview` / `time_log_apply` / `time_list` | Time entry logging & queries |
| `report_daily` / `report_weekly` | Daily / weekly aggregation (work / study breakdown) |

### Data Portability

| Tool | Description |
|------|-------------|
| `db_export` | Export to JSON / CSV (read-only; refuses to overwrite) |
| `db_import_preview` / `db_import_apply` | Import with conflict detection & merge semantics |

### Files & Environment

| Tool | Description |
|------|-------------|
| `file_scan` | Read-only scan: name / size / mtime / extension |
| `file_organize_preview` / `file_organize_apply` | Rule-based sorting (move-only; conflicts skipped) |
| `file_clean_preview` / `file_clean_apply` | Move matched files into `.trash/` — **never** physically deletes |
| `diagnose_collect` | Read-only env collection (versions / PATH / ports / disk) |
| `diagnose_report` | Issue report with suggested actions (never auto-executes) |
| `safety_policy` | Read-only: current `mode` / `allow_rules` / `auto_approve` — call at session start |

---

## Security Model

All write operations go through a two-phase flow:

```
preview (dry-run impact list)
   → safety adjudication
       → apply (execute)
```

Adjudication is driven by `config.json` — **human-maintained, AI-read-only**:

```json
{
  "safety": {
    "mode": "whitelist",
    "auto_approve": ["todo.*", "time.*", "report.*", "meeting.*"],
    "allow_rules": ["todo.*", "meeting.*", "time.*", "report.*"],
    "deny_rules": ["file.delete", "env.modify"]
  },
  "file": {
    "trash_dir": ".trash"
  }
}
```

| Mode | Policy |
|------|--------|
| `whitelist` (default) | **Default-deny**: operation must match `allow_rules`, otherwise rejected with the missing-rule hint |
| `blacklist` | **Default-allow**: operation matching `deny_rules` is rejected, everything else runs |

Additional guarantees:

- **`auto_approve` trust domains**: operations matching `auto_approve` (low-risk: todos, time, reports, meeting notes) execute directly in one step — no per-operation confirmation dialog. Everything else (e.g. `file.*`, `env.*`, `db.import`) still requires a preview + human confirmation before apply
- **Sensitive domains** (`file.*`, `env.*`) escalate to **human approval** whenever rules don't explicitly cover them — in either mode
- Call the read-only `safety_policy` tool at session start to see the current `mode` / `allow_rules` / `auto_approve`
- Every adjudication is logged to `logs/e-worker/security.log` (operation, mode, matched rule, decision)
- Rule granularity is `operation class × path glob`, e.g. `todo.*`, `file.move|~/notes/**`
- File operations are **move-only**; cleanup goes to a `.trash/` recovery area with timestamp suffixing on name collisions — there is no physical deletion path in the codebase

---

## Data Storage & Portability

- **Local SQLite (WAL mode)**: `db/e-worker.db` — no external services
- **Schema evolution**: sequential migrations in `src/e_worker/migrations/NNN_*.sql`, applied automatically in a transaction at startup, recorded in the `schema_version` table; failures roll back
- **Export / import**: `db_export` → `db_import` for cross-machine migration and backups (JSON / CSV, including tags & metadata)
- **Storage abstraction**: all SQL lives in `storage/repository.py`; the business layer never touches SQL directly, so switching to PostgreSQL later only requires replacing the storage layer
- **Forward compatibility**: `items.metadata` JSON field reserves space for future capabilities; new features extend via new migrations without altering existing tables

---

## Architecture

```
AI assistant (stdio MCP client)
        │ tool calls
        ▼
server.py ── tool registration + preview/apply dispatch
        │
        ├─ read-only tools → services/* directly
        │
        └─ write tools (two-phase)
              preview: security adjudication → dry-run impact
              apply:   security re-check → services → storage
        │
        ▼
storage/repository.py ←── the only SQL access layer
        │
        ▼
db/e-worker.db (SQLite WAL, schema_version table)
        ▲
        │ startup: migrations/NNN_*.sql applied in a transaction
        ▼
config.py ←── config.json (human-maintained safety rules)
```

```
src/e_worker/
├── server.py              # MCP entry, tool registration
├── config.py              # safety config loading
├── security.py            # whitelist/blacklist adjudication
├── models.py              # Item / TimeEntry models, state machine
├── storage/
│   ├── db.py              # connection, WAL, migrations
│   ├── repository.py      # SQL layer (items, time_entries)
│   └── migrations/        # 001_init.sql, 002_time_entries.sql, ...
├── services/
│   ├── todo_service.py    # item CRUD + state machine
│   ├── time_service.py    # time entries
│   ├── meeting_service.py # transcript → todo drafts
│   ├── report_service.py  # daily/weekly aggregation
│   ├── file_service.py    # scan / organize / clean (trash)
│   └── diagnose_service.py# env collection & issue report
└── tools/                 # MCP tool definitions (preview/apply pairs)
```

---

## Testing

```bash
uv run pytest tests/ -v
```

> Windows: `.venv\Scripts\python.exe -m pytest tests/ -v`

Coverage: migrations (idempotent / rollback / constraints), dual-mode adjudication, todo state machine, preview/apply chains, meeting extraction, time logging, daily/weekly reports, export/import round-trips, file organize/clean, diagnostics.

---

## Roadmap

- [x] MVP: todos, time, reports, meeting notes, dual-mode safety, migrations & export/import
- [x] C group: file organization (move-only + trash) & environment diagnostics (read-only)
- [ ] Auto-execution of environment fixes behind explicit human approval (suggestions already in place)
- [ ] Cross-platform diagnostics (Linux `ss`/`ps` parity with the current Windows `netstat`/`tasklist` path)

---

## License

No license has been specified for this project yet. Contact the maintainer before using or redistributing the code.

---

<div align="center">

Built with Python · [MCP SDK](https://github.com/modelcontextprotocol/python-sdk) · SQLite

</div>
