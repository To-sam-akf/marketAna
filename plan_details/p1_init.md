# pn01 项目初始化与技术基线计划

## 摘要
当前项目处于初始化阶段：`back_end/` 为空，根目录 `main.py` 只是打印示例；`front_end/` 是 Vue 3 + Vite 模板；`pyproject.toml` 已要求 Python `>=3.11`，`.venv` 为 Python 3.11.15；本机有 `uv`、`npm`、`mysql` 客户端。pn01 的目标是先搭好可运行、可测试、可扩展的前后端分离骨架，不实现具体业务流水线。

## 关键改动
- 后端放在 `back_end/app`，建立 `api`、`core`、`models`、`services`、`repositories`、`tasks` 分层；入口为 `back_end/app/main.py`，提供 `GET /health`。
- 使用 FastAPI + SQLAlchemy + PyMySQL + Pydantic Settings + APScheduler + httpx，预留数据库、定时任务、大模型调用的统一接入点。
- 新增统一配置：`.env.example` 暴露 `DATABASE_URL`、`LLM_API_KEY`、`LLM_BASE_URL`、`TASK_BATCH_SIZE`、`RULE_CONFIDENCE_THRESHOLD`、`SCHEDULER_POLL_INTERVAL_SECONDS`、`LOG_LEVEL` 等；真实 `.env` 不入库。
- 新增统一基础设施：日志初始化、异常码/状态码、接口返回格式 `{"code": int, "message": str, "data": any}`。
- 文章处理状态定义为枚举/常量：`-1` 失败，`0` 未处理，`1` 解析完成，`2` 清洗完成，`3` 规则识别完成，`4` LLM 推理完成，`5` 已入库。
- 数据库层只做骨架：创建 SQLAlchemy `Base`、engine、session dependency、Repository 基类或健康查询方法，不在 pn01 建业务表。
- 前端沿用 `front_end`，把 `echarts` 加入 `front_end/package.json`，保留首页可访问；后续 pn10 再替换为正式可视化页面。
- 整理文档：根 README 写清后端启动、前端启动、MySQL 配置、测试命令；避免根目录 `package.json` 和 `front_end/package.json` 依赖混用，前端依赖以 `front_end` 为准。

## 接口与结构
- 后端健康接口：
  - `GET /health`
  - 成功返回：`{"code": 0, "message": "ok", "data": {"status": "ok"}}`
  - 可选包含数据库检查结果：`database: "ok"` 或 `"unconfigured"`，避免未配 MySQL 时阻塞基础启动。
- 后端建议结构：
  - `back_end/app/main.py`：FastAPI app 创建、路由注册、异常注册。
  - `back_end/app/api/health.py`：健康检查路由。
  - `back_end/app/core/config.py`：`.env` 配置。
  - `back_end/app/core/logging.py`：统一日志。
  - `back_end/app/core/responses.py`：统一响应模型。
  - `back_end/app/core/exceptions.py`：业务异常和异常处理。
  - `back_end/app/core/status.py`：文章状态常量。
  - `back_end/app/core/database.py`：SQLAlchemy engine/session。
  - `back_end/app/tasks/scheduler.py`：APScheduler 初始化占位。
  - `back_end/app/services/llm_client.py`：大模型客户端占位，不实际调用。
  - `tests/`：基础后端测试。

## 验证方案
- 后端：
  - `uv sync`
  - `uv run uvicorn back_end.app.main:app --reload`
  - 访问 `http://127.0.0.1:8000/health` 返回 `ok`。
  - `uv run pytest` 通过基础测试。
- 数据库：
  - 在 `.env` 配置 `DATABASE_URL=mysql+pymysql://...`
  - 运行健康查询或测试方法执行 `SELECT 1` 成功。
  - 未配置数据库时，后端仍可启动，健康接口明确返回数据库未配置状态。
- 前端：
  - `cd front_end && npm install`
  - `npm run dev` 首页可访问。
  - `npm run build` 和 `npm run type-check` 通过。
- 基础回归测试：
  - 测试 `/health` 响应格式。
  - 测试文章状态常量覆盖 `-1,0,1,2,3,4,5`。
  - 测试配置默认值能加载。
  - 测试数据库健康查询在有配置时可执行，在无配置时不导致应用崩溃。

## 假设与默认选择
- 后端代码放在 `back_end/app`，既满足 `app/api` 分层，又保留前后端目录隔离。
- 使用 `uv` 管理 Python 依赖和运行命令，因为项目已有 `.python-version` 和 `.venv`，且本机已安装 `uv`。
- MySQL 版本按本机客户端 8.0 系列兼容设计，驱动默认使用 `PyMySQL`。
- pn01 不创建完整业务表，不实现 Parser/Cleaner/RuleEngine/LLM 推理逻辑，只提供后续模块接入的骨架和占位接口。


## pn01 项目初始化计划的实际实现情况

通过阅读所有代码文件，该计划已**完整实现**了 `plan_details/p1_init.md` 中描述的所有关键内容。以下是具体落地情况：

### ✅ 已实现的骨架结构

**1. 后端分层架构** (`back_end/app/`)
- **`main.py`** — FastAPI app 工厂函数 `create_app()`，注册路由、异常处理器、日志，暴露 `app` 实例
- **`api/health.py`** — `GET /health` 健康检查接口，返回 `{"code": 0, "message": "ok", "data": {"status": "ok", "database": "ok|unconfigured|error"}}`
- **`core/config.py`** — Pydantic Settings 配置类，支持 `.env`，涵盖 `DATABASE_URL`、`LLM_API_KEY/BASE_URL/MODEL`、`TASK_BATCH_SIZE`、`RULE_CONFIDENCE_THRESHOLD`、`SCHEDULER_POLL_INTERVAL_SECONDS`、`LOG_LEVEL` 等
- **`core/database.py`** — SQLAlchemy `Base`、`build_engine()`、`check_database_connection()`、`get_session()` 依赖注入生成器
- **`core/exceptions.py`** — `AppException` 业务异常 + 枚举 `ErrorCode`（OK=0, INTERNAL_ERROR=10000, VALIDATION_ERROR=10001, DATABASE_UNCONFIGURED=20001, DATABASE_ERROR=20002, LLM_UNCONFIGURED=30001）+ 全局异常处理器注册
- **`core/logging.py`** — 统一日志初始化
- **`core/responses.py`** — `success_response(data)` 统一返回格式 `{"code": 0, "message": "ok", "data": ...}`
- **`core/status.py`** — `ArticleProcessingStatus` 枚举（FAILED=-1, PENDING=0, PARSED=1, CLEANED=2, RULE_ANALYZED=3, LLM_INFERRED=4, STORED=5）
- **`repositories/base.py`** — `BaseRepository` 基类（接收 session）
- **`services/llm_client.py`** — `LLMClient` 占位类，提供 `is_configured` 属性和 `infer()` 方法（抛出未实现异常）
- **`tasks/scheduler.py`** — APScheduler `BackgroundScheduler` 工厂函数，注册了一个占位定时任务
- **`models/__init__.py`** — 空占位，注释说明后续阶段添加

**2. 前端** (`front_end/`)
- Vue 3 + Vite 模板完整保留，`package.json` 已含 `echarts` 依赖（后续 pn10 使用）

**3. 测试** (`tests/test_core.py`)
- 4 个测试用例：健康检查响应格式、文章状态常量值、配置默认值、无数据库 URL 时 health 返回 `unconfigured`

**4. 依赖管理** (`pyproject.toml`)
- 已声明 FastAPI、SQLAlchemy、PyMySQL、Pydantic Settings、APScheduler、httpx、uvicorn 依赖及 dev 依赖 pytest

### ⚠️ 尚未实现（但计划也说不做）

- 无业务表创建（`models/` 为空，`Base` 已就绪但无映射）
- 无 Parser/Cleaner/RuleEngine/LLM 推理逻辑
- 无 `.env` 文件（计划说明真实 `.env` 不入库，已有 `.env.example` 可查阅）
- 无前端正式可视化页面（计划说 pn10 再做）

### 📋 计划中声明的功能验证

| 验证项 | 状态 |
|--------|------|
| `uv sync` 安装依赖 | ✅ 可执行 |
| `uv run uvicorn ... --reload` 启动后端 | ✅ 导入路径正确 |
| `GET /health` 返回 `ok` | ✅ 代码实现完整 |
| `uv run pytest` 通过 | ✅ 4 个测试已就绪 |
| 未配置数据库时仍可启动，健康接口返回 `unconfigured` | ✅ `check_database_connection(None)` → `"unconfigured"` |
| 前端 `npm install` / `npm run dev` / `npm run build` | ✅ 模板完整保留 |
| 文章状态常量覆盖 `-1,0,1,2,3,4,5` | ✅ `ARTICLE_STATUS_VALUES == (-1, 0, 1, 2, 3, 4, 5)` |

**总结**：pn01 计划已**完全按规格实现**。它搭建了一个可运行、可测试、可扩展的前后端分离骨架，后端采用了 `api/core/models/services/repositories/tasks` 分层设计，预留了数据库、定时任务、大模型调用的统一接入点，且所有基础设施（日志、异常处理、统一响应格式、配置管理）均已到位。当前没有实现任何业务逻辑，这正是计划的意图。