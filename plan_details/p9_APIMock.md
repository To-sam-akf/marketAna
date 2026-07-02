# 开发者 A：API Mock 交付计划

## Summary

目标是先冻结 pn02、pn09 的前后端契约，输出一份 C 可直接照着开发页面的 API mock 文档。交付物建议为 `docs/api_mock.md`，内容包含数据库核心字段、枚举、统一响应格式、接口参数、mock response、confirm/manual run 请求体。

## Key Contracts

- 统一成功响应：
  ```json
  { "code": 0, "message": "ok", "data": {} }
  ```
- 统一错误响应：
  ```json
  { "code": 10001, "message": "Request validation failed", "data": null, "detail": [] }
  ```
- 状态码固定：`-1` 失败，`0` 未处理，`1` 解析完成，`2` 清洗完成，`3` 规则识别完成，`4` LLM 推理完成，`5` 已入库。
- 方向枚举固定：`看涨`、`看跌`、`中性`。
- 分析方法枚举固定：`rule`、`llm`、`manual`。
- 核心表字段：
  - `articles`：`id/title/source/company/file_url/file_type/publish_time/status/error_msg/created_at/updated_at`
  - `article_texts`：`id/article_id/raw_text/cleaned_text/raw_length/cleaned_length/parser_type/created_at/updated_at`
  - `analysis_results`：`id/article_id/product/direction/reason/confidence/analysis_method/need_manual_review/analysis_time`
  - `task_logs`：`id/article_id/stage/status/message/duration_ms/created_at`
  - `manual_confirmations`：确认前后 `product/direction/reason/confidence`、`confirmed_by/note/confirmed_at`

## API Mock 内容

在 `docs/api_mock.md` 中按以下接口给 C：

- `GET /api/dashboard/summary`

  返回字段：
  ```json
  {
    "code": 0,
    "message": "ok",
    "data": {
      "today_articles": 12,
      "total_articles": 86,
      "success_count": 72,
      "failed_count": 3,
      "success_rate": 0.8372,
      "manual_review_count": 5,
      "direction_distribution": {
        "看涨": 31,
        "看跌": 24,
        "中性": 17
      }
    }
  }
  ```

- `GET /api/articles?product=豆粕&company=甲期货&direction=看涨&status=5&page=1&page_size=20`

  返回字段：
  ```json
  {
    "code": 0,
    "message": "ok",
    "data": {
      "items": [
        {
          "id": 101,
          "title": "豆粕短期需求改善",
          "source": "日报",
          "company": "甲期货",
          "file_url": "/files/soymeal.html",
          "file_type": "html",
          "publish_time": "2026-07-02T09:00:00",
          "status": 5,
          "error_msg": null,
          "created_at": "2026-07-02T09:05:00",
          "updated_at": "2026-07-02T09:08:00",
          "product": "豆粕",
          "direction": "看涨",
          "reason": "下游补库增加，库存压力缓解。",
          "confidence": 0.82,
          "need_manual_review": false,
          "analysis_time": "2026-07-02T09:08:00"
        }
      ],
      "total": 1,
      "page": 1,
      "page_size": 20
    }
  }
  ```

- `GET /api/articles/{article_id}`

  返回 `article/text/analysis_result/task_logs/manual_confirmations`：
  ```json
  {
    "code": 0,
    "message": "ok",
    "data": {
      "article": { "id": 101, "title": "豆粕短期需求改善", "status": 5, "product": "豆粕", "direction": "看涨", "confidence": 0.82 },
      "text": { "raw_text": "原始正文...", "cleaned_text": "清洗后正文...", "raw_length": 2034, "cleaned_length": 1680, "parser_type": "html" },
      "analysis_result": { "id": 201, "article_id": 101, "product": "豆粕", "direction": "看涨", "reason": "下游补库增加，库存压力缓解。", "confidence": 0.82, "analysis_method": "llm", "need_manual_review": false, "analysis_time": "2026-07-02T09:08:00" },
      "task_logs": [{ "id": 1, "stage": "llm", "status": "success", "message": "ok", "duration_ms": 430, "created_at": "2026-07-02T09:08:00" }],
      "manual_confirmations": []
    }
  }
  ```

- `GET /api/trends?product=豆粕&start_time=2026-07-01T00:00:00&end_time=2026-07-02T23:59:59`

  ```json
  {
    "code": 0,
    "message": "ok",
    "data": {
      "items": [
        { "date": "2026-07-01", "product": "豆粕", "direction": "看涨", "count": 4 },
        { "date": "2026-07-01", "product": "豆粕", "direction": "看跌", "count": 1 },
        { "date": "2026-07-02", "product": "豆粕", "direction": "中性", "count": 2 }
      ]
    }
  }
  ```

- `POST /api/tasks/run`

  请求体：
  ```json
  { "article_id": null, "limit": 20 }
  ```

  响应：
  ```json
  {
    "code": 0,
    "message": "ok",
    "data": {
      "triggered": true,
      "article_id": null,
      "limit": 20,
      "message": "Manual pipeline run submitted"
    }
  }
  ```

- `POST /api/results/{result_id}/confirm`

  请求体：
  ```json
  {
    "product": "豆粕",
    "direction": "看涨",
    "reason": "人工确认需求改善。",
    "confidence": 0.9,
    "confirmed_by": "analyst",
    "note": "修正低置信 LLM 结果"
  }
  ```

  响应：
  ```json
  {
    "code": 0,
    "message": "ok",
    "data": {
      "id": 301,
      "article_id": 101,
      "original_product": "豆粕",
      "original_direction": "中性",
      "original_reason": "震荡整理。",
      "original_confidence": 0.45,
      "confirmed_product": "豆粕",
      "confirmed_direction": "看涨",
      "confirmed_reason": "人工确认需求改善。",
      "confirmed_confidence": 0.9,
      "confirmed_by": "analyst",
      "note": "修正低置信 LLM 结果",
      "confirmed_at": "2026-07-02T10:00:00"
    }
  }
  ```

## Test Plan

- 用现有后端字段对照 mock 文档，确保字段名和真实 serializer 一致。
- 覆盖 3 类页面场景：正常数据、空列表、待人工确认。
- 确认 C 可据此定义前端类型：`ApiResponse<T>`、`DashboardSummary`、`ArticleListItem`、`ArticleDetail`、`TrendItem`、`ManualRunResult`、`ManualConfirmation`。
- 联调前冻结字段；之后如修改字段名、枚举、分页结构，A 必须同步 B/C。

## Assumptions

- 第一版分析结果采用“一篇文章一条当前有效结果”，重跑覆盖旧结果，不做版本历史。
- `POST /api/tasks/run` 在 B 接入流水线前可以返回占位结果，但字段结构保持不变。
- 前端展示置信度时按 `0-1` 小数处理，页面可自行格式化为百分比。

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
