已加好单文件手动测试脚本：[tests/manual_single_file_pipeline.py](/home/sanmu/marketANA/tests/manual_single_file_pipeline.py)。

用法示例：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python tests/manual_single_file_pipeline.py data/20250401/323354/浙商期货_323354_0.html
```

运行到清洗阶段时，终端会显示 `清洗进度` 进度条。

如果只想跳过真实 LLM 调用：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python tests/manual_single_file_pipeline.py data/20250401/323354/浙商期货_323354_0.html --skip-llm
```

如果想把处理结果写成文件：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python tests/manual_single_file_pipeline.py data/20250401/323354/浙商期货_323354_0.html --output-dir tests/outputs
```

会输出/写入：

- `01_raw_text.txt`：原始文本
- `02_document.json`：统一文档
- `03_product_matches.json`：品种匹配结果
- `04_signals.jsonl`：方向信号
- `05_analysis_results.jsonl`：分析结果
- `06_review_queue.jsonl`：审核队列
- `07_summary.json`：处理统计摘要
- `08_readable_report.md`：可读报告
- `09_canonical_result.json`：canonical 结果

验证过：
- 用你打开过的 HTML 样例跑 `--skip-llm` 成功。
- `py_compile` 通过。
