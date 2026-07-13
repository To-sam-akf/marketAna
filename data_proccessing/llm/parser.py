"""Strict parser for structured LLM fallback output."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from data_proccessing.catalog import PRODUCT_CATALOG, get_product, product_key_for_name
from data_proccessing.models import Direction


@dataclass(frozen=True, slots=True)
class LLMOutput:
    product_key: str
    product: str
    direction: Direction
    reason: str
    confidence: float


def parse_llm_response(raw: str, *, expected_product_key: str | None = None) -> tuple[list[LLMOutput], list[str]]:
    errors: list[str] = []
    payload = _decode_json(raw, errors)
    if payload is None:
        return [], errors
    rows = payload.get("results") if isinstance(payload, dict) and isinstance(payload.get("results"), list) else [payload]
    outputs: list[LLMOutput] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"result[{index}] is not an object")
            continue
        product_value = str(row.get("product") or row.get("product_key") or "").strip()
        product_key = str(row.get("product_key") or "").strip().upper() or product_key_for_name(product_value)
        product = get_product(product_key)
        if product is None:
            product = next((item for item in PRODUCT_CATALOG if product_value in {item.display_name, item.official_name, *item.aliases}), None)
        if product is None:
            errors.append(f"result[{index}] unknown product: {product_value}")
            continue
        if expected_product_key and product.product_key != expected_product_key:
            errors.append(f"result[{index}] product mismatch: {product.product_key}")
            continue
        direction = _direction(row.get("direction"))
        if direction is None:
            errors.append(f"result[{index}] invalid direction")
            continue
        reason = str(row.get("reason") or "").strip()
        if not reason:
            errors.append(f"result[{index}] empty reason")
            continue
        try:
            confidence = max(0.0, min(1.0, float(row.get("confidence"))))
        except (TypeError, ValueError):
            errors.append(f"result[{index}] invalid confidence")
            continue
        outputs.append(LLMOutput(product.product_key, product.display_name, direction, reason, confidence))
    return outputs, errors


def _decode_json(raw: str, errors: list[str]) -> dict[str, Any] | None:
    candidate = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", candidate, re.DOTALL | re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1)
    else:
        match = re.search(r"\{.*\}", candidate, re.DOTALL)
        if match:
            candidate = match.group(0)
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON: {exc.msg}")
        return None
    if not isinstance(payload, dict):
        errors.append("top-level JSON must be an object")
        return None
    return payload


def _direction(value: object) -> Direction | None:
    aliases = {"bullish": "看涨", "bearish": "看跌", "neutral": "中性"}
    normalized = aliases.get(str(value).strip().casefold(), str(value).strip())
    return normalized if normalized in {"看涨", "看跌", "中性"} else None  # type: ignore[return-value]
