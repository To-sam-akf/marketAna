from data_proccessing.instrument_mapping.runtime import LexiconMatch
from data_proccessing.models import AnalysisResult, DirectionSignal, Document
from data_proccessing.pipeline.canonical import to_canonical_result
from data_proccessing.pipeline.processor import DocumentProcessingResult


def _match(text: str, alias: str, product_key: str, display_name: str, *, occurrence: int = 0) -> LexiconMatch:
    start = -1
    offset = 0
    for _ in range(occurrence + 1):
        start = text.index(alias, offset)
        offset = start + len(alias)
    return LexiconMatch(product_key, display_name, alias, start, start + len(alias), "test", "body_alias")


def _signal(text: str, phrase: str, product_key: str, direction: str, *, occurrence: int = 0) -> DirectionSignal:
    start = -1
    offset = 0
    for _ in range(occurrence + 1):
        start = text.index(phrase, offset)
        offset = start + len(phrase)
    return DirectionSignal(
        signal_id=f"{product_key}-{start}",
        product_key=product_key,
        raw_alias=product_key,
        direction=direction,  # type: ignore[arg-type]
        signal_type="direction_word",
        phrase=phrase,
        value=None,
        confidence=1.0,
        start=start,
        end=start + len(phrase),
        evidence_text=text,
    )


def test_canonical_reason_and_evidence_are_complete_and_product_scoped() -> None:
    text = (
        "【PX】PX价格上涨，短期偏强。"
        "【PTA】PTA跟随PX成本走强而上升，幅度不及原料。"
        "另外下游开工继续回升，PTA去库将持续。"
        "【乙二醇】乙二醇供应承压，价格下跌。"
    )
    matches = (
        _match(text, "PX", "CZCE.PX", "PX", occurrence=0),
        _match(text, "PTA", "CZCE.TA", "PTA", occurrence=0),
        _match(text, "PX", "CZCE.PX", "PX", occurrence=2),
        _match(text, "乙二醇", "DCE.EG", "乙二醇", occurrence=0),
    )
    signals = (
        # This cross-section signal must not become PTA evidence.
        _signal(text, "上涨", "CZCE.TA", "看涨"),
        _signal(text, "上升", "CZCE.TA", "看涨"),
        _signal(text, "回升", "CZCE.TA", "看涨"),
    )
    analysis = AnalysisResult(
        source_id="doc-1",
        product_key="CZCE.TA",
        product="PTA",
        direction="看涨",
        reason="旧的截断理由",
        confidence=0.9,
        method="rule",
    )
    result = DocumentProcessingResult(Document("doc-1", text), matches, signals, (analysis,))

    payload = to_canonical_result(result)
    item = payload["results"][0]

    assert item["reason"] == "PTA跟随PX成本走强而上升，幅度不及原料。 另外下游开工继续回升，PTA去库将持续。"
    assert item["need_manual_review"] is False
    assert all(excerpt["quote"].endswith("。") for excerpt in item["evidence"]["excerpts"])
    assert all("乙二醇" not in excerpt["quote"] for excerpt in item["evidence"]["excerpts"])
    assert all("PX价格上涨" not in excerpt["quote"] for excerpt in item["evidence"]["excerpts"])
    assert all(
        text[excerpt["start_char"]:excerpt["end_char"]] == excerpt["raw_quote"]
        for excerpt in item["evidence"]["excerpts"]
    )


def test_canonical_marks_result_for_review_without_complete_scoped_evidence() -> None:
    text = "【甲醇】甲醇价格偏空。【PP】PP下游需求一般，短期震荡"
    matches = (
        _match(text, "甲醇", "CZCE.MA", "甲醇"),
        _match(text, "PP", "DCE.PP", "PP"),
    )
    signals = (_signal(text, "偏空", "DCE.PP", "看跌"),)
    analysis = AnalysisResult(
        source_id="doc-2",
        product_key="DCE.PP",
        product="PP",
        direction="看跌",
        reason="甲醇价格偏空",
        confidence=0.8,
        method="rule",
    )
    result = DocumentProcessingResult(Document("doc-2", text), matches, signals, (analysis,))

    item = to_canonical_result(result)["results"][0]

    assert item["reason"] == ""
    assert item["evidence"]["excerpts"] == []
    assert item["need_manual_review"] is True


def test_canonical_rejects_unexplained_other_product_in_same_section() -> None:
    text = "【PTA】PTA库存下降，乙二醇价格上涨。【乙二醇】乙二醇短期震荡。"
    matches = (
        _match(text, "PTA", "CZCE.TA", "PTA"),
        _match(text, "乙二醇", "DCE.EG", "乙二醇", occurrence=0),
        _match(text, "乙二醇", "DCE.EG", "乙二醇", occurrence=1),
    )
    signals = (_signal(text, "上涨", "CZCE.TA", "看涨"),)
    analysis = AnalysisResult(
        source_id="doc-3",
        product_key="CZCE.TA",
        product="PTA",
        direction="看涨",
        reason="乙二醇价格上涨",
        confidence=0.8,
        method="rule",
    )
    result = DocumentProcessingResult(Document("doc-3", text), matches, signals, (analysis,))

    item = to_canonical_result(result)["results"][0]

    assert item["evidence"]["excerpts"] == []
    assert item["need_manual_review"] is True
