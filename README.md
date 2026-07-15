# MarketANA

## 项目展示
![](./img/marketNAN.jpeg)

## 完整使用流程

### 1. 启动 MySQL

启动本地 MySQL 8.4 数据库，用于后端与流水线集成：

```bash
docker compose up -d mysql
```

检查 MySQL 是否就绪（约需 10-30 秒）：

```bash
docker compose logs -f mysql
```

看到类似 `port: 3306  MySQL Community Server - GPL` 的日志即表示启动完成。

### 2. 初始化数据库表

创建本地环境变量文件（如果还没有）：

```bash
cp .env.example .env
```

初始化数据库表结构：

```bash
uv run python -c "from back_end.app.core.database import create_database_tables; create_database_tables()"
```

或者使用初始化脚本（推荐用模块方式，避免直接运行脚本时找不到 `back_end` 包）：

```bash
uv run python -m scripts.init_db
```

如果数据库是在品种归一化功能上线前创建的，先备份数据库，再执行一次迁移：

```bash
mysql -u marketana -p marketana < scripts/migrate_product_resolution_20260710.sql
```

如需启用独立数据处理流水线的结构化证据和复核队列，再执行一次 canonical 结果迁移：

```bash
mysql -u marketana -p marketana < scripts/migrate_canonical_result.sql
```

启用审核队列的审核人、驳回原因和审核时间字段：

```bash
docker compose exec -T mysql mysql -umarketana -pmarketana_password marketana \
  < scripts/migrate_manual_review_20260713.sql
```

如果已经执行过旧版人工审核迁移，只需补充结构化驳回原因列：

```bash
docker compose exec -T mysql mysql -umarketana -pmarketana_password marketana \
  < scripts/migrate_review_queue_upgrade_20260713.sql
```

异常发布日期可先预览、确认后修复：

```bash
uv run python scripts/repair_publish_times.py
uv run python scripts/repair_publish_times.py --apply
```

### 3. 导入本地数据文件

预览将要插入 `articles` 表的文件：

```bash
uv run python scripts/ingest_files.py --root data --dry-run --limit 20
```

插入最多 20 条新的 PDF/HTML 文章任务：

```bash
uv run python scripts/ingest_files.py --root data --limit 20
```

默认跳过独立图片文件。如需包含图片，请显式指定：

```bash
uv run python scripts/ingest_files.py --root data --limit 20 --include-images
```

导入器默认会将 CSV 报告写入 `data/ingest_report.csv`。它会跳过 `img_folder` 中的资源、`.svg` 文件以及不受支持的文档类型（如 `.doc/.docx`）。

导入成功后，文章以 `status=0`（待处理）状态存入数据库。

### 4. 启动后端服务（含自动数据处理流水线）

```bash
uv run uvicorn back_end.app.main:app --reload --host 0.0.0.0
```

应用启动时自动执行以下操作（仅在配置了 `DATABASE_URL` 时启动数据库和调度器）：

- 创建数据库连接池
- 启动后台 Scheduler 定时调度器
- Scheduler 按 `SCHEDULER_POLL_INTERVAL_SECONDS` 扫描待处理文章；默认值为 **300 秒（5 分钟）**
- 扫描到的文章自动执行完整流水线：**读取 → 清洗 → 品种匹配 → 方向信号提取 → 规则仲裁 → LLM 兜底 → canonical 入库**

Scheduler 使用间隔触发，服务启动后不会立即执行第一次扫描。需要立即处理时，使用下方的 `/api/tasks/run` 接口。

每个阶段的具体含义：

| 阶段 | 功能 | 输入 | 输出 |
|------|------|------|------|
| **readers** | 从源文件（TXT/PDF/HTML/图片）提取统一文档 | 文件 URL | `Document.raw_text` |
| **cleaning** | 去噪、规范化、免责声明和 OCR 数字噪声清理 | `raw_text` | `Document.cleaned_text` |
| **instrument_mapping** | 标准品种与动态别名匹配 | 原文、标题、审核别名 | `product_key` 和匹配跨度 |
| **signals/arbitrator** | 提取带证据的方向信号并进行规则投票 | 原文品种局部窗口 | 规则方向、置信度和证据 |
| **llm** | 仅对冲突或低置信结果做结构化兜底 | 最多 3 条品种相关证据 | LLM 分析结果或审核队列 |
| **canonical/ingestion** | 校验统一结果并写入数据库 | canonical result | 文本、分析结果、审核队列 |

### 5. （可选）启动前端界面

后端和前端需要分别运行。先安装前端依赖：

```bash
npm --prefix front_end install
```

再启动 Vite 开发服务器：

```bash
npm run frontend:dev
```

默认访问地址为 `http://127.0.0.1:5173/`。前端真实请求后端 `http://localhost:8000`，因此需要先启动后端服务。前端使用 Hash 路由，审核队列的实际浏览器地址为 `http://127.0.0.1:5173/#/review-queue`。

### 6. （可选）手动触发处理

根目录的 `main.py` 只是占位入口，执行它只会打印 `Hello from marketana!`，不会触发数据处理。

如果不想等待定时器自动触发，可以用以下任一方式立即执行。

#### 方式 A：通过后端 API 触发

先启动后端服务：

```bash
uv run uvicorn back_end.app.main:app --reload --host 0.0.0.0
```

**处理所有待处理文章：**

```bash
curl -X POST http://localhost:8000/api/tasks/run
```

**处理单篇文章：**

```bash
curl -X POST http://localhost:8000/api/tasks/run \
  -H "Content-Type: application/json" \
  -d '{"article_id": 7}'
```

也可以指定批量上限：

```bash
curl -X POST http://127.0.0.1:8000/api/tasks/run \
  -H "Content-Type: application/json" \
  -d '{"limit": 20}'
```

#### 方式 B：不启动后端，直接从命令行触发数据库任务

处理最多 20 篇待处理文章：

```bash
uv run python -c "from back_end.app.core.database import get_session; from back_end.app.api.tasks import run_task; from back_end.app.api.schemas import TaskRunRequest; s=next(get_session()); print(run_task(TaskRunRequest(limit=20), session=s)); s.close()"
```

处理指定文章，例如 `article_id=1`：

```bash
uv run python -c "from back_end.app.core.database import get_session; from back_end.app.services.pipeline import run_pipeline; s=next(get_session()); ok=run_pipeline(1, s); s.commit(); print({'article_id': 1, 'success': ok}); s.close()"
```

#### 方式 C：单文件手动调试，不写入正式数据库

适合排查某个 PDF/HTML/图片文件的解析、清洗、识别和分段效果：

```bash
uv run python tests/manual_single_file_pipeline.py data/20250401/323354/浙商期货_323354_0.html --output-dir tests/outputs/
```

如果暂时不想调用真实 LLM：

```bash
uv run python tests/manual_single_file_pipeline.py data/20250401/323354/浙商期货_323354_0.html --output-dir tests/outputs --skip-llm
```

输出文件包括：

- `01_raw_text.txt`
- `02_document.json`
- `03_product_matches.json`
- `04_signals.jsonl`
- `05_analysis_results.jsonl`
- `06_review_queue.jsonl`
- `07_summary.json`
- `08_readable_report.md`
- `09_canonical_result.json`

### 7. （可选）查看处理结果

文章处理完成后，可通过 API 查询分析结果：

```bash
# 查看文章列表
curl http://127.0.0.1:8000/api/articles

# 查看公司预测汇总
curl http://127.0.0.1:8000/api/companies

# 查看产品预测汇总
curl http://127.0.0.1:8000/api/products

# 查看趋势热力图
curl http://127.0.0.1:8000/api/trends

# 查看仪表盘统计
curl http://127.0.0.1:8000/api/dashboard/summary
```

### 8. 停止与清理

停止后端服务：按下 `Ctrl+C`

停止 MySQL 容器（保留数据卷，下次启动数据还在）：

```bash
docker compose down
```

停止 MySQL 容器并删除所有数据：

```bash
docker compose down -v
```

---

## 常用命令参考

```bash
docker compose ps          # 查看容器状态
docker compose logs -f mysql  # 查看 MySQL 日志
docker compose down        # 停止并移除容器
```

独立数据处理包也提供批处理、词典构建、评估和隔离检查命令：

```bash
uv run python -m data_proccessing.cli process data/samples --skip-llm
uv run python -m data_proccessing.cli check-isolation
```

## 环境变量说明

默认的 Docker Compose 连接字符串为：

```env
DATABASE_URL=mysql+pymysql://marketana:marketana_password@127.0.0.1:3306/marketana?charset=utf8mb4
```

其他可配置的环境变量参见 `.env.example`。

LLM 调用较慢时可以调整：

```env
LLM_TIMEOUT_SECONDS=300  # 单次请求最多等待秒数
LLM_MAX_RETRIES=2        # 超时/网络错误/5xx/429/空 SSE 后最多重试次数
SCHEDULER_POLL_INTERVAL_SECONDS=300  # 调度扫描间隔，单位：秒
```

`.env` 会覆盖 `.env.example` 的默认值；例如配置为 `30000` 时，调度间隔约为 8 小时 20 分钟。

后端的 `Settings` 会自动读取 `.env`；独立单文件命令使用进程环境变量读取 LLM 配置。如果要让单文件命令调用真实 LLM，需要先导出变量，例如：

```bash
set -a
source .env
set +a
```

如果只想运行规则处理，可以继续使用 `--skip-llm`。未导出 LLM 配置时，单文件命令会自动跳过 LLM，不会报错。

前端的 `/review-queue` 是内部审核工作台，按待审核、已完成、已驳回和处理异常归类文章。审核人员可以驳回误识别、重新解析整篇，或在填写标准品种、方向、理由和证据后创建正式人工结论；已驳回状态不会被流水线重跑覆盖。

`product_resolutions` 和 `product_aliases` 仍提供独立的品种审核 API，但当前 canonical 主流水线不会自动把每个匹配结果写入 `product_resolutions`。

升级编号证据协议后，可先预览仍处于待审核且没有可展示证据的历史文章：

```bash
uv run python -m scripts.reprocess_missing_evidence --dry-run --limit 100
```

确认列表后再显式重跑。默认串行调用模型，可按服务容量调整并发数：

```bash
uv run python -m scripts.reprocess_missing_evidence --apply --limit 100 --concurrency 1
```

如果日志出现 `请求超时`，通常表示模型服务在该时间内没有返回结果。可以适当增大 `LLM_TIMEOUT_SECONDS`，或减小批量处理数量，避免多篇文章连续等待。


```mermaid
flowchart TD
    A[本地研报文件<br/>PDF / HTML / 图片] --> B[scripts/ingest_files.py<br/>导入 articles 表]

    B --> C[(MySQL<br/>articles / article_texts<br/>article_product_segments<br/>analysis_results / analysis_review_queue<br/>task_logs)]

    C --> D[FastAPI 后端<br/>back_end/app/main.py]

    D --> E[back_end/app/tasks/scheduler.py<br/>定时扫描 status=0]
    D --> F[/api/tasks/run<br/>手动触发]

    E --> G[back_end/app/services/pipeline.py<br/>端到端编排]
    F --> G

    G --> H[data_proccessing/readers<br/>解析文件为 raw_text]
    H --> I[data_proccessing/cleaning<br/>清洗为 cleaned_text]
    I --> J[data_proccessing/instrument_mapping<br/>品种匹配与别名审核]
    J --> K[data_proccessing/signals<br/>提取局部方向证据]
    K --> L[data_proccessing/signals/arbitrator<br/>规则投票与置信度]
    L -->|冲突/低置信度| M[data_proccessing/llm<br/>结构化 LLM 兜底]
    L -->|规则可接受| N[data_proccessing/pipeline/canonical<br/>统一结果]
    M --> N
    N --> O

    O --> C

    C --> Q[Repositories<br/>back_end/app/repositories]
    Q --> R[API Routers<br/>articles/products/companies/trends<br/>dashboard/review-queue/results]
    R --> S[Serializers<br/>back_end/app/api/serializers.py]
    S --> T[Vue 前端<br/>front_end/src/views]

    T --> U[产品页 / 公司页 / 趋势热力图<br/>文章详情 / 人工审核]
```
