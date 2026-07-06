"""
pn04 表格提取与 Markdown 转换工具

将 HTML <table> 和 PDF 提取的表格数据转换为 Markdown 格式，
并可选追加自然语言描述以避免趋势信息丢失。
"""

from __future__ import annotations

import re
from typing import Any


def html_table_to_markdown(
    table_soup: Any,
    *,
    add_description: bool = True,
) -> str:
    """
    将 BeautifulSoup <table> 标签转换为 Markdown 表格。

    处理合并单元格（rowspan/colspan）、空单元格和表头。

    Args:
        table_soup: BeautifulSoup Tag 对象（<table>）
        add_description: 是否在表格前后添加自然语言描述

    Returns:
        Markdown 格式的表格字符串
    """
    # 提取所有行
    rows: list[list[str]] = []
    thead_rows = table_soup.find_all("tr") if table_soup.name == "thead" else []
    tbody_rows = table_soup.find_all("tr") if table_soup.name == "tbody" else []

    all_rows = table_soup.find_all("tr")

    if not all_rows:
        return ""

    max_cols = 0
    for row in all_rows:
        cells = row.find_all(["th", "td"])
        col_count = sum(_cell_colspan(cell) for cell in cells)
        max_cols = max(max_cols, col_count)

    if max_cols == 0:
        return ""

    # 构建表格数据
    table_data: list[list[str]] = []
    for row in all_rows:
        cells = row.find_all(["th", "td"])
        row_data: list[str] = []
        for cell in cells:
            text = _clean_cell_text(cell.get_text(strip=True))
            colspan = _cell_colspan(cell)
            row_data.append(text)
            # 填充 colspan 的空列
            for _ in range(colspan - 1):
                row_data.append("")
        # 补齐到 max_cols
        while len(row_data) < max_cols:
            row_data.append("")
        table_data.append(row_data[:max_cols])

    if not table_data:
        return ""

    # 生成 Markdown
    lines: list[str] = []

    if add_description:
        lines.append(f"\n下表包含 {len(table_data)} 行 {max_cols} 列的表格数据：\n")

    # 表头（第一行）
    header = table_data[0]
    lines.append("| " + " | ".join(h or " " for h in header) + " |")
    lines.append("| " + " | ".join("---" for _ in header) + " |")

    # 数据行
    for row in table_data[1:]:
        lines.append("| " + " | ".join(c or " " for c in row) + " |")

    if add_description:
        lines.append(f"\n（上表共 {len(table_data) - 1} 行数据）\n")

    return "\n".join(lines)


def pdf_table_to_markdown(
    cells: list[list[str]],
    *,
    headers: list[str] | None = None,
    add_description: bool = True,
) -> str:
    """
    将 PDF 提取的表格单元格列表转换为 Markdown 表格。

    Args:
        cells: 二维列表，每行是一列单元格文本
        headers: 可选的表头行，若未提供则使用 cells 第一行
        add_description: 是否添加自然语言描述

    Returns:
        Markdown 格式的表格字符串
    """
    if not cells:
        return ""

    max_cols = max(len(row) for row in cells)
    if max_cols == 0:
        return ""

    lines: list[str] = []

    if add_description:
        lines.append(f"\n下表包含 {len(cells)} 行数据的表格：\n")

    # 表头
    header_row = headers if headers else cells[0]
    padded_header = list(header_row) + [""] * (max_cols - len(header_row))
    lines.append("| " + " | ".join(h or " " for h in padded_header) + " |")
    lines.append("| " + " | ".join("---" for _ in range(max_cols)) + " |")

    # 数据行
    start = 0 if headers else 1
    for row in cells[start:]:
        padded_row = list(row) + [""] * (max_cols - len(row))
        lines.append("| " + " | ".join(c or " " for c in padded_row) + " |")

    if add_description:
        data_rows = len(cells) - (0 if headers else 1)
        lines.append(f"\n（上表共 {max(0, data_rows)} 行数据）\n")

    return "\n".join(lines)


def extract_table_text(table_soup: Any) -> str:
    """
    从 HTML <table> 提取纯文本描述（非 Markdown）。

    用于辅助 LLM 理解表格语义，与 Markdown 表格互补。

    Args:
        table_soup: BeautifulSoup Tag 对象（<table>）

    Returns:
        表格的纯文本描述
    """
    rows = table_soup.find_all("tr")
    if not rows:
        return ""

    parts: list[str] = []
    for i, row in enumerate(rows):
        cells = row.find_all(["th", "td"])
        cell_texts = [_clean_cell_text(c.get_text(strip=True)) for c in cells]
        if i == 0:
            parts.append("表头: " + " | ".join(cell_texts))
        else:
            parts.append(f"第{i}行: " + " | ".join(cell_texts))

    return "\n".join(parts)


# ---- 内部工具函数 ----

def _cell_colspan(cell: Any) -> int:
    """获取单元格的 colspan 值，最小为 1。"""
    colspan_str = cell.get("colspan", "1")
    try:
        return max(1, int(colspan_str))
    except (ValueError, TypeError):
        return 1


def _clean_cell_text(text: str) -> str:
    """清理单元格文本：合并空白、去除换行。"""
    text = re.sub(r"\s+", " ", text)
    return text.strip()
