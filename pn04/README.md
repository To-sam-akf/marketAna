# pn04 文件解析模块 Parser

## 概述

将 PDF、HTML、PNG/JPG 等格式的原始研报文件解析为纯文本，供后续 Cleaner（pn05）处理。

## 目录结构

```
pn04/
├── __init__.py          # 包初始化，导出 parse_article
├── parser.py            # 主解析器：路由选择、Repository 集成
├── pdf_parser.py        # PyMuPDF PDF 解析器
├── html_parser.py       # BeautifulSoup HTML 解析器
├── image_parser.py      # Tesseract OCR 图片解析器
├── table_utils.py       # 表格提取与 Markdown 转换
├── models.py            # 数据模型、类型检测
├── exceptions.py        # 解析器专用异常
├── test_parser.py       # 单元测试
├── requirements.txt     # 依赖清单
└── README.md            # 本文档
```

## 依赖安装

### 方式 1：pip 安装
```bash
pip install -r pn04/requirements.txt
```

### 方式 2：uv 安装（推荐）
```bash
uv add pymupdf beautifulsoup4 lxml pytesseract Pillow
```

> **注意**：OCR 功能需要额外安装 Tesseract OCR 引擎：
> - Ubuntu: `sudo apt install tesseract-ocr tesseract-ocr-chi-sim`
> - macOS: `brew install tesseract tesseract-lang`
> - Windows: 从 https://github.com/UB-Mannheim/tesseract/wiki 下载安装

## 使用方法

```python
from pn04.parser import parse_article, ParseConfig
from back_end.app.repositories.articles import ArticleRepository

# 创建配置
config = ParseConfig(
    ocr_lang="chi_sim+eng",
    extract_tables=True,
    max_text_length=500_000,
)

# 解析文章
raw_text = parse_article(article, session, config=config)
# 解析结果已自动写入 article_texts 表，状态更新为 1（PARSED）
```

## 支持的文件格式

| 格式 | 解析器 | 依赖 |
|------|--------|------|
| PDF | PdfParser (PyMuPDF) | pymupdf |
| HTML | HtmlParser (BeautifulSoup) | beautifulsoup4, lxml |
| PNG/JPG/BMP/TIFF/WebP | ImageParser (OCR) | pytesseract, Pillow, Tesseract |

## 文件类型检测优先级

1. `article.file_type` 字段
2. `article.file_url` 扩展名

## 状态流转

- 成功：`status = 0` → `status = 1`（PARSED），写入 `article_texts.raw_text`
- 失败：`status = -1`（FAILED），写入 `article.error_msg` 和 `task_logs`

## 测试

```bash
uv run pytest pn04/ -v
```
