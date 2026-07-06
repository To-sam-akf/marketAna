# pn05 数据清洗模块 Cleaner 计划

## 摘要

pn05 清洗 pn04 Parser 输出的 `raw_text`，执行编码修复、HTML 残留移除、噪声行过滤（30+ 关键词 + 5 段正则）、低密度块过滤（页眉/页脚/导航）、空白规范化和全半角转换六步处理。输出干净的纯文本通过 `ArticleRepository.save_cleaned_text()` 写入 `article_texts`，成功更新 `status=2`（CLEANED），失败更新 `status=-1`（FAILED）。清洗比例全程监控，防止过度清洗或清洗不足。

## 关键改动

- 文本规范化（`normalizer.py`）：
  - `normalize_whitespace()`：统一 `\r\n` → `\n`，合并连续空白，压缩多余空行。
  - `normalize_fullwidth()`：全角字母/数字/符号 → 半角（中文标点保留）。
  - `remove_html_residue()`：处理 `&nbsp;` `&lt;` 等 20+ 种 HTML 实体、`&#xxxx;` 数字实体和残留 `<tag>` 标签。
  - `detect_and_clean_encoding()`：移除 `\x00` NULL 字节，修复连续 Unicode 替换字符。

- 噪声规则库（`noise_rules.py`）：
  - 行级关键词过滤：30+ 关键词（"版权所有""免责声明""风险提示""扫码关注""客服电话"等），包含任一关键词的整行被移除。
  - 正则段落模式：5 段正则移除整段免责声明、风险提示、分析师声明、重要声明、法律声明。
  - 纯噪声行检测：纯 URL、纯分隔符、纯页码和纯空白行。
  - 规则设计为可扩展列表，新增规则只需追加到对应列表。

- 低密度块过滤：
  - 按 `\n\n` 分段，对每段计算中文字符占比。
  - 密度 < `min_density_ratio`（默认 0.15）的段视为页眉/页脚/导航 → 移除。
  - 短于 `min_paragraph_chars`（默认 10）的段直接移除。

- 清洗比例监控：
  - `removal_ratio = (raw - cleaned) / raw`。
  - `> 0.95`（几乎无清洗效果）→ warn 日志。
  - `< 0.05`（清洗比例异常高）→ warn 日志，可能过度清洗。
  - 清洗后为空 → `ValueError` → `mark_failed`。

- 主入口（`cleaner.py`）：
  - `clean_article(article_id, session)`：读取 `article_texts.raw_text` → 六步清洗 → `save_cleaned_text()` → task_log。
  - 异常统一调用 `repo.mark_failed()`。

## 实现顺序

1. 定义 `CleanConfig`、`CleanResult` 数据类（`models.py`）。
2. 实现 4 个规范化纯函数（`normalizer.py`）。
3. 实现噪声规则库（`noise_rules.py`）。
4. 实现主清洗流程 + 低密度过滤 + Repository 集成（`cleaner.py`）。
5. 编写测试用例，覆盖规范化、噪声过滤、完整流程和边界情况。
6. 编写 README 和本文档。

## 验证方案

- 规范化函数：
  - `\r\n` → `\n`，连续 3+ 换行 → 2 换行，连续空格合并。
  - 全角字母数字 → 半角，中文标点保留。
  - `&nbsp;` `<script>` `<p>` → 正确清理。

- 噪声过滤：
  - 含"版权所有""免责声明"的行 → 移除。
  - 纯 URL 行、纯分隔符行 → 移除。
  - 免责声明整段（正则）→ 移除。

- 低密度过滤：
  - 纯英文页眉页脚（如"Page 1 of 10""Contact: info@test.com"）→ 移除。
  - 中文正文完整保留。

- 集成测试：
  - 完整清洗流程：噪声移除 + 正文保留 + `status=2`（CLEANED）。
  - HTML 残留被清除。
  - 空 raw_text → `status=-1`（FAILED）。
  - task_log 正确记录清洗统计。
  - 中文内容完整保留（铁矿石、港口库存、震荡偏强）。

- 回归验证：
  - `uv run pytest pn05/ -v` 全部 16 个测试通过。

## 假设与默认选择

- 输入 `raw_text` 已是解码后的 str（编码检测由 pn04 在文件读取阶段完成）。
- 中文字符密度是区分正文和页眉页脚的核心指标（中文研报场景）。
- 清洗比例异常只记录 warn 日志，不阻塞流程（避免误杀）。
- 噪声规则初始覆盖中文期货研报常见噪声，后续可根据实际数据扩展。
- 不引入 chardet 硬依赖（pn05 以 str 为输入，编码问题残留由 `detect_and_clean_encoding()` 处理）。

## pn05 数据清洗模块实际实现情况

通过阅读和验证本阶段代码，pn05 的六步清洗流程、噪声规则库、低密度过滤和清洗比例监控已按计划落地。模块通过 `ArticleRepository` 接口写入数据库，状态流转（1→2 或 →-1）完整。

### 已实现的框架

**1. 文本规范化器** (`pn05/normalizer.py`)
- **`normalize_whitespace()`**：`\r\n`→`\n`，连续 3+ 换行→2 换行，行内空白合并。
- **`normalize_fullwidth()`**：全角字母（FF21-FF5A）、数字（FF10-FF19）、空格（3000）→半角。中文标点保留。
- **`remove_html_residue()`**：20+ 种 HTML 实体映射 + `&#xxxx;` 数字实体 + `<tag>` 残留标签正则移除。
- **`detect_and_clean_encoding()`**：移除 `\x00` + 压缩连续 `�`。

**2. 噪声规则库** (`pn05/noise_rules.py`)
- **行级关键词**：30+ 关键词覆盖法律/免责、营销/推广、联系方式、声明四类。
- **正则段落模式**：5 段正则（免责声明/风险提示/分析师声明/重要声明/法律声明）。
- **纯噪声行**：纯 URL、纯分隔符、纯页码、中文页码 4 种模式。
- 规则可扩展：追加到对应列表即生效。

**3. 低密度块过滤** (`pn05/cleaner.py` 中的 `_filter_low_density()`)
- 按 `\n\n` 分段 → 中文字符占比计算 → 低于阈值移除。
- 过短段落（< `min_paragraph_chars`）直接移除。

**4. 主入口** (`pn05/cleaner.py`)
- **`clean_article(article_id, session)`**：六步清洗流程 + 清洗比例监控 + `save_cleaned_text()` + task_log。

**5. 数据模型** (`pn05/models.py`)
- **`CleanConfig`**：8 个可配置参数（比例阈值、密度阈值、功能开关）。
- **`CleanResult`**：清洗前后长度、移除比例、噪声行数、低密度字符数、耗时。

### 尚未实现（但计划也说不做）

- 未引入 chardet 硬依赖 — pn05 输入已是 str，编码问题残留由 `detect_and_clean_encoding()` 处理。
- 噪声规则库当前覆盖中文期货研报常见模式，英文或其他语言需要扩展规则列表。
- 不修改 `back_end/app/services/` 中的任何现有文件。

### 计划中声明的功能验证

| 验证项 | 状态 |
|--------|------|
| 空白规范化（\r\n、连续换行、多余空格） | ✅ `test_normalize_whitespace_*` 系列 |
| 全角字母/数字 → 半角 | ✅ `test_normalize_fullwidth_*` |
| HTML 实体/标签移除 | ✅ `test_remove_html_residue_*` |
| NULL 字节/替换字符修复 | ✅ `test_detect_*` 系列 |
| 噪声行关键词过滤 | ✅ `test_filter_noise_keywords` |
| 纯 URL/分隔符行过滤 | ✅ `test_filter_noise_*` 系列 |
| 免责声明段落正则移除 | ✅ `test_filter_disclaimer_paragraph` |
| 低密度页眉页脚移除 | ✅ `test_low_density_filtered_in_cleaner` |
| 完整清洗流程 + status=2 | ✅ `test_clean_full_pipeline` |
| HTML 残留清除 | ✅ `test_clean_with_html_residue` |
| 空文本 → mark_failed | ✅ `test_clean_empty_raw` |
| task_log 记录 | ✅ `test_clean_task_log` |
| 中文内容完整保留 | ✅ `test_clean_preserves_chinese` |
| 清洗比例监控 | ✅ `test_clean_ratio_tracking` |
| 全量测试 | ✅ 16 个测试用例全部通过 |

**总结**：pn05 已完成数据清洗模块的核心实现。六步清洗流程可有效移除广告、免责声明、HTML 残留和页眉页脚噪声，清洗比例全程监控防止过度清洗。模块通过 `ArticleRepository` 接口写入 `cleaned_text` 和更新状态。后续 pn06 RuleEngine 可直接消费 `article_texts.cleaned_text`。
