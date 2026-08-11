<div align="center">

# e-worker-mcp

**一个本地优先的 MCP 服务器，替你处理日常工作中的琐事。**

把会议纪要变成待办、记录工时、生成日报、整理文件、诊断开发环境——全部通过你的 AI 助手完成，每一次写操作都由人工维护的安全策略把关。

[English](./README_EN.md) · [功能特性](#功能特性) · [快速开始](#快速开始) · [工具清单](#工具清单) · [安全模型](#安全模型) · [架构](#架构)

</div>

---

## 这是什么？

`e-worker-mcp` 是一个 **Model Context Protocol (MCP) 服务器**，为 AI 助手提供一套安全、本地的日常工作工具箱：

- **会议纪要 → 待办**：从会议记录中提取行动项
- **待办管理**：五态状态机覆盖全生命周期
- **工时记录**：按待办记录时长，聚合进报表
- **日报 / 周报**：按类别（工作 / 学习）自动汇总
- **文件整理**：基于规则的整理——只**移动**文件，绝不删除
- **环境诊断**：只读检查并给出可执行的建议

它运行在**纯 stdio 进程**中——没有 HTTP daemon、不开放端口，数据保存在本机本地 SQLite 数据库中。

---

## 功能特性

| 领域 | 能力 |
|------|-----------|
| 📋 待办 | 创建 / 更新 / 状态流转 / 组合过滤查询（状态、分类、关键词、标签） |
| 🗂 分类 | 每个事项标记为 `work` 或 `study`；报表按类分列 |
| 🕐 工时 | 按待办记录工时，支持日期范围查询与总量统计 |
| 📊 报表 | 完成事项 + 工时的日报 / 周报聚合 |
| 📝 会议纪要 | 动作词检测 → 待办草案（日期短语自动转为截止时间） |
| 🗃 文件 | 扫描、规则化整理（仅移动）、清理进 `.trash/` 回收区 |
| 🔍 诊断 | 只读环境采集（工具链版本、PATH、监听端口、磁盘）+ 带建议的问题报告 |
| 🔐 安全 | 白名单 / 黑名单双模式裁决；敏感域（`file.*`、`env.*`）默认需人工批准 |
| 💾 可迁移 | schema 版本化 + 迁移、JSON/CSV 导入导出、存储抽象层 |

---

## 快速开始

### 环境要求

- Python ≥ 3.11
- [uv](https://docs.astral.sh/uv/)（推荐）或 pip

### 安装

```bash
cd e-worker-mcp
uv venv --python 3.12
uv pip install -e ".[dev]"
```

> Windows：`uv pip install --python .venv\Scripts\python.exe -e ".[dev]"`

### 接入 MCP 客户端

在 MCP 客户端配置（Claude Desktop、Kilo、Qoder 等）中添加 stdio server：

```json
{
  "mcpServers": {
    "e-worker-mcp": {
      "command": "/绝对/路径/e-worker-mcp/.venv/bin/python",
      "args": ["-m", "e_worker.server"],
      "cwd": "/绝对/路径/e-worker-mcp"
    }
  }
}
```

> Windows 示例：`command: "D:\\路径\\e-worker-mcp\\.venv\\Scripts\\python.exe"`

### 试试看

接入后直接用自然语言吩咐 AI：

- *「记录一个待办：明天提交报销单（工作）」*
- *「列出我当前所有的待办」*
- *「整理这段会议纪要：……」*
- *「今天给 XX 事项记 2 小时编码工时」*
- *「生成今天的日报」*
- *「扫描一下我的下载目录」*
- *「检查一下开发环境」*

---

## 工具清单

共 24 个工具。每个**写**工具都成对提供 `preview` / `apply`——preview 展示影响（dry-run，无副作用），apply 在裁决通过后执行。

### 待办与报表

| 工具 | 说明 |
|------|-------------|
| `todo_create_preview` / `todo_create_apply` | 创建事项（`category` 必填：`work` / `study`） |
| `todo_update_preview` / `todo_update_apply` | 更新事项 |
| `todo_transition_preview` / `todo_transition_apply` | 状态流转：`inbox → todo → doing → done → archived` |
| `todo_list` / `todo_get` | 组合过滤查询（`status` / `category` / `keyword` / `tag`） |
| `meeting_extract` | 会议纪要 → 待办草案（绝不写库） |
| `time_log_preview` / `time_log_apply` / `time_list` | 工时记录与查询 |
| `report_daily` / `report_weekly` | 日报 / 周报聚合（work / study 分列） |

### 数据迁移

| 工具 | 说明 |
|------|-------------|
| `db_export` | 导出 JSON / CSV（只读；拒绝覆盖已存在文件） |
| `db_import_preview` / `db_import_apply` | 导入（冲突检测 + merge 语义） |

### 文件与环境

| 工具 | 说明 |
|------|-------------|
| `file_scan` | 只读扫描：名称 / 大小 / mtime / 扩展名 |
| `file_organize_preview` / `file_organize_apply` | 规则化整理（仅移动；目标冲突跳过） |
| `file_clean_preview` / `file_clean_apply` | 匹配文件移入 `.trash/`——**绝不**物理删除 |
| `diagnose_collect` | 只读环境采集（版本 / PATH / 端口 / 磁盘） |
| `diagnose_report` | 问题报告 + 建议动作（绝不自动执行） |
| `safety_policy` | 只读：当前 mode / allow_rules / auto_approve——会话开始时先调用 |

---

## 安全模型

所有写操作都经过两阶段流程：

```
preview（dry-run 影响清单）
   → 安全裁决
       → apply（执行）
```

裁决由 `config.json` 驱动——**人工维护，AI 只读**：

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

| 模式 | 策略 |
|------|--------|
| `whitelist`（默认） | **默认拒绝**：操作必须命中 `allow_rules`，否则拒绝并返回缺失规则提示 |
| `blacklist` | **默认放行**：命中 `deny_rules` 的操作被拒绝，其余执行 |

附加保证：

- **`auto_approve` 信任域**：命中 `auto_approve` 的操作（低风险：待办/工时/日报/纪要）**一步直达**，无需逐次确认弹窗；其余操作（如 `file.*`、`env.*`、`db.import`）仍必须先 preview 展示影响并征求用户确认后再 apply
- **敏感域**（`file.*`、`env.*`）在任一模式下，只要规则未明确覆盖，一律升级为**人工批准**
- 会话开始时调用只读工具 `safety_policy` 可查看当前 mode / allow_rules / auto_approve
- 每次裁决都记录到 `logs/e-worker/security.log`（操作、模式、命中规则、决策）
- 规则粒度 = 操作类 × 路径 glob，如 `todo.*`、`file.move|~/notes/**`
- 文件操作**仅移动**；清理进入 `.trash/` 回收区，同名冲突自动加时间戳后缀——代码库中不存在物理删除路径

---

## 数据存储与迁移

- **本地 SQLite（WAL 模式）**：`db/e-worker.db`——无外部服务依赖
- **Schema 演进**：`src/e_worker/migrations/NNN_*.sql` 顺序迁移脚本，启动时在事务内自动应用未执行版本，`schema_version` 表记录，失败即回滚
- **导出 / 导入**：`db_export` → `db_import` 支持跨机迁移与备份（JSON / CSV，含 tags 与 metadata）
- **存储抽象**：所有 SQL 集中在 `storage/repository.py`，业务层不直接写 SQL——未来切换 PostgreSQL 只需替换存储层
- **向前兼容**：`items.metadata` JSON 字段为未来能力预留；新特性通过新增迁移脚本扩展，不动已有表

---

## 架构

```
AI 助手（stdio MCP 客户端）
        │ 工具调用
        ▼
server.py ── 工具注册 + preview/apply 分发
        │
        ├─ 只读工具 → services/* 直接执行
        │
        └─ 写工具（两阶段）
              preview: 安全裁决 → dry-run 影响清单
              apply:   安全复检 → services → storage
        │
        ▼
storage/repository.py ←── 唯一 SQL 访问层
        │
        ▼
db/e-worker.db（SQLite WAL，schema_version 表）
        ▲
        │ 启动时：migrations/NNN_*.sql 事务内应用
        ▼
config.py ←── config.json（人工维护的安全规则）
```

```
src/e_worker/
├── server.py              # MCP 入口，工具注册
├── config.py              # 安全配置加载
├── security.py            # 白名单/黑名单裁决
├── models.py              # Item / TimeEntry 模型，状态机
├── storage/
│   ├── db.py              # 连接、WAL、迁移
│   ├── repository.py      # SQL 层（items, time_entries）
│   └── migrations/        # 001_init.sql, 002_time_entries.sql, ...
├── services/
│   ├── todo_service.py    # 事项 CRUD + 状态机
│   ├── time_service.py    # 工时记录
│   ├── meeting_service.py # 纪要 → 待办草案
│   ├── report_service.py  # 日报/周报聚合
│   ├── file_service.py    # 扫描 / 整理 / 清理（回收区）
│   └── diagnose_service.py# 环境采集与问题报告
└── tools/                 # MCP 工具定义（preview/apply 成对）
```

---

## 测试

```bash
uv run pytest tests/ -v
```

> Windows：`.venv\Scripts\python.exe -m pytest tests/ -v`

覆盖范围：迁移（幂等 / 回滚 / 约束）、双模式裁决、待办状态机、preview/apply 裁决链、纪要提取、工时记录、日报/周报、导出/导入往返、文件整理/清理、环境诊断。

---

## 路线图

- [x] MVP：待办、工时、日报、纪要提取、双模式安全、迁移与导出/导入
- [x] C 组：文件整理（仅移动 + 回收区）与环境诊断（只读）
- [ ] 环境修复自动执行（显式人工批准后；建议动作已就绪）
- [ ] 跨平台诊断（Linux `ss`/`ps` 对齐现有 Windows `netstat`/`tasklist` 实现）

---

## 许可证

本项目尚未指定许可证。使用或分发前请联系维护者。

---

<div align="center">

Python · [MCP SDK](https://github.com/modelcontextprotocol/python-sdk) · SQLite 构建

</div>
