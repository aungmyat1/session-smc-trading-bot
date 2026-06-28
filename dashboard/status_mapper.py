from __future__ import annotations

from typing import Any


def normalize_status(value: Any) -> str:
    text = str(value or "").strip().upper()
    return text or "UNKNOWN"


def recommendation_badge(value: Any) -> str:
    text = normalize_status(value)
    aliases = {
        "READY FOR DEMO": "DEMO_READY",
        "READY": "CONTINUE",
        "PASS": "CONTINUE",
        "FAIL": "REVIEW",
        "BLOCKED": "PAUSE",
        "SHADOW": "REVIEW",
    }
    return aliases.get(text, text)


def health_to_status(value: Any) -> str:
    text = normalize_status(value)
    if text in {"PASS", "READY", "ONLINE"}:
        return "HEALTHY"
    if text in {"WARN", "SHADOW", "SKIP"}:
        return "WATCH"
    if text in {"FAIL", "BLOCKED", "OFFLINE"}:
        return "ALERT"
    return text
