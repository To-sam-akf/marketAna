# MarketANA 三人简化并行开发计划

本文基于 `plan.md` 的 pn01-pn12 拆分为 3 条完整功能线。目标是减少沟通成本，避免一个功能被多人拆开做：每个人负责一块相对完整的能力，最后通过稳定接口集成。

## 一、简化原则

1. **一个功能一个负责人**：数据库和 API 归 A，流水线归 B，前端归 C。
2. **只在接口契约处对齐**：三人只需要对齐数据库字段、API 返回结构、状态码和方向枚举。
3. **允许 mock 先行**：B 可以用 A 提供的 Repository 接口 mock 开发，C 可以用 A 提供的 API mock 开发。
4. **阶段少而清晰**：先定契约，再各自完成主功能，最后集中联调验收。
5. **状态码统一不变**：文章状态固定为 `0, 1, 2, 3, 4, 5, -1`，任何模块不得另起含义。

## 二、人员分工

### 开发者 A：后端数据与 API

负责 pn：

- pn02 数据库模型与状态流转设计
- pn08 数据存储模块 Repository
- pn09 后端 API 模块
- pn12 中的后端测试、接口文档、数据库说明

完整负责的功能：

- 数据库表结构
- SQLAlchemy models
- Repository 数据访问层
- Dashboard、Articles、Trends、Manual Run、Confirm API
- 后端接口测试
- 数据库和接口文档

主要目录：

- `back_end/app/models`
- `back_end/app/repositories`
- `back_end/app/api`
- `tests`

### 开发者 B：文章处理流水线

负责 pn：

- pn03 定时调度模块 Scheduler
- pn04 文件解析模块 Parser
- pn05 数据清洗模块 Cleaner
- pn06 规则识别模块 RuleEngine
- pn07 LLM 推理模块 LLMInfer
- pn11 流水线联调与异常处理
- pn12 中的流水线测试、异常测试、端到端测试

完整负责的功能：

- 定时扫描待处理文章
- 文件解析
- 文本清洗
- 规则识别
- LLM 推理
- Pipeline 编排
- 失败重试、日志、耗时统计
- 流水线端到端测试

主要目录：

- `back_end/app/services`
- `back_end/app/tasks`
- `tests`

### 开发者 C：前端可视化与演示

负责 pn：

- pn10 前端可视化模块 WebFrontend
- pn12 中的前端 build、type-check、页面验收、演示材料

完整负责的功能：

- 首页统计
- 趋势图和方向柱状图
- 文章列表和筛选
- 文章详情
- 待人工确认提示和确认入口
- 前端 API client
- 前端验收和演示材料

主要目录：

- `front_end/src`
- `front_end/package.json`

## 三、阶段计划

### 阶段 0：接口契约对齐，0.5 天

目标：只对齐会影响三个人并行开发的公共契约，其他实现细节各自负责。

开发者 A：pn02、pn09

- 定义数据库核心表字段：`articles`、`article_texts`、`analysis_results`、`task_logs`、`manual_confirmations`。
- 定义统一 API response 格式：`code`、`message`、`data`。
- 定义前端需要的接口字段：summary、articles、article detail、trends、manual run、confirm。
- 输出一份 API mock 返回示例，供 C 直接开发页面。

开发者 B：pn03-pn07、pn11

- 确认 Pipeline 只依赖 A 的 Repository 方法，不直接写 SQL。
- 确认流水线阶段：解析、清洗、规则识别、LLM 推理、入库。
- 确认每个阶段写入的状态码和 task log 字段。
- 如果 A 的 Repository 未完成，先使用本地 mock Repository 开发。

开发者 C：pn10

- 基于 A 的 API mock 确认页面字段够用。
- 准备前端 mock 数据。
- 确认首页、列表、详情、图表和人工确认入口的页面范围。

阶段出口：

- 状态码、方向枚举、API 返回结构冻结第一版。
- A 有 API mock 示例。
- B 有 Pipeline 输入输出约定。
- C 可以不等待后端，直接用 mock 开发页面。

整体验证方法：

- 三人共同过一遍 API mock。
- 确认 `direction` 只使用 `看涨`、`看跌`、`中性`。
- 确认状态只使用 `0, 1, 2, 3, 4, 5, -1`。

### 阶段 1：各自完成主功能，2-4 天

目标：三个人各自完成自己负责的完整功能，尽量不互相阻塞。

开发者 A：pn02、pn08、pn09

- pn02：完成数据库模型、字段、索引和状态流转。
- pn08：完成 Repository：待处理文章读取、文本保存、分析结果保存、状态更新、日志写入、统计查询。
- pn08：保证分析结果写入幂等，同一文章重跑不会重复统计。
- pn09：完成 Dashboard、Articles、Article Detail、Trends、Manual Run、Confirm API。
- pn09：所有 API 返回统一 JSON 格式。
- pn09：提供接口测试数据，方便 C 联调。

开发者 B：pn03、pn04、pn05、pn06、pn07、pn11

- pn03：完成 Scheduler，定时扫描 `status = 0` 的文章，并避免重复消费。
- pn04：完成 PDF、HTML、图片解析，表格内容尽量转为 Markdown。
- pn05：完成文本清洗，去除广告、免责声明、异常空白和无效噪声。
- pn06：完成规则识别，输出品种、方向、理由、置信度。
- pn07：完成 LLM 推理，处理 JSON 解析、字段校验、重试和低置信人工确认标记。
- pn11：完成 Pipeline 编排，每个阶段写入 task logs，失败统一标记 `-1`。

开发者 C：pn10

- pn10：完成首页布局：侧边栏、统计卡片、趋势图、方向柱状图、文章列表、筛选区。
- pn10：完成文章详情页或详情抽屉。
- pn10：完成筛选、搜索、分页、图表切换、手动刷新、30 秒轮询。
- pn10：完成待人工确认状态展示和确认入口。
- pn10：先使用 mock API 开发，A 的真实 API 可用后切换。
- pn10：处理加载、空状态、错误状态。

阶段出口：

- A：后端数据模型、Repository、API 基本完成。
- B：文章从待处理到分析结果的流水线基本完成。
- C：前端页面可用 mock 数据完整展示。

整体验证方法：

- A 运行后端 API 测试，确认核心接口可返回数据。
- B 使用样例文章跑 Pipeline，确认状态能推进到 `5` 或 `-1`。
- C 运行 `npm run build` 和 `npm run type-check`。

### 阶段 2：集中联调，1-2 天

目标：把 A 的 API、B 的流水线、C 的页面接起来，修字段不一致和状态流转问题。

开发者 A：pn08、pn09、pn12

- 用真实 Repository 支撑 B 的 Pipeline。
- 检查 API 返回字段是否满足 C 的页面展示。
- 修复统计聚合、分页、筛选、详情和人工确认接口问题。
- 补齐后端接口测试。

开发者 B：pn03-pn07、pn11、pn12

- 接入 A 的真实 Repository。
- 使用真实数据库样例跑完整 Pipeline。
- 修复解析失败、清洗失败、LLM 超时、重复消费、状态回滚等问题。
- 输出 task logs，供 A 的详情接口和 C 的详情页展示。

开发者 C：pn10、pn12

- 前端从 mock API 切换到真实 API。
- 联调首页统计、趋势图、文章列表、详情页、人工确认。
- 修复字段映射、分页、筛选、空状态和错误状态。
- 准备演示数据和页面验收截图。

阶段出口：

- 真实文章可以从 `status = 0` 跑到 `5` 或 `-1`。
- 前端能展示真实接口返回的统计、趋势、文章列表和详情。
- 人工确认流程可以从前端提交到后端。

整体验证方法：

- 插入至少 10 篇样例文章，包含 PDF、HTML、图片和模糊观点文章。
- 手动触发 `/api/tasks/run` 或 Scheduler。
- 检查 `/api/articles`、`/api/articles/{id}`、`/api/trends` 是否和前端展示一致。
- 对一条低置信结果执行人工确认，确认数据库和页面同步更新。

### 阶段 3：验收交付，1 天

目标：完成 pn12，形成可演示、可验收的版本。

开发者 A：pn12

- 运行后端测试：`uv run pytest`。
- 整理数据库表结构说明。
- 整理接口文档。
- 检查 `.env` 不入 Git，日志不暴露密钥。

开发者 B：pn12

- 使用混合格式样例跑端到端测试。
- 验证失败重试、任务日志、耗时统计和重复消费控制。
- 整理流水线说明和异常处理说明。

开发者 C：pn12

- 运行前端构建和类型检查：`npm run build`、`npm run type-check`。
- 准备演示脚本、演示数据和页面截图。
- 验证页面能展示今日统计、文章数量、品种趋势、方向统计和待人工确认结果。

阶段出口：

- 后端测试通过。
- 前端 build 和 type-check 通过。
- 至少完成一轮真实样例文章端到端演示。
- 输出数据库说明、接口文档、测试报告、演示材料。

整体验证方法：

- 后端执行 `uv run pytest`。
- 前端执行 `npm run build` 和 `npm run type-check`。
- 使用 PDF、HTML、PNG 样例各至少 1 篇，从 `status = 0` 跑到前端可视化结果。

## 四、pn 到人员映射

| pn | 模块 | 负责人 |
| --- | --- | --- |
| pn01 | 项目初始化与技术基线 | 已完成，三人共同维护 |
| pn02 | 数据库模型与状态流转 | A |
| pn03 | Scheduler | B |
| pn04 | Parser | B |
| pn05 | Cleaner | B |
| pn06 | RuleEngine | B |
| pn07 | LLMInfer | B |
| pn08 | Repository | A |
| pn09 | 后端 API | A |
| pn10 | 前端可视化 | C |
| pn11 | 流水线联调与异常 | B |
| pn12 | 测试、验收与交付 | A/B/C 各自负责自己模块，最后共同验收 |

## 五、最小接口契约

第一优先级：

- `GET /health`
- `GET /api/dashboard/summary`
- `GET /api/articles`
- `GET /api/articles/{id}`
- `GET /api/trends`

第二优先级：

- `POST /api/tasks/run`
- `POST /api/results/{id}/confirm`

前端文章列表最小字段：

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

## 六、分支建议

- `feature/backend-api`：开发者 A
- `feature/pipeline`：开发者 B
- `feature/frontend`：开发者 C

合并规则：

1. 每个人只改自己负责的主目录，减少冲突。
2. API 字段、数据库字段、状态码变化时，必须同步另外两人。
3. 每个阶段结束合并一次。
4. 合并前至少跑自己负责模块的测试或构建。

## 七、每日同步

每天只同步 3 件事：

1. 昨天完成了什么。
2. 今天要完成什么。
3. 有没有接口、字段、状态码变化。

如果没有公共契约变化，各自继续开发，不开长会。
