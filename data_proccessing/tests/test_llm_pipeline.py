from pathlib import Path

from data_proccessing.instrument_mapping.runtime import RuntimeLexicon
from data_proccessing.llm.client import HttpLLMClient
from data_proccessing.llm.parser import parse_llm_response
from data_proccessing.models import Document
from data_proccessing.pipeline.processor import process_document


def _lexicon() -> RuntimeLexicon:
    return RuntimeLexicon(
        [{"product_key": "SHFE.RB", "canonical": "螺纹钢", "aliases": ["螺纹钢"], "negative_contexts": []}]
    )


def test_llm_parser_accepts_wrapped_json() -> None:
    outputs, errors = parse_llm_response(
        '分析如下：```json\n{"product":"螺纹钢","direction":"看涨","reason":"库存下降","confidence":0.8}\n```',
        expected_product_key="SHFE.RB",
    )
    assert errors == []
    assert outputs[0].direction == "看涨"
    assert outputs[0].confidence == 0.8


def test_pipeline_skip_llm_emits_review_queue() -> None:
    result = process_document(Document("doc-1", "螺纹钢上涨后回落，库存增加，短期震荡"), _lexicon(), skip_llm=True)
    assert result.review_queue or result.analyses
    assert result.processing_stats["signal_count"] > 0


def test_pipeline_uses_injected_llm_client() -> None:
    class FakeClient:
        def complete(self, messages):
            assert len(messages) == 2
            assert len(messages[1]["content"]) < 1500
            return '{"product":"螺纹钢","direction":"看跌","reason":"库存增加","confidence":0.8}'

    result = process_document(
        Document("doc-1", "螺纹钢上涨后回落，库存增加，短期震荡"),
        _lexicon(),
        llm_client=FakeClient(),
    )
    assert result.analyses
    assert result.analyses[0].method == "llm"
    assert result.analyses[0].direction == "看跌"


def test_rule_without_product_scoped_evidence_falls_back_to_llm() -> None:
    lexicon = RuntimeLexicon(
        [
            {"product_key": "CZCE.MA", "canonical": "甲醇", "aliases": ["甲醇"], "negative_contexts": []},
            {"product_key": "DCE.PP", "canonical": "PP", "aliases": ["PP"], "negative_contexts": []},
        ]
    )
    text = "【甲醇】甲醇供应压力凸显，价格下跌，09合约偏空。【PP】PP下游需求一般，价格预计震荡修复。"

    class FakeClient:
        def complete(self, messages):
            prompt = messages[1]["content"]
            assert "PP下游需求一般，价格预计震荡修复。" in prompt
            assert "甲醇供应压力凸显" not in prompt
            return '{"product":"PP","direction":"中性","reason":"价格预计震荡修复。","confidence":0.8}'

    result = process_document(Document("doc-2", text), lexicon, llm_client=FakeClient())
    pp = next(item for item in result.analyses if item.product_key == "DCE.PP")

    assert pp.method == "llm"
    assert pp.direction == "中性"
    assert pp.need_manual_review is False
    assert pp.processing_stats["fallback_reason"] == "rule_evidence_quality_failed"
    assert result.processing_stats["llm_count"] == 1


def test_rule_suggestion_is_preserved_for_review_when_llm_is_unavailable() -> None:
    lexicon = RuntimeLexicon(
        [
            {"product_key": "CZCE.MA", "canonical": "甲醇", "aliases": ["甲醇"], "negative_contexts": []},
            {"product_key": "DCE.PP", "canonical": "PP", "aliases": ["PP"], "negative_contexts": []},
        ]
    )
    text = "【甲醇】甲醇供应压力凸显，价格下跌，09合约偏空。【PP】PP下游需求一般，价格预计震荡修复。"

    result = process_document(Document("doc-3", text), lexicon, skip_llm=True)
    pp = next(item for item in result.analyses if item.product_key == "DCE.PP")

    assert pp.method == "rule"
    assert pp.direction == "看跌"
    assert pp.need_manual_review is True
    assert any(item.get("product_key") == "DCE.PP" for item in result.review_queue)


def test_wenhua_http_client_parses_sse(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def raise_for_status(self):
            return None

        def iter_lines(self):
            return iter(
                [
                    'data: {"choices":[{"delta":{"content":"{\\"product\\":\\"PP\\","},"finish_reason":null}]}',
                    'data: {"choices":[{"delta":{"content":"\\"direction\\":\\"中性\\"}"},"finish_reason":null}]}',
                    'data: {"choices":[{"delta":{"content":""},"finish_reason":"stop"}]}',
                ]
            )

    def fake_stream(method, url, **kwargs):
        captured.update({"method": method, "url": url, **kwargs})
        return FakeResponse()

    monkeypatch.setattr("data_proccessing.llm.client.httpx.stream", fake_stream)
    client = HttpLLMClient(
        api_key="secret",
        base_url="https://example.test/GetContent",
        model="wenhua-shixi",
        provider="wenhua",
    )

    result = client.complete([{"role": "user", "content": "判断 PP"}])

    assert result == '{"product":"PP","direction":"中性"}'
    assert captured["url"].endswith("/GetContent")
    assert captured["json"] == {"content": "user:\n判断 PP"}
