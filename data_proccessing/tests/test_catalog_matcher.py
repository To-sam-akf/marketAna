from data_proccessing.catalog import ProductMatcher, get_product


def test_catalog_matcher_supports_dynamic_aliases_and_negative_context() -> None:
    matcher = ProductMatcher(dynamic_aliases={"欧集线": "INE.EC"})

    matches = matcher.find_matches("【欧集线】运价预期偏强。国内沪铜供应偏紧。LME铜价上涨。")

    assert [(item.product_key, item.alias) for item in matches] == [
        ("INE.EC", "欧集线"),
        ("SHFE.CU", "沪铜"),
    ]
    assert get_product("INE.EC").display_name == "集运指数（欧线）"
