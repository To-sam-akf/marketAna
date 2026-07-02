# 开发者 A 计划：数据库模型、Repository 与后端 API

## Summary

开发者 A 负责把后端数据底座先稳定下来：用现有 FastAPI + SQLAlchemy 2.0 基线建立核心表模型、轻量建表脚本、Repository 数据访问层和前端/流水线需要的 REST API。第一版采用“每篇文章一条当前有效分析结果”的幂等策略，重跑时覆盖更新，不保留多版本历史。

## Key Changes

- 数据模型：
  - `articles`：文章主表，包含 `id/title/source/company/file_url/file_type/publish_time/status/error_msg/created_at/updated_at`。
  - `article_texts`：解析与清洗文本表，`article_id` 唯一关联文章，保存 `raw_text/cleaned_text/raw_length/cleaned_length/parser_type`。
  - `analysis_results`：分析结果表，`article_id` 唯一，保存 `product/direction/reason/confidence/analysis_method/need_manual_review/analysis_time`。
  - `task_logs`：流水线日志表，记录 `article_id/stage/status/message/duration_ms/created_at`。
  - `manual_confirmations`：人工确认表，记录确认前后结果、确认人、备注和确认时间，用于低置信度结果修正审计。

- 状态规则：
  - 继续使用现有 `ArticleProcessingStatus`：`-1, 0, 1, 2, 3, 4, 5`。
  - Repository 提供统一状态更新入口，正常流转为 `0 -> 1 -> 2 -> 3 -> 4 -> 5`，任意阶段可失败为 `-1` 并写入 `error_msg` 和 `task_logs`。
  - 不新增“处理中”状态；批量领取待处理文章时使用事务 + `SELECT ... FOR UPDATE SKIP LOCKED` 防止 Scheduler 并发重复消费。

- Repository：
  - 新增文章读取、文本保存、分析结果保存、状态更新、日志写入、人工确认、统计聚合方法。
  - `save_analysis_result` 对同一 `article_id` 执行 upsert/覆盖更新，保证重跑不产生重复有效统计。
  - 关键写操作使用事务，保证“结果、状态、日志”一致提交或回滚。
  - 查询接口支持前端筛选：品种、期货公司、方向、状态、时间范围、关键词、分页。

- API：
  - `GET /api/dashboard/summary`：返回今日文章数、成功数、失败数、成功率、待人工确认数、方向分布。
  - `GET /api/articles`：分页文章列表，支持 `product/company/direction/status/start_time/end_time/keyword/page/page_size`。
  - `GET /api/articles/{id}`：返回文章基础信息、解析文本、清洗文本、当前分析结果、处理日志、人工确认记录。
  - `GET /api/trends`：按日期和品种聚合看涨/看跌/中性数量。
  - `POST /api/tasks/run`：提供手动触发入口，先定义契约；流水线服务由开发者 B 接入。
  - `POST /api/results/{id}/confirm`：人工修正品种、方向、理由、置信度，并将结果标记为已确认。
  - 所有接口继续使用现有统一格式：`{"code": 0, "message": "ok", "data": ...}`。

## Implementation Order

1. 在 `back_end/app/models` 增加 SQLAlchemy ORM 模型，并补齐 `models/__init__.py` 导出。
2. 增加轻量初始化脚本，基于 `Base.metadata.create_all()` 创建表；不引入 Alembic。
3. 增加 Repository 类，先完成流水线最小依赖：`get_pending_articles`、`save_raw_text`、`save_cleaned_text`、`save_analysis_result`、`update_status`、`save_task_log`。
4. 补齐统计、详情、人工确认相关 Repository 方法。
5. 增加 API 路由并在 `create_app()` 注册 `/api` 下的 dashboard、articles、trends、tasks、results。
6. 与开发者 B/C 对齐最终 response schema，保证前端 mock 字段和真实 API 字段一致。

## Test Plan

- 模型/建表测试：
  - 使用 SQLite 内存库或临时库创建全部表，验证字段、外键、唯一约束和核心索引存在。
  - 验证 `articles.status` 只接受既定状态值。

- Repository 测试：
  - 插入模拟文章，按 `0 -> 1 -> 2 -> 3 -> 4 -> 5` 更新状态。
  - 任意阶段失败时确认 `status = -1`、`error_msg` 和 `task_logs` 同时写入。
  - 重复保存同一 `article_id` 的分析结果，确认只保留一条当前有效结果。
  - 验证文章列表筛选、分页、详情查询、趋势聚合和 dashboard 聚合结果。

- API 测试：
  - 覆盖正常查询、空结果、非法参数、分页边界和不存在的文章 ID。
  - 验证 `/api/results/{id}/confirm` 会更新当前分析结果并新增人工确认记录。
  - 保留并运行现有 `tests/test_core.py`，确保健康检查、配置和状态枚举不回归。

## Assumptions

- 第一版不引入 Alembic，采用 SQLAlchemy models + `create_all` 初始化脚本满足课程/项目交付速度。
- `analysis_results.article_id` 采用唯一约束，重跑覆盖当前结果，不做版本历史。
- `direction` 固定为 `看涨`、`看跌`、`中性`；`analysis_method` 固定为 `rule`、`llm`、`manual`。
- 人工确认会更新当前分析结果，并额外写入 `manual_confirmations` 审计记录。
- `POST /api/tasks/run` 的实际流水线执行由开发者 B 接入；A 先提供稳定 API 契约和可测试占位接口。

## pn02  数据库模型与状态流转设计实际实现情况

通过阅读和验证本阶段代码，pn02 相关的数据模型、状态流转、Repository 基础能力和后端 API 契约已经按计划落地。当前实现不仅完成了 pn02 的数据库模型设计，也提前覆盖了开发者 A 在 pn08、pn09 中需要交付的部分基础 Repository 与 API 能力，为后续 Scheduler、Parser、Cleaner、RuleEngine、LLMInfer 和前端联调提供了稳定数据底座。

### 已实现的框架

**1. 数据库 ORM 模型** (`back_end/app/models/article.py`)
- **`Article` / `articles`**：文章主表，包含标题、来源、期货公司、文件地址、文件类型、发布时间、处理状态、错误信息、创建时间和更新时间。
- **`ArticleText` / `article_texts`**：文章解析与清洗结果表，通过 `article_id` 唯一关联文章，保存 `raw_text`、`cleaned_text`、文本长度和解析器类型。
- **`AnalysisResult` / `analysis_results`**：趋势分析结果表，通过 `article_id` 唯一关联文章，实现“同一文章只保留当前有效分析结果”的幂等策略。
- **`TaskLog` / `task_logs`**：流水线执行日志表，保存文章、阶段、执行状态、消息、耗时和创建时间。
- **`ManualConfirmation` / `manual_confirmations`**：人工确认记录表，保存确认前后的品种、方向、理由、置信度、确认人、备注和确认时间。

**2. 字段约束、索引与状态约束**
- `articles.status` 使用 `CheckConstraint` 限制为 `-1, 0, 1, 2, 3, 4, 5`，与 `ArticleProcessingStatus` 保持一致。
- `analysis_results.direction` 限制为 `看涨`、`看跌`、`中性`。
- `analysis_results.analysis_method` 限制为 `rule`、`llm`、`manual`。
- `confidence` 和 `confirmed_confidence` 限制在 `0 <= value <= 1`。
- 对 `article_id`、`status`、`company`、`publish_time`、`product`、`direction`、`analysis_time`、日志创建时间等关键查询字段建立了索引或唯一约束。

**3. 轻量建表能力**
- `back_end/app/core/database.py` 新增 `create_database_tables(engine=None)`，通过 `Base.metadata.create_all()` 创建所有 ORM 表。
- `scripts/init_db.py` 提供命令行初始化入口，适合第一版课程项目和本地 MySQL 快速建表。
- 本阶段未引入 Alembic，符合计划中“轻量脚本优先”的假设。

**4. Repository 数据访问层** (`back_end/app/repositories/articles.py`)
- 新增 `ArticleRepository`，封装文章创建、查询、状态更新、文本保存、分析结果保存、日志写入、失败标记、人工确认和统计聚合。
- 流水线最小依赖已提供：`get_pending_articles()`、`save_raw_text()`、`save_cleaned_text()`、`save_analysis_result()`、`update_status()`、`save_task_log()`。
- `save_analysis_result()` 对同一 `article_id` 采用覆盖更新策略，避免重复统计。
- `mark_failed()` 会同时更新文章 `status = -1`、写入 `error_msg` 并新增失败阶段日志。
- `get_pending_articles(lock=True)` 在 MySQL/PostgreSQL 下使用 `FOR UPDATE SKIP LOCKED`，为后续 Scheduler 并发防重复消费预留能力。

**5. 后端 API 路由**
- **`GET /api/dashboard/summary`**：返回文章总数、今日文章数、成功数、失败数、成功率、待人工确认数和方向分布。
- **`GET /api/articles`**：支持按品种、期货公司、方向、状态、时间范围、关键词分页查询文章列表。
- **`GET /api/articles/{article_id}`**：返回文章基础信息、解析/清洗文本、当前分析结果、流水线日志和人工确认记录。
- **`GET /api/trends`**：按日期、品种和方向聚合趋势数据。
- **`POST /api/tasks/run`**：提供手动触发任务的占位契约，实际 Pipeline 执行留给开发者 B 接入。
- **`POST /api/results/{result_id}/confirm`**：支持人工确认和修正分析结果，并写入确认审计记录。
- 所有接口继续使用统一响应格式：`{"code": 0, "message": "ok", "data": ...}`。

**6. API 序列化与请求模型**
- `back_end/app/api/schemas.py` 定义 `ConfirmResultRequest`、`TaskRunRequest` 等请求模型。
- `back_end/app/api/serializers.py` 统一序列化文章列表、文章详情、分析结果、日志和人工确认记录。
- `back_end/app/main.py` 已注册 dashboard、articles、trends、tasks、results 路由。

###  尚未实现（但计划也说不做）

- 未引入 Alembic 迁移体系；当前使用 SQLAlchemy `create_all()` 轻量建表。
- `POST /api/tasks/run` 尚未真实触发 Scheduler/Pipeline，仅返回稳定占位响应，等待开发者 B 接入。
- Parser、Cleaner、RuleEngine、LLMInfer 的真实业务逻辑不属于 pn02，由后续模块实现。
- 当前没有分析结果版本历史；重跑文章会覆盖 `analysis_results` 当前记录，这是本阶段明确采用的幂等策略。
- 没有新增“处理中”状态；并发领取通过数据库锁能力预留，而不是扩展状态码。

### 计划中声明的功能验证

| 验证项 | 状态 |
|--------|------|
| 使用 ORM 创建所有核心表 | ✅ `create_database_tables()` 已实现，测试使用 SQLite 内存库完成建表 |
| 核心表字段、外键、唯一约束存在 | ✅ `tests/test_backend_data.py` 覆盖表存在和 `analysis_results.article_id` 唯一约束 |
| `articles.status` 只接受 `-1,0,1,2,3,4,5` | ✅ 测试非法状态会触发数据库约束错误 |
| 文章状态可按 `0 -> 1 -> 2 -> 3 -> 4 -> 5` 流转 | ✅ Repository 测试覆盖解析、清洗、规则、LLM、入库状态更新 |
| 任一阶段失败标记 `-1` 并记录错误 | ✅ `mark_failed()` 测试确认 `status=-1`、`error_msg`、`task_logs` 同时写入 |
| `save_analysis_result()` 幂等覆盖结果 | ✅ 重复保存同一文章结果后仍只有一条有效 `analysis_results` 记录 |
| 文章筛选、分页、统计、趋势聚合可用 | ✅ Repository 测试覆盖 `list_articles()`、`get_dashboard_summary()`、`get_trends()` |
| 人工确认会更新结果并写入审计记录 | ✅ API handler 测试覆盖 `/api/results/{id}/confirm` 对应逻辑 |
| 保留 pn01 基础测试不回归 | ✅ `tests/test_core.py` 继续通过 |
| 全量测试 | ✅ `UV_CACHE_DIR=/tmp/uv-cache uv run pytest`，8 个测试全部通过 |

**总结**：pn02 已完成核心数据模型和状态流转设计，并实现了可运行、可测试的数据访问层与 API 契约。当前数据库结构能够支撑“原始文章读取 -> 文本解析/清洗 -> 规则识别 -> LLM 推理 -> 分析结果入库 -> 人工确认”的完整状态追踪。后续开发者 B 可以直接通过 `ArticleRepository` 接入流水线，开发者 C 可以基于 `/api/articles`、`/api/dashboard/summary`、`/api/trends` 和 `/api/results/{id}/confirm` 进行前端联调。
