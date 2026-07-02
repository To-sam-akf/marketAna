# MarketANA 三人并行开发计划

本文基于 `plan.md` 的 pn01-pn12 串行计划改写，目标是在 3 名开发者之间并行推进，同时保持数据库模型、后端接口、流水线状态和前端展示口径一致。

## 一、并行原则

1. **先定契约，再分头实现**：数据库表结构、状态码、核心 API response schema、前端 mock 数据必须在第一轮同步完成。
2. **按边界拆分，不按页面或函数抢同一块代码**：每个人负责稳定的目录和模块，减少冲突。
3. **每天集成一次主干**：每天下班前至少合并一次可运行代码，避免到最后集中联调。
4. **所有模块都可单独测试**：Parser、Cleaner、RuleEngine、LLMInfer、Repository、API、前端页面都必须能用 mock 或测试数据独立验证。
5. **状态流转保持唯一口径**：文章状态统一为 `-1, 0, 1, 2, 3, 4, 5`，任何模块不得自定义额外含义。

## 二、人员分工

### 开发者 A：后端基础、数据库、Repository、API

负责范围：

- pn02 数据库模型与状态流转设计
- pn08 数据存储模块 Repository
- pn09 后端 API 模块
- pn12 中后端单元测试、接口测试、数据库说明

主要目录：

- `back_end/app/models`
- `back_end/app/repositories`
- `back_end/app/api`
- `back_end/app/core`
- `tests`

核心交付：

- SQLAlchemy models 和迁移/建表脚本
- Repository DAO 方法
- Dashboard、Articles、Trends、Manual Run、Confirm API
- 统一返回格式和错误处理
- API schema 文档或接口说明

### 开发者 B：文章处理流水线、解析、清洗、规则、LLM、调度

负责范围：

- pn03 定时调度模块 Scheduler
- pn04 文件解析模块 Parser
- pn05 数据清洗模块 Cleaner
- pn06 规则识别模块 RuleEngine
- pn07 LLM 推理模块 LLMInfer
- pn11 流水线联调与异常处理
- pn12 中流水线端到端测试、异常测试

主要目录：

- `back_end/app/services`
- `back_end/app/tasks`
- `back_end/app/core`
- `tests`

核心交付：

- `Pipeline` 编排入口
- PDF、HTML、图片 OCR 解析能力
- 文本清洗规则库
- 品种、方向、置信度规则识别
- LLM prompt、调用封装、JSON 校验和重试
- APScheduler 扫描和防重复消费
- task logs 写入约定和失败恢复策略

### 开发者 C：前端可视化、交互、联调、验收材料

负责范围：

- pn10 前端可视化模块 WebFrontend
- pn12 中前端 build、type-check、页面验收、演示数据
- 协助 pn09 的 API 字段联调

主要目录：

- `front_end/src`
- `front_end/package.json`
- 前端 mock 数据和接口 client

核心交付：

- 首页布局：侧边栏、统计区、趋势图、方向柱状图、文章列表、筛选区
- 文章详情页或详情抽屉
- 待人工确认状态展示
- ECharts 图表封装
- API client 和 mock/真实后端切换
- 空状态、加载状态、错误状态

## 三、阶段计划

### 阶段 0：共同对齐，0.5 天

目标：把并行开发最容易冲突的契约一次定清楚。

共同完成：

1. 确认数据库核心表字段：`articles`、`article_texts`、`analysis_results`、`task_logs`、`manual_confirmations`。
2. 确认统一状态码：`0 未处理`、`1 解析完成`、`2 清洗完成`、`3 规则识别完成`、`4 LLM 推理完成`、`5 已入库`、`-1 失败`。
3. 确认 API response 格式：

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

4. 确认 `direction` 枚举：`看涨`、`看跌`、`中性`。
5. 确认前端需要的 mock 字段和分页格式。

阶段出口：

- A 输出数据库模型草案和 API schema 草案。
- B 输出 Pipeline 阶段接口草案。
- C 输出页面数据需求和 mock JSON。

### 阶段 1：基础闭环，1-2 天

目标：先跑通「数据库 -> API -> 前端 mock 页面」和「单篇文章 pipeline mock」两条最小闭环。

开发者 A：

- 完成 pn02 表模型。
- 完成基础 Repository：文章读取、状态更新、日志写入、结果保存。
- 提供 `/api/dashboard/summary`、`/api/articles`、`/api/articles/{id}` 的 mock/数据库版本。

开发者 B：

- 完成 Pipeline 骨架：`parse -> clean -> rule -> llm -> store`。
- Parser/Cleaner/RuleEngine/LLMInfer 先提供可替换的 stub 实现。
- 完成 Scheduler 扫描 `status = 0` 的文章并调用 Pipeline。

开发者 C：

- 搭建前端主页面结构。
- 使用 mock API 完成统计卡片、趋势图、方向柱状图、文章列表、筛选区。
- 建立 API client，字段名与 A 的 schema 对齐。

阶段出口：

- 后端可以启动，健康检查和基础 API 可访问。
- Scheduler 可扫描测试文章并推进状态。
- 前端可用 mock 数据完整展示首页。

### 阶段 2：业务能力并行深化，2-4 天

目标：各模块从 stub 变成可用实现。

开发者 A：

- 完成 pn08 Repository 幂等写入、事务、统计查询。
- 完成 `/api/trends`、`/api/tasks/run`、`/api/results/{id}/confirm`。
- 完成后端 API 单元测试和接口测试。

开发者 B：

- 完成 pn04 Parser：PDF、HTML、图片 OCR，表格转 Markdown。
- 完成 pn05 Cleaner：编码统一、噪声过滤、空白规范化、正文保留。
- 完成 pn06 RuleEngine：品种词典、方向规则、理由窗口、置信度计算。
- 完成 pn07 LLMInfer：prompt、JSON 解析、字段校验、重试和低置信人工确认。

开发者 C：

- 完成文章详情页/详情抽屉。
- 完成筛选、分页、图表切换、手动刷新、30 秒轮询。
- 完成待人工确认高亮与人工确认入口。
- 前端从 mock API 切换到真实后端联调。

阶段出口：

- 明确观点文章可通过规则直接生成分析结果。
- 模糊观点文章可进入 LLM 推理。
- 前端可以展示真实接口返回的数据。

### 阶段 3：集成、异常、端到端，1-2 天

目标：跑通真实样例文章，并补齐失败、重试、幂等和日志。

开发者 A：

- 检查 Repository 事务一致性和重复保存幂等性。
- 补齐失败文章、人工确认、统计聚合的边界测试。
- 配合 B 处理 Pipeline 中的状态回滚和日志写入。

开发者 B：

- 完成 pn11 全链路编排。
- 对解析失败、清洗失败、OCR 失败、LLM 超时、数据库写入失败进行异常处理。
- 加入并发限制、超时配置、有限重试和阶段耗时统计。

开发者 C：

- 联调空状态、错误状态、加载状态。
- 验证前端展示：今日统计、文章数量、品种趋势、方向统计、待人工确认。
- 准备演示数据和验收截图。

阶段出口：

- 至少 20 篇混合格式样例文章可从 `status = 0` 跑到 `5` 或 `-1`。
- 失败文章能看到失败阶段、错误信息和处理日志。
- 前端可完整演示核心业务流程。

### 阶段 4：验收交付，1 天

目标：形成可演示、可验收、可继续扩展的版本。

共同完成：

1. 后端测试：`uv run pytest`。
2. 前端测试：`npm run build`、`npm run type-check`。
3. 端到端测试：PDF、HTML、PNG 样例各至少 1 篇。
4. 安全检查：`.env` 不入 Git，日志不打印 API Key，数据库账号最小权限。
5. 文档交付：部署说明、接口文档、数据库表结构说明、测试报告、演示数据说明。

阶段出口：

- 系统可本地启动演示。
- 核心页面和接口达到验收要求。
- 后续扩展点清晰：多模型投票、准确率评估、分析师画像、自动日报、风险预警。

## 四、pn 到人员映射

| pn | 模块 | 主负责人 | 协作人 | 可并行性 | 关键依赖 |
| --- | --- | --- | --- | --- | --- |
| pn01 | 项目初始化与技术基线 | 已完成/共同维护 | 全员 | 已完成 | 无 |
| pn02 | 数据库模型与状态流转 | A | B、C | 优先完成 | pn01 |
| pn03 | Scheduler | B | A | 可与 pn04-pn07 并行 | pn02 Repository 接口 |
| pn04 | Parser | B | A | 可独立开发 | article_texts 表 |
| pn05 | Cleaner | B | A | 可独立开发 | Parser 输出格式 |
| pn06 | RuleEngine | B | C | 可独立开发 | cleaned_text |
| pn07 | LLMInfer | B | A | 可独立开发 | cleaned_text、LLM 配置 |
| pn08 | Repository | A | B | 优先完成 | pn02 |
| pn09 | 后端 API | A | C | 可与前端并行 | pn02、pn08、API schema |
| pn10 | 前端可视化 | C | A | 可用 mock 并行 | API schema |
| pn11 | 流水线联调与异常 | B | A、C | 集成阶段 | pn03-pn09 |
| pn12 | 测试、验收与交付 | 全员 | 全员 | 贯穿全程 | 所有模块 |

## 五、接口与数据契约优先级

第一优先级，必须先稳定：

- `GET /health`
- `GET /api/dashboard/summary`
- `GET /api/articles`
- `GET /api/articles/{id}`
- `GET /api/trends`

第二优先级，业务闭环需要：

- `POST /api/tasks/run`
- `POST /api/results/{id}/confirm`

前端最小字段：

```json
{
  "id": 1,
  "title": "文章标题",
  "source": "来源",
  "company": "期货公司",
  "product": "螺纹钢",
  "direction": "看涨",
  "reason": "理由摘要",
  "confidence": 0.82,
  "need_manual_review": false,
  "publish_time": "2026-07-02T09:30:00",
  "status": 5
}
```

## 六、分支与合并建议

建议分支：

- `feature/backend-model-repository-api`：开发者 A
- `feature/pipeline-parser-cleaner-llm`：开发者 B
- `feature/frontend-dashboard`：开发者 C

合并节奏：

1. 每个阶段结束必须合并到主分支。
2. 每次合并前至少运行自己负责模块的测试。
3. 涉及 schema、API 字段、状态码变化时，必须先通知另外两人。
4. 前端 mock 数据必须跟随后端 schema 更新。

## 七、每日协作检查清单

每日开始：

- 确认昨天合并后的主分支可启动。
- 确认当天是否有 schema/API 变更。
- 确认每个人当天的可交付目标。

每日结束：

- 合并或提交当天可运行代码。
- 更新未完成事项和阻塞点。
- 至少跑一次相关测试。
- 记录接口字段变化、数据库字段变化、配置项变化。

## 八、主要风险与应对

1. **数据库模型变动影响全员**：pn02 阶段先冻结第一版字段，后续新增字段走变更说明。
2. **前端等待后端接口**：C 先基于 mock JSON 开发，A 保证真实 API 返回结构兼容 mock。
3. **OCR 和 LLM 环境不稳定**：B 需要保留 stub/mock 模式，保证流水线和测试不依赖外部服务。
4. **规则识别和 LLM 结果不一致**：统一 `direction` 枚举、置信度范围和人工确认标记。
5. **调度重复消费文章**：B 和 A 共同实现处理前锁定或状态占用机制。
6. **最后联调压力过大**：阶段 1 就完成最小闭环，之后每天增量联调。

## 九、推荐验收顺序

1. 启动后端，访问 `/health`。
2. 插入测试文章，确认 `status = 0`。
3. 手动触发 `/api/tasks/run`。
4. 查看文章状态是否推进到 `5` 或 `-1`。
5. 查看 `/api/articles/{id}` 是否包含清洗文本、分析结果、处理日志。
6. 打开前端首页，确认统计卡片、趋势图、方向柱状图、文章列表正常展示。
7. 对低置信结果执行人工确认，确认前端和数据库同步更新。
