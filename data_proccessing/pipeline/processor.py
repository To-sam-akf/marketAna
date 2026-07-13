"""Single-document standalone processing pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any

from data_proccessing.config import ProcessingConfig
from data_proccessing.instrument_mapping.runtime import LexiconMatch, RuntimeLexicon
from data_proccessing.llm.client import LLMClient
from data_proccessing.llm.context import build_llm_context
from data_proccessing.llm.parser import parse_llm_response
from data_proccessing.models import AnalysisResult, DirectionSignal, Document
from data_proccessing.pipeline.canonical import build_product_evidence
from data_proccessing.signals.aggregator import aggregate_signals
from data_proccessing.signals.arbitrator import arbitrate
from data_proccessing.signals.extractor import extract_signals


@dataclass(frozen=True, slots=True)
class DocumentProcessingResult:
    document: Document
    matches: tuple[LexiconMatch, ...]
    signals: tuple[DirectionSignal, ...]
    analyses: tuple[AnalysisResult, ...]
    review_queue: tuple[dict[str, Any], ...] = ()
    errors: tuple[str, ...] = ()
    processing_stats: dict[str, Any] = field(default_factory=dict)


def process_document(
    document: Document,
    lexicon: RuntimeLexicon,
    *,
    llm_client: LLMClient | None = None,
    config: ProcessingConfig | None = None,
    skip_llm: bool = False,
) -> DocumentProcessingResult:
    config = config or ProcessingConfig()
    started = time.perf_counter()
    matches = tuple(lexicon.find_matches(document.raw_text, title=document.title))
    signals = tuple(extract_signals(document.raw_text, matches, context_window=config.context_window))
    grouped = aggregate_signals(signals)
    analyses: list[AnalysisResult] = []
    review_queue: list[dict[str, Any]] = []
    errors: list[str] = []
    rule_count = 0
    llm_count = 0
    for product_key, product_signals in grouped.items():
        arbitration = arbitrate(product_key, product_signals, config=config)
        rule_candidate: AnalysisResult | None = None
        fallback_reason = "rule_uncertain"
        if arbitration.decision == "rule_accept":
            rule_count += 1
            rule_evidence = _quality_evidence(
                document,
                product_key=product_key,
                direction=arbitration.direction,
                signals=signals,
                matches=matches,
            )
            rule_candidate = _rule_result(
                document,
                arbitration,
                evidence=_evidence_quotes(rule_evidence),
                need_manual_review=not rule_evidence["excerpts"],
            )
            if rule_evidence["excerpts"]:
                analyses.append(rule_candidate)
                continue
            fallback_reason = "rule_evidence_quality_failed"
        if arbitration.decision == "no_signal":
            review_queue.append({"source_id": document.source_id, "product_key": product_key, "reason": "no_signal"})
            continue

        llm_context_evidence = _quality_evidence(
            document,
            product_key=product_key,
            direction=None,
            signals=signals,
            matches=matches,
            allow_cross_product=True,
        )
        llm_snippets = _evidence_quotes(llm_context_evidence)
        if skip_llm or llm_client is None:
            if rule_candidate is not None:
                analyses.append(rule_candidate)
            review_queue.append({
                "source_id": document.source_id,
                "product_key": product_key,
                "product": arbitration.display_name,
                "reason": f"{fallback_reason}:llm_unavailable",
                "evidence": list(llm_snippets),
            })
            continue
        if not llm_snippets:
            if rule_candidate is not None:
                analyses.append(rule_candidate)
            review_queue.append({
                "source_id": document.source_id,
                "product_key": product_key,
                "product": arbitration.display_name,
                "reason": f"{fallback_reason}:no_product_scoped_context",
                "evidence": [],
            })
            continue
        llm_count += 1
        try:
            messages = build_llm_context(
                title=document.title,
                product=arbitration.display_name,
                arbitration=arbitration,
                config=config,
                evidence_snippets=list(llm_snippets),
            )
            raw = llm_client.complete(messages)
            outputs, parse_errors = parse_llm_response(raw, expected_product_key=product_key)
            errors.extend(parse_errors)
            if outputs:
                output = outputs[0]
                llm_evidence = _quality_evidence(
                    document,
                    product_key=product_key,
                    direction=output.direction,
                    signals=signals,
                    matches=matches,
                )
                llm_needs_review = output.confidence < 0.50 or not llm_evidence["excerpts"]
                analyses.append(
                    AnalysisResult(
                        source_id=document.source_id,
                        product_key=output.product_key,
                        product=output.product,
                        direction=output.direction,
                        reason=output.reason,
                        confidence=output.confidence,
                        method="llm",
                        need_manual_review=llm_needs_review,
                        evidence=_evidence_quotes(llm_evidence),
                        processing_stats={
                            "rule_margin": arbitration.margin,
                            "llm_errors": parse_errors,
                            "fallback_reason": fallback_reason,
                        },
                    )
                )
                if llm_needs_review:
                    review_queue.append({
                        "source_id": document.source_id,
                        "product_key": product_key,
                        "product": output.product,
                        "reason": "llm_evidence_quality_failed",
                        "evidence": list(_evidence_quotes(llm_evidence)),
                    })
                continue
        except Exception as exc:
            errors.append(f"llm_error: {exc}")
        if rule_candidate is not None:
            analyses.append(rule_candidate)
        review_queue.append({
            "source_id": document.source_id,
            "product_key": product_key,
            "product": arbitration.display_name,
            "reason": "llm_error_or_invalid_output",
            "evidence": list(llm_snippets),
        })
    # A product match without any direction signal is still an actionable
    # review item.  Do not silently lose navigation-page matches, OCR noise,
    # or articles that mention a product but express no view.
    matched_product_keys = {match.product_key for match in matches}
    for product_key in sorted(matched_product_keys - set(grouped)):
        match = next(match for match in matches if match.product_key == product_key)
        review_queue.append(
            {
                "source_id": document.source_id,
                "product_key": product_key,
                "product": match.display_name,
                "reason": "no_signal",
                "evidence": [match.evidence],
            }
        )
    if not matches:
        review_queue.append({"source_id": document.source_id, "reason": "no_product_match"})
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    stats = {
        "match_count": len(matches),
        "signal_count": len(signals),
        "rule_count": rule_count,
        "llm_count": llm_count,
        "review_count": len(review_queue),
        "duration_ms": elapsed_ms,
        "pipeline_version": config.pipeline_version,
    }
    return DocumentProcessingResult(document, matches, signals, tuple(analyses), tuple(review_queue), tuple(errors), stats)


def _rule_result(
    document: Document,
    arbitration: Any,
    *,
    evidence: tuple[str, ...] | None = None,
    need_manual_review: bool = False,
) -> AnalysisResult:
    resolved_evidence = evidence if evidence is not None else arbitration.evidence_snippets
    reason = _short_reason(resolved_evidence)
    return AnalysisResult(
        source_id=document.source_id,
        product_key=arbitration.product_key,
        product=arbitration.display_name,
        direction=arbitration.direction,
        reason=reason,
        confidence=arbitration.confidence,
        method="rule",
        need_manual_review=need_manual_review or arbitration.confidence < 0.50,
        evidence=resolved_evidence,
        processing_stats={
            "bullish_score": arbitration.bullish_score,
            "bearish_score": arbitration.bearish_score,
            "neutral_score": arbitration.neutral_score,
            "margin": arbitration.margin,
            "signal_count": len(arbitration.signals),
        },
    )


def _quality_evidence(
    document: Document,
    *,
    product_key: str,
    direction: str | None,
    signals: tuple[DirectionSignal, ...],
    matches: tuple[LexiconMatch, ...],
    allow_cross_product: bool = False,
) -> dict[str, Any]:
    cleaned_text = document.cleaned_text or str(document.metadata.get("cleaned_text") or document.raw_text)
    return build_product_evidence(
        product_key=product_key,
        direction=direction,
        cleaned_text=cleaned_text,
        raw_text=document.raw_text,
        signals=list(signals),
        matches=list(matches),
        allow_cross_product=allow_cross_product,
    )


def _evidence_quotes(evidence: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        str(excerpt.get("quote") or "")
        for excerpt in evidence.get("excerpts", [])
        if str(excerpt.get("quote") or "").strip()
    )


def _short_reason(snippets: tuple[str, ...]) -> str:
    """Keep UI-facing reasons short; full text stays in structured evidence."""
    import re

    unique: list[str] = []
    seen: set[str] = set()
    for item in snippets:
        compact = re.sub(r"\s+", " ", item).strip()
        if compact and compact not in seen:
            seen.add(compact)
            unique.append(compact)
    text = "；".join(unique[:3])
    return text
