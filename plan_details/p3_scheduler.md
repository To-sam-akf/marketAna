# pn03 定时调度模块 Scheduler 计划

## 摘要

pn03 实现定时扫描调度器，每 N 分钟（默认 5）自动查询 `status=0` 的待处理文章，按 FIFO 顺序取固定批次（默认 20 条），逐条通过回调函数送入 Pipeline。通过数据库行级锁（`FOR UPDATE SKIP LOCKED`）防止多实例并发重复消费。pn03 不直接依赖 pn04-pn07，通过 `PipelineCallback` 函数注入实现解耦，可独立测试。

## 关键改动

- 调度器核心：
  - `Scheduler` 类封装 APScheduler `BackgroundScheduler`，提供 `scan_and_dispatch()` 手动触发 + `start()`/`stop()` 后台运行。
  - 扫描逻辑：调用 `ArticleRepository.get_pending_articles(limit, lock=True)` 取待处理文章，逐条执行 `pipeline_callback(article_id, session)`。
  - 单篇失败不阻塞：每篇文章的异常被独立 catch，失败文章写入 `task_logs` 后继续处理下一篇。

- 并发安全：
  - MySQL/PostgreSQL 上使用 `FOR UPDATE SKIP LOCKED`，两个并发 Scheduler 实例各自获取互不重叠的文章集合。
  - SQLite 测试环境虽然不支持行级锁，但通过事务隔离和顺序执行验证逻辑正确性。

- 扫描级日志：
  - 每次扫描写一条 `task_log(article_id=None, stage="scheduler")`，汇总扫描数、触发数、成功数、失败数。
  - 单篇失败额外写一条 `task_log(article_id=id, stage="scheduler", status="failed")`。

- Pipeline 回调约定：
  - 类型别名 `PipelineCallback = Callable[[int, Session], bool]`，通过函数注入解耦 pn04-pn07。
  - 内置 `noop_callback` 用于测试和占位。

- 配置：
  - `batch_size`（默认 20）和 `poll_interval_seconds`（默认 300）可配置。
  - 时区固定 `Asia/Shanghai`，单实例模式（`coalesce=True, max_instances=1`）。

## 实现顺序

1. 创建 `pn03/` 目录，定义 `ScanResult` 数据类（`models.py`）。
2. 实现 `Scheduler` 类：`scan_and_dispatch()` 核心扫描逻辑。
3. 实现 `start()`/`stop()`：封装 APScheduler 后台定时调度。
4. 实现 `noop_callback`：用于测试的占位回调。
5. 编写测试用例：覆盖空扫描、批次限制、异常容错、并发无重复。
6. 编写 README 和本文档。

## 验证方案

- 调度器扫描逻辑：
  - 构造 25 条 `status=0` 文章，`batch_size=20`，验证单次只取前 20 条。
  - 空数据场景：正常退出，日志记录 "no pending articles"。
  - 两个 Scheduler 实例顺序扫描 15 条文章（A 取 10 条，B 取 5 条），验证文章集合无重叠。

- Pipeline 回调异常处理：
  - 部分回调返回 `False` 或抛异常 → 计数正确 + 失败日志写入。
  - 异常不阻塞后续文章处理。

- 调度器启停：
  - `start()` → `is_running=True`，`stop()` → `is_running=False`。
  - 重复 `start()` 不报错。

- 回归验证：
  - `uv run pytest pn03/ -v` 全部 14 个测试通过。

## 假设与默认选择

- 使用 APScheduler 而非系统 crontab，减少部署依赖。
- 不新增"处理中"状态；并发安全完全依赖数据库行级锁。
- 调度器不直接修改 `articles.status`，状态变更由 pipeline 回调内部负责。
- `POST /api/tasks/run` API 集成留到 pn11 处理；pn03 聚焦调度逻辑本身。
- SQLite 测试环境不支持 `FOR UPDATE SKIP LOCKED`，但测试通过顺序执行验证。

## pn03 定时调度模块实际实现情况

通过阅读和验证本阶段代码，pn03 的调度器核心逻辑、并发安全机制、扫描日志和异常容错已按计划落地。模块独立于 pn04-pn07，通过函数注入实现解耦。

### 已实现的框架

**1. 核心调度器** (`pn03/scheduler.py`)
- **`Scheduler` 类**：封装 APScheduler `BackgroundScheduler`，提供 `scan_and_dispatch()`、`start()`、`stop()` 三个公共方法。
- **`scan_and_dispatch()`**：从 `ArticleRepository.get_pending_articles(limit, lock=True)` 取待处理文章，逐条调用 `pipeline_callback`，catch 单篇异常不阻塞后续处理。
- **扫描级日志**：每次扫描写 `task_log(article_id=None, stage="scheduler")`，记录扫描统计；单篇失败写 `task_log(article_id=id, status="failed")`。
- **`start()`/`stop()`**：注册 interval 定时任务，单实例模式（`coalesce=True, max_instances=1`），时区 `Asia/Shanghai`。

**2. 数据模型** (`pn03/models.py`)
- **`ScanResult`**：记录 `scanned/triggered/succeeded/failed/duration_ms/message`，提供 `summary()` 和 `empty` 属性。

**3. Pipeline 回调约定** (`pn03/scheduler.py`)
- 类型别名 `PipelineCallback = Callable[[int, Session], bool]`，通过函数注入解耦。
- 内置 `noop_callback` 返回 `True` 并写 task_log，用于测试和占位。

**4. 并发安全**
- 调用 `get_pending_articles(lock=True)` → `FOR UPDATE SKIP LOCKED`（MySQL/PG）。
- SQLite 测试环境通过事务隔离和顺序执行验证逻辑。

### 尚未实现（但计划也说不做）

- 未集成到 `POST /api/tasks/run` — 由 pn11 处理。
- 未接入 `back_end/app/main.py` 的 app 生命周期 — pn11 负责。
- `noop_callback` 仅用于测试，pn11 会替换为真实 Pipeline 回调。
- 不修改 `back_end/app/tasks/scheduler.py`（pn01 占位文件）。

### 计划中声明的功能验证

| 验证项 | 状态 |
|--------|------|
| 构造 25 条 PENDING，batch_size=20，单次取 20 条 | ✅ `test_scan_picks_batch_size` |
| 空数据场景正常退出 + 日志 | ✅ `test_scan_empty` |
| 全部成功场景计数正确 | ✅ `test_scan_all_succeed` |
| 部分失败不影响后续处理 | ✅ `test_scan_mixed_results` |
| 回调抛异常被 catch + 失败日志 | ✅ `test_scan_pipeline_exception` |
| 已处理文章不被选中 | ✅ `test_scan_does_not_touch_processed` |
| 两实例扫描无重叠 | ✅ `test_concurrent_scans_no_overlap` |
| 调度器正常启停 | ✅ `test_scheduler_start_stop` |
| 全量测试 | ✅ 14 个测试用例全部通过 |

**总结**：pn03 已完成定时调度模块的核心实现。Scheduler 可自动、稳定、可追踪地拉起文章分析任务，通过行级锁保证并发安全，通过回调注入保持与后续模块的解耦。等待 pn11 接入真实 Pipeline 回调和 API 端点。
