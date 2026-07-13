from data_proccessing.instrument_mapping.runtime import RuntimeLexicon
from data_proccessing.signals.arbitrator import arbitrate
from data_proccessing.signals.aggregator import aggregate_signals
from data_proccessing.signals.extractor import extract_signals


def _signals(text: str):
    lexicon = RuntimeLexicon(
        [{"product_key": "SHFE.RB", "canonical": "螺纹钢", "aliases": ["螺纹钢"], "negative_contexts": []}]
    )
    matches = lexicon.find_matches(text)
    return extract_signals(text, matches)


def test_domain_signal_wins_over_nested_generic_word() -> None:
    signals = _signals("螺纹钢库存下降，需求改善，短期偏强")
    phrases = {signal.phrase for signal in signals}
    assert "库存下降" in phrases
    assert "需求改善" in phrases
    assert "下降" not in phrases


def test_conflict_is_sent_to_llm_fallback() -> None:
    signals = _signals("螺纹钢上涨后快速回落，库存增加，短期震荡")
    result = arbitrate("SHFE.RB", aggregate_signals(signals)["SHFE.RB"])
    assert result.decision in {"llm_fallback", "rule_accept"}
    assert result.signals
    assert result.bullish_score > 0
    assert result.bearish_score > 0


def test_historical_signal_is_discounted() -> None:
    signals = _signals("螺纹钢昨日上涨，但今日库存增加")
    historical = [signal for signal in signals if "历史" in signal.context_flags or "historical" in signal.context_flags]
    assert historical
