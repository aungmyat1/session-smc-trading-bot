"""Canonical symbol metadata and scope validation."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml


@dataclass(frozen=True, slots=True)
class SymbolMetadata:
    symbol: str
    asset_class: str
    base_currency: str
    quote_currency: str
    market_type: str
    session_model: str
    timezone: str
    pip_model: str
    default_data_timeframe: str
    research_allowed: bool
    execution_allowed: bool
    live_execution_allowed: bool
    sessions: tuple[str, ...]
    details: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class SymbolValidation:
    valid: bool
    symbol: str
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def normalize_symbol(value: str) -> str:
    return "".join(ch for ch in str(value).upper() if ch.isalnum())


@lru_cache(maxsize=1)
def _catalog() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "config" / "symbols.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("symbols"), dict):
        raise ValueError("invalid symbol catalog")
    return payload


def symbol_metadata(symbol: str) -> SymbolMetadata:
    normalized = normalize_symbol(symbol)
    details = _catalog()["symbols"].get(normalized)
    if not isinstance(details, dict):
        raise KeyError(f"unknown symbol: {normalized}")
    return SymbolMetadata(
        symbol=normalized,
        asset_class=str(details["asset_class"]),
        base_currency=str(details["base_currency"]),
        quote_currency=str(details["quote_currency"]),
        market_type=str(details["market_type"]),
        session_model=str(details["session_model"]),
        timezone=str(details["timezone"]),
        pip_model=str(details["pip_model"]),
        default_data_timeframe=str(details["default_data_timeframe"]),
        research_allowed=bool(details.get("research_allowed")),
        execution_allowed=bool(details.get("execution_allowed")),
        live_execution_allowed=bool(details.get("live_execution_allowed")),
        sessions=tuple(str(v) for v in details.get("sessions", [])),
        details=details,
    )


def enabled_symbols(scope: str = "research") -> tuple[str, ...]:
    field = {"research": "research_allowed", "execution": "execution_allowed", "live_execution": "live_execution_allowed"}.get(scope)
    if field is None:
        raise ValueError(f"unknown symbol scope: {scope}")
    return tuple(name for name, details in _catalog()["symbols"].items() if details.get(field) is True)


def validate_symbol(
    symbol: str,
    *,
    scope: str = "research",
    session: str | None = None,
    metadata_override: Mapping[str, Any] | None = None,
) -> SymbolValidation:
    normalized = normalize_symbol(symbol)
    try:
        metadata = symbol_metadata(normalized)
    except KeyError:
        return SymbolValidation(False, normalized, (f"unknown symbol: {normalized}",))
    errors: list[str] = []
    if normalized not in enabled_symbols(scope):
        errors.append(f"{normalized} is not allowed for {scope}")
    if session and session not in metadata.sessions:
        errors.append(f"session {session} is not allowed for {normalized}")
    details = {**metadata.details, **dict(metadata_override or {})}
    warnings: list[str] = []
    if metadata.asset_class == "crypto":
        for field in ("data_source", "fee_model", "tick_size", "price_precision", "slippage_model", "trading_hours", "funding_cost"):
            if details.get(field) is None:
                warnings.append(f"crypto metadata is missing {field}")
    return SymbolValidation(not errors, normalized, tuple(errors), tuple(warnings))
