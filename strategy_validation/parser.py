from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .models import StrategyDocument

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_TABLE_RE = re.compile(r"^\|\s*(.*?)\s*\|\s*(.*?)\s*\|$")
_BULLET_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+(.*)$")
_COLON_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 /()%_-]{1,50})\s*:\s*(.+)$")

_FIELD_HINTS = {
    "instrument": ("instrument", "instruments", "symbol", "symbols"),
    "market": ("market",),
    "timeframe": (
        "timeframe",
        "timeframes",
        "primary tf",
        "signal tf",
        "primary tf (signal)",
        "htf bias tf",
    ),
    "session": ("session", "sessions", "trading session"),
    "direction": ("direction", "long / short direction", "bias"),
    "entry_rules": ("entry rules", "entry trigger", "signal chain"),
    "exit_rules": ("exit rules", "tp / sl / be / trailing / partial", "exits"),
    "stop_loss": ("stop loss", "sl", "exit rules"),
    "take_profit": ("take profit", "tp", "exit rules"),
    "risk_model": ("risk model", "risk", "kill switch / safety"),
    "position_sizing": ("position sizing", "position size"),
    "news_rules": ("news rules", "news filter"),
    "max_daily_loss": ("maximum daily loss", "daily loss limit"),
    "max_drawdown": ("maximum drawdown", "max drawdown"),
    "max_open_positions": (
        "maximum open positions",
        "one position per session",
        "max open positions",
    ),
}


def _normalize_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _extract_name(lines: list[str]) -> str:
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# Strategy:"):
            return stripped.split(":", 1)[1].strip()
    for line in lines:
        match = _HEADING_RE.match(line.strip())
        if match:
            title = match.group(2).strip()
            if title:
                return title
    return "Unnamed Strategy"


def _extract_field(
    key_values: dict[str, str], sections: dict[str, str], *hints: str
) -> str:
    normalized = {_normalize_key(key): value for key, value in key_values.items()}
    for hint in hints:
        if hint in normalized:
            return normalized[hint]
    for key, value in normalized.items():
        if any(hint in key for hint in hints):
            return value
    for heading, body in sections.items():
        normalized_heading = _normalize_key(heading)
        if normalized_heading in hints:
            return body.strip()
        if any(hint in normalized_heading for hint in hints):
            return body.strip()
    return ""


def _extract_fields(
    key_values: dict[str, str], sections: dict[str, str]
) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for field_name, hints in _FIELD_HINTS.items():
        value = _extract_field(key_values, sections, *hints)
        if value:
            fields[field_name] = value
    instruments = str(fields.get("instrument", ""))
    if not fields.get("market") and any(
        pair in instruments for pair in ("EURUSD", "GBPUSD", "USDJPY", "XAUUSD")
    ):
        fields["market"] = "FX"
    if not fields.get("position_sizing"):
        candidate = "\n".join(
            filter(
                None,
                [
                    fields.get("risk_model", ""),
                    sections.get("Risk Model", ""),
                    sections.get("Kill Switch / Safety", ""),
                ],
            )
        )
        lowered = candidate.lower()
        if any(
            token in lowered
            for token in (
                "risk per trade",
                "fixed fractional",
                "position size",
                "lot size",
            )
        ):
            fields["position_sizing"] = candidate.strip()
    exit_rules = str(fields.get("exit_rules", ""))
    if exit_rules:
        lowered = exit_rules.lower()
        if not fields.get("stop_loss") and "stop loss" in lowered:
            fields["stop_loss"] = exit_rules
        if not fields.get("take_profit") and "take profit" in lowered:
            fields["take_profit"] = exit_rules
    return fields


def parse_strategy_document(text: str, source_path: str = "") -> StrategyDocument:
    lines = text.splitlines()
    strategy_name = _extract_name(lines)
    sections: dict[str, str] = {}
    key_values: dict[str, str] = {}
    list_items: list[str] = []
    buckets: dict[str, list[str]] = defaultdict(list)
    current_heading = "overview"

    for raw_line in lines:
        line = raw_line.rstrip()
        heading_match = _HEADING_RE.match(line.strip())
        if heading_match:
            current_heading = heading_match.group(2).strip()
            continue

        table_match = _TABLE_RE.match(line.strip())
        if table_match:
            left = table_match.group(1).strip()
            right = table_match.group(2).strip()
            if left and right and set(left) != {"-"} and set(right) != {"-"}:
                key_values[left] = right
                buckets[current_heading].append(f"{left}: {right}")
            continue

        colon_match = _COLON_RE.match(line)
        if colon_match:
            key = colon_match.group(1).strip()
            value = colon_match.group(2).strip()
            key_values[key] = value
            buckets[current_heading].append(f"{key}: {value}")
            continue

        bullet_match = _BULLET_RE.match(line)
        if bullet_match:
            item = bullet_match.group(1).strip()
            list_items.append(item)
            buckets[current_heading].append(item)
            continue

        if line.strip():
            buckets[current_heading].append(line.strip())

    for heading, section_lines in buckets.items():
        sections[heading] = "\n".join(section_lines).strip()

    extracted_fields = _extract_fields(key_values, sections)
    return StrategyDocument(
        strategy_name=strategy_name,
        raw_text=text,
        source_path=source_path,
        sections=sections,
        key_values=key_values,
        list_items=list_items,
        extracted_fields=extracted_fields,
    )
