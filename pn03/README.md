# pn03 定时调度模块 Scheduler

## 概述

定时扫描 `status=0` 的待处理文章，按录入时间升序（FIFO）取固定批次，逐条触发 Pipeline，通过行级锁（`FOR UPDATE SKIP LOCKED`）防止并发重复消费。

## 目录结构

```
pn03/
├── __init__.py          # 包入口，导出 Scheduler, ScanResult
├── scheduler.py         # 核心调度器类（scan_and_dispatch + start/stop）
├── models.py            # ScanResult 数据类
├── test_scheduler.py    # 单元测试（14 个用例）
└── README.md            # 本文档
```

## 使用方法

```python
from pn03 import Scheduler, ScanResult
from back_end.app.core.database import get_session

# 定义 pipeline 回调（pn11 会提供真实实现）
def my_pipeline(article_id: int, session) -> bool:
    # pn04 → pn05 → pn06 → pn07 的完整流程
    return True

# 创建调度器
scheduler = Scheduler(
    session_factory=lambda: next(get_session()),
    pipeline_callback=my_pipeline,
    batch_size=20,
    poll_interval_seconds=300,
)

# 启动后台调度（每 5 分钟自动扫描）
scheduler.start()

# 手动触发一次扫描
result: ScanResult = scheduler.scan_and_dispatch()
print(result.summary())  # [350ms] 扫描=20 触发=20 成功=18 失败=2

# 停止调度器
scheduler.stop()
```

## Pipeline 回调约定

```python
PipelineCallback = Callable[[int, Session], bool]
# article_id: 待处理文章 ID
# session: 当前 SQLAlchemy Session（调用方管理事务）
# 返回: True=成功, False=失败, raise Exception=失败
```

回调内部应自行处理状态更新和日志记录。pn03 只负责调度和分发，不关心各 pn 的具体实现。

## 并发安全

- **MySQL/PostgreSQL**：`SELECT ... WHERE status=0 FOR UPDATE SKIP LOCKED` 保证每个实例获取互不重叠的文章集合
- **SQLite**（测试环境）：`FOR UPDATE` 不支持但无副作用，测试通过顺序执行验证逻辑

## 状态流转

调度器本身不修改文章状态（由 pipeline 回调内部处理），但会写入 `task_logs`：
- 扫描级日志：`article_id=NULL, stage="scheduler"`
- 失败日志：`article_id=文章ID, stage="scheduler", status="failed"`

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `batch_size` | 20 | 每次扫描最大文章数 |
| `poll_interval_seconds` | 300 | 定时扫描间隔（秒） |
| `timezone` | Asia/Shanghai | 调度器时区 |

## 测试

```bash
uv run pytest pn03/ -v
```
