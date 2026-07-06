# pn05 数据清洗模块 Cleaner

## 概述

清洗 pn04 Parser 输出的 `raw_text`，移除广告、免责声明、HTML 残留、异常空白和低密度噪声块（页眉/页脚），输出干净的纯文本供 pn06/pn07 分析。

## 目录结构

```
pn05/
├── __init__.py          # 导出 clean_article, CleanConfig
├── cleaner.py           # 主清洗器：流程编排 + Repository 集成
├── normalizer.py        # 文本规范化（空白、全半角、HTML 残留、编码）
├── noise_rules.py       # 噪声规则库（行级关键词 + 正则段落模式）
├── models.py            # CleanConfig, CleanResult
├── test_cleaner.py      # 单元测试
└── README.md            # 本文档
```

## 清洗流程

```
raw_text
  → 编码检测修复    (detect_and_clean_encoding)
  → HTML 残留移除   (remove_html_residue)
  → 噪声行过滤      (filter_noise_lines + filter_noise_regex)
  → 低密度块过滤    (页眉/页脚/导航移除)
  → 空白规范化      (normalize_whitespace)
  → 全半角转换      (normalize_fullwidth)
  → cleaned_text     → 写入 article_texts + status=2
```

## 使用方法

```python
from pn05 import clean_article, CleanConfig

config = CleanConfig(
    min_density_ratio=0.15,   # 中文密度阈值
    filter_low_density=True,  # 移除页眉页脚
)

cleaned = clean_article(article_id, session, config=config)
# cleaned_text 已写入，status 已更新为 2 (CLEANED)
```

## 噪声规则扩展

编辑 `noise_rules.py` 中的列表即可扩展规则：

```python
# 新增行级关键词
NOISE_LINE_KEYWORDS.append("新广告词")

# 新增正则段落模式
NOISE_REGEX_PATTERNS.append(r"新广告标题[\s\S]*?(?=\n\n|\Z)")
```

## 测试

```bash
uv run pytest pn05/ -v
```
