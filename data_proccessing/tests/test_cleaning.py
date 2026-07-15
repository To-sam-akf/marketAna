from data_proccessing.cleaning import clean_display_text, clean_text


def test_clean_text_removes_report_noise_but_keeps_market_evidence() -> None:
    raw = (
        "螺纹钢库存下降，需求改善，短期偏强。\n"
        "免责声明：本报告不构成投资建议。\n"
        "电话：021-68757827\n"
        "1 2 3 4 5 6"
    )

    cleaned, stats = clean_text(raw)

    assert "螺纹钢库存下降" in cleaned
    assert "免责声明" not in cleaned
    assert "021-68757827" not in cleaned
    assert stats.noise_lines_removed >= 1


def test_clean_text_preserves_markdown_table() -> None:
    raw = "## 表格\n| 品种 | 库存 |\n| --- | --- |\n| 螺纹钢 | 100 |"

    cleaned, _ = clean_text(raw)

    assert "| 品种 | 库存 |" in cleaned
    assert "| 螺纹钢 | 100 |" in cleaned


def test_clean_display_text_removes_credentials_and_contact_details() -> None:
    text = "观点：螺纹钢偏强。投资咨询证号：Z0019876\n邮箱：a@example.com\n电话：021-68757827"

    cleaned = clean_display_text(text)

    assert "螺纹钢偏强" in cleaned
    assert "Z0019876" not in cleaned
    assert "a@example.com" not in cleaned
    assert "021-68757827" not in cleaned
