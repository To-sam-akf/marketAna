"""Extract short, traceable direction signals from raw text."""

from __future__ import annotations

import hashlib
import re
from typing import Iterable

from data_proccessing.instrument_mapping.runtime import LexiconMatch
from data_proccessing.models import DirectionSignal
from data_proccessing.signals.context import context_flags
from data_proccessing.signals.patterns import COMPILED_PATTERNS, PATTERN_WEIGHTS


def extract_signals(
    text: str,
    matches: Iterable[LexiconMatch],
    *,
    context_window: int = 80,
) -> list[DirectionSignal]:
    signals: list[DirectionSignal] = []
    for product_match in matches:
        window_start = max(0, product_match.start - context_window)
        window_end = min(len(text), product_match.end + context_window)
        window = text[window_start:window_end]
        for signal_type, direction, label, pattern in COMPILED_PATTERNS:
            for found in pattern.finditer(window):
                start = window_start + found.start()
                end = window_start + found.end()
                flags = context_flags(text, start, end)
                phrase = found.group(0)
                evidence = text[max(0, start - 35):min(len(text), end + 35)].replace("\n", " ").strip()
                signal_id = hashlib.sha1(
                    f"{product_match.product_key}|{start}|{end}|{direction}|{phrase}".encode("utf-8")
                ).hexdigest()[:16]
                signals.append(
                    DirectionSignal(
                        signal_id=signal_id,
                        product_key=product_match.product_key,
                        raw_alias=product_match.alias,
                        direction=direction,  # type: ignore[arg-type]
                        signal_type=signal_type,
                        phrase=phrase,
                        value=_numeric_value(phrase),
                        confidence=max(0.05, min(1.0, _signal_factor(flags))),
                        start=start,
                        end=end,
                        evidence_text=evidence,
                        context_flags=flags,
                    )
                )
    return _deduplicate(signals)


def _numeric_value(phrase: str) -> float | None:
    match = re.search(r"[+-]?\d+(?:\.\d+)?", phrase)
    return float(match.group(0)) if match else None


def _signal_factor(flags: tuple[str, ...]) -> float:
    factor = 1.0
    if "negated" in flags:
        factor *= 0.35
    if "conditional" in flags:
        factor *= 0.70
    if "historical" in flags:
        factor *= 0.50
    if "risk_context" in flags:
        factor *= 0.75
    if "after_turn" in flags:
        factor *= 0.75
    return factor


def _deduplicate(signals: list[DirectionSignal]) -> list[DirectionSignal]:
    unique: dict[tuple[str | None, int, int, str], DirectionSignal] = {}
    for signal in signals:
        key = (signal.product_key, signal.start, signal.end, signal.direction)
        previous = unique.get(key)
        if previous is None or signal.confidence > previous.confidence:
            unique[key] = signal

    # A domain-specific phrase such as “库存下降” must win over the shorter
    # generic direction word “下降” occurring inside the same span.
    ordered = sorted(unique.values(), key=lambda item: (-(item.end - item.start), item.start))
    accepted: list[DirectionSignal] = []
    for signal in ordered:
        overlaps = [
            item for item in accepted
            if item.product_key == signal.product_key
            and signal.start < item.end
            and item.start < signal.end
        ]
        if overlaps:
            continue
        accepted.append(signal)
    return sorted(accepted, key=lambda item: (item.product_key or "", item.start, item.end))
