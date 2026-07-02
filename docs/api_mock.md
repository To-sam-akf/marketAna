# MarketANA API Mock Contract

本文档冻结开发者 A 在 pn02、pn09 阶段提供给前端开发者 C 的第一版接口契约。前端可以直接基于本文档编写页面类型、mock 数据和 API client；真实后端接入时应保持字段名、枚举值和分页结构不变。

## 1. Common Contract

### 1.1 Unified Response

所有成功接口统一返回：

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

所有错误接口统一返回：

```json
{
  "code": 10001,
  "message": "Request validation failed",
  "data": null,
  "detail": []
}
```

常用错误码：

| code | meaning |
| --- | --- |
| `0` | success |
| `10000` | internal error |
| `10001` | validation error |
| `10002` | not found |
| `20001` | database unconfigured |
| `20002` | database error |
| `30001` | LLM unconfigured |

### 1.2 Enums

文章处理状态：

| status | meaning |
| --- | --- |
| `-1` | 失败 |
| `0` | 未处理 |
| `1` | 解析完成 |
| `2` | 清洗完成 |
| `3` | 规则识别完成 |
| `4` | LLM 推理完成 |
| `5` | 已入库 |

方向枚举固定为：`看涨`、`看跌`、`中性`。

分析方法枚举固定为：`rule`、`llm`、`manual`。

置信度统一使用 `0-1` 小数，前端展示百分比时自行格式化。

### 1.3 Core Table Fields

| table | fields |
| --- | --- |
| `articles` | `id`, `title`, `source`, `company`, `file_url`, `file_type`, `publish_time`, `status`, `error_msg`, `created_at`, `updated_at` |
| `article_texts` | `id`, `article_id`, `raw_text`, `cleaned_text`, `raw_length`, `cleaned_length`, `parser_type`, `created_at`, `updated_at` |
| `analysis_results` | `id`, `article_id`, `product`, `direction`, `reason`, `confidence`, `analysis_method`, `need_manual_review`, `analysis_time`, `created_at`, `updated_at` |
| `task_logs` | `id`, `article_id`, `stage`, `status`, `message`, `duration_ms`, `created_at` |
| `manual_confirmations` | `id`, `article_id`, `original_product`, `original_direction`, `original_reason`, `original_confidence`, `confirmed_product`, `confirmed_direction`, `confirmed_reason`, `confirmed_confidence`, `confirmed_by`, `note`, `confirmed_at` |

## 2. Dashboard Summary

### `GET /api/dashboard/summary`

用于首页统计卡片、方向分布图和待人工确认提示。

Response:

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

## 3. Article List

### `GET /api/articles`

用于文章列表、筛选区、搜索和分页。

Query parameters:

| name | type | required | description |
| --- | --- | --- | --- |
| `product` | string | no | 按品种筛选，如 `豆粕` |
| `company` | string | no | 按期货公司筛选，如 `甲期货` |
| `direction` | string | no | `看涨`、`看跌`、`中性` |
| `status` | number | no | 文章处理状态 |
| `start_time` | ISO datetime | no | 起始时间 |
| `end_time` | ISO datetime | no | 结束时间 |
| `keyword` | string | no | 标题关键词 |
| `page` | number | no | 默认 `1` |
| `page_size` | number | no | 默认 `20`，最大 `100` |

Example:

`GET /api/articles?product=豆粕&company=甲期货&direction=看涨&status=5&page=1&page_size=20`

Response:

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
      },
      {
        "id": 102,
        "title": "沪铜短期观点分歧",
        "source": "晨会纪要",
        "company": "乙期货",
        "file_url": "/files/copper.pdf",
        "file_type": "pdf",
        "publish_time": "2026-07-02T10:15:00",
        "status": 5,
        "error_msg": null,
        "created_at": "2026-07-02T10:20:00",
        "updated_at": "2026-07-02T10:23:00",
        "product": "沪铜",
        "direction": "中性",
        "reason": "宏观扰动和需求弱修复并存，短线以震荡判断为主。",
        "confidence": 0.45,
        "need_manual_review": true,
        "analysis_time": "2026-07-02T10:23:00"
      }
    ],
    "total": 2,
    "page": 1,
    "page_size": 20
  }
}
```

Empty response:

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [],
    "total": 0,
    "page": 1,
    "page_size": 20
  }
}
```

## 4. Article Detail

### `GET /api/articles/{article_id}`

用于详情页或详情抽屉。返回文章基础信息、原始/清洗文本、当前分析结果、流水线日志和人工确认记录。

Response:

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "article": {
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
    },
    "text": {
      "id": 501,
      "article_id": 101,
      "raw_text": "原始正文...",
      "cleaned_text": "清洗后正文...",
      "raw_length": 2034,
      "cleaned_length": 1680,
      "parser_type": "html",
      "created_at": "2026-07-02T09:06:00",
      "updated_at": "2026-07-02T09:07:00"
    },
    "analysis_result": {
      "id": 201,
      "article_id": 101,
      "product": "豆粕",
      "direction": "看涨",
      "reason": "下游补库增加，库存压力缓解。",
      "confidence": 0.82,
      "analysis_method": "llm",
      "need_manual_review": false,
      "analysis_time": "2026-07-02T09:08:00"
    },
    "task_logs": [
      {
        "id": 1,
        "article_id": 101,
        "stage": "parser",
        "status": "success",
        "message": "parsed html",
        "duration_ms": 120,
        "created_at": "2026-07-02T09:06:00"
      },
      {
        "id": 2,
        "article_id": 101,
        "stage": "llm",
        "status": "success",
        "message": "ok",
        "duration_ms": 430,
        "created_at": "2026-07-02T09:08:00"
      }
    ],
    "manual_confirmations": []
  }
}
```

待人工确认详情示例：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "article": {
      "id": 102,
      "title": "沪铜短期观点分歧",
      "source": "晨会纪要",
      "company": "乙期货",
      "file_url": "/files/copper.pdf",
      "file_type": "pdf",
      "publish_time": "2026-07-02T10:15:00",
      "status": 5,
      "error_msg": null,
      "created_at": "2026-07-02T10:20:00",
      "updated_at": "2026-07-02T10:23:00",
      "product": "沪铜",
      "direction": "中性",
      "reason": "宏观扰动和需求弱修复并存，短线以震荡判断为主。",
      "confidence": 0.45,
      "need_manual_review": true,
      "analysis_time": "2026-07-02T10:23:00"
    },
    "text": {
      "id": 502,
      "article_id": 102,
      "raw_text": "原始正文...",
      "cleaned_text": "清洗后正文...",
      "raw_length": 3280,
      "cleaned_length": 2740,
      "parser_type": "pdf",
      "created_at": "2026-07-02T10:21:00",
      "updated_at": "2026-07-02T10:22:00"
    },
    "analysis_result": {
      "id": 202,
      "article_id": 102,
      "product": "沪铜",
      "direction": "中性",
      "reason": "宏观扰动和需求弱修复并存，短线以震荡判断为主。",
      "confidence": 0.45,
      "analysis_method": "llm",
      "need_manual_review": true,
      "analysis_time": "2026-07-02T10:23:00"
    },
    "task_logs": [
      {
        "id": 3,
        "article_id": 102,
        "stage": "llm",
        "status": "success",
        "message": "low confidence, manual review required",
        "duration_ms": 680,
        "created_at": "2026-07-02T10:23:00"
      }
    ],
    "manual_confirmations": []
  }
}
```

Not found response:

```json
{
  "code": 10002,
  "message": "Article not found",
  "data": null,
  "detail": {
    "article_id": 999
  }
}
```

## 5. Trends

### `GET /api/trends`

用于趋势折线图、柱状图或按品种切换的聚合视图。

Query parameters:

| name | type | required | description |
| --- | --- | --- | --- |
| `product` | string | no | 按品种筛选 |
| `start_time` | ISO datetime | no | 起始时间 |
| `end_time` | ISO datetime | no | 结束时间 |

Example:

`GET /api/trends?product=豆粕&start_time=2026-07-01T00:00:00&end_time=2026-07-02T23:59:59`

Response:

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "date": "2026-07-01",
        "product": "豆粕",
        "direction": "看涨",
        "count": 4
      },
      {
        "date": "2026-07-01",
        "product": "豆粕",
        "direction": "看跌",
        "count": 1
      },
      {
        "date": "2026-07-02",
        "product": "豆粕",
        "direction": "中性",
        "count": 2
      }
    ]
  }
}
```

Empty response:

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": []
  }
}
```

## 6. Manual Run

### `POST /api/tasks/run`

用于前端手动刷新或触发一次扫描。开发者 B 接入真实 Pipeline 前，此接口可以返回占位结果，但字段结构不变。

Request body:

```json
{
  "article_id": null,
  "limit": 20
}
```

指定单篇文章重跑：

```json
{
  "article_id": 101,
  "limit": null
}
```

Response:

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

Current placeholder response before Pipeline is wired:

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "triggered": false,
    "article_id": null,
    "limit": 20,
    "message": "Pipeline runner is not wired yet"
  }
}
```

## 7. Manual Confirm

### `POST /api/results/{result_id}/confirm`

用于人工确认或修正低置信分析结果。提交成功后，后端会把当前 `analysis_result` 更新为人工确认值，并写入 `manual_confirmations` 审计记录。

Request body:

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

Response:

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

Validation error example:

```json
{
  "code": 10001,
  "message": "Request validation failed",
  "data": null,
  "detail": [
    {
      "type": "less_than_equal",
      "loc": ["body", "confidence"],
      "msg": "Input should be less than or equal to 1",
      "input": 1.2,
      "ctx": {
        "le": 1.0
      }
    }
  ]
}
```

## 8. Frontend Type Suggestions

前端建议先定义以下类型，字段名与本文档保持一致：

```ts
export interface ApiResponse<T> {
  code: number
  message: string
  data: T | null
  detail?: unknown
}

export interface DashboardSummary {
  today_articles: number
  total_articles: number
  success_count: number
  failed_count: number
  success_rate: number
  manual_review_count: number
  direction_distribution: Record<'看涨' | '看跌' | '中性', number>
}

export interface ArticleListItem {
  id: number
  title: string
  source: string | null
  company: string | null
  file_url: string | null
  file_type: string | null
  publish_time: string | null
  status: -1 | 0 | 1 | 2 | 3 | 4 | 5
  error_msg: string | null
  created_at: string | null
  updated_at: string | null
  product: string | null
  direction: '看涨' | '看跌' | '中性' | null
  reason: string | null
  confidence: number | null
  need_manual_review: boolean
  analysis_time: string | null
}

export interface TrendItem {
  date: string
  product: string
  direction: '看涨' | '看跌' | '中性'
  count: number
}
```

## 9. Acceptance Checklist

- C 可以用 `GET /api/dashboard/summary` 完成首页统计卡片和方向分布。
- C 可以用 `GET /api/articles` 完成文章列表、筛选、搜索、分页和待人工确认标记。
- C 可以用 `GET /api/articles/{article_id}` 完成详情页或详情抽屉。
- C 可以用 `GET /api/trends` 完成趋势图。
- C 可以用 `POST /api/tasks/run` 完成手动刷新入口。
- C 可以用 `POST /api/results/{result_id}/confirm` 完成人工确认提交。
- 后续如修改字段名、枚举、分页结构或响应外壳，A 必须同步 B/C。
