"""Typed strategy specification — structured representation of a strategy spec document.

A StrategySpecification is parsed from a human-readable Markdown/text specification
and a catalog manifest. It provides typed access to required rule sections and a
deterministic spec_hash for version-change detection.

Usage::

    spec = StrategySpecification.from_text(spec_text, catalog_manifest)
    errors = spec.validate()
    if not errors:
        # spec is complete and internally consistent
        version_rec = registry.ensure_spec_version(strategy, specification=spec_text, ...)
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any


# Regex patterns for extracting labelled sections from spec text.
# Each pattern matches "Label:" at line start, capturing everything until
# the next same-level label or end-of-text.
_LABEL_RE = re.compile(
    r"^([\w ]+?)\s*:\s*(.+?)(?=\n[\w ]+?\s*:|$)",
    re.MULTILINE | re.DOTALL,
)

_ENTRY_KEYS = frozenset({
    "entry rules", "entry rule", "entry", "signal", "setup",
    "entry condition", "entry conditions",
})
_CONFIRM_KEYS = frozenset({
    "confirmation", "confirmation rules", "confirmation rule",
    "filter", "bias filter",
})
_INVALIDATION_KEYS = frozenset({
    "invalidation", "invalidation rules", "invalidation rule",
    "cancel condition", "void condition",
})
_EXIT_KEYS = frozenset({
    "exit rules", "exit rule", "exit", "take profit", "tp",
    "profit target",
})
_RISK_KEYS = frozenset({
    "risk", "risk model", "risk rules", "risk rule",
    "position sizing", "position size", "lot size", "risk per trade",
})
_STOP_KEYS = frozenset({
    "stop loss", "sl", "stop", "stop-loss",
})
_SESSION_KEYS = frozenset({
    "session", "sessions", "time filter", "trading session", "trading hours",
})


def _extract_sections(text: str) -> dict[str, str]:
    """Return a lowercased-key dict of all 'Label: Value' sections in text."""
    sections: dict[str, str] = {}
    for match in _LABEL_RE.finditer(text):
        key = match.group(1).strip().lower()
        value = match.group(2).strip()
        sections[key] = value
    return sections


def _pick(sections: dict[str, str], keys: frozenset[str], default: str = "") -> str:
    for key in keys:
        if key in sections:
            return sections[key].strip()
    return default


def _spec_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class StrategySpecification:
    """Structured, typed representation of a strategy specification.

    All text fields are normalised strings extracted from the raw spec document.
    `spec_hash` is the SHA-256 of the original text — a change in hash means a
    new version must be registered.
    """

    strategy_id: str
    version: str
    owner: str
    symbols: tuple[str, ...]
    timeframes: tuple[str, ...]
    sessions: tuple[str, ...]
    entry_rules: str
    confirmation_rules: str
    invalidation_rules: str
    exit_rules: str
    risk_rules: str
    parameters: dict[str, Any]
    data_requirements: dict[str, Any]
    qualification_policy_version: str
    spec_hash: str

    @classmethod
    def from_text(
        cls,
        text: str,
        manifest: dict[str, Any],
    ) -> "StrategySpecification":
        """Parse a specification from raw text and a catalog manifest dict.

        Args:
            text: Full strategy specification text (Markdown or plain text).
            manifest: Catalog manifest dict for the strategy (from strategy_catalog.yaml).

        Returns:
            A populated StrategySpecification. Call `validate()` to check completeness.
        """
        sections = _extract_sections(text)

        strategy_id = str(manifest.get("slug", manifest.get("name", "")))
        version = str(manifest.get("version", ""))
        owner = str(manifest.get("owner", ""))

        raw_symbols = manifest.get("symbols", [])
        symbols: tuple[str, ...] = tuple(str(s) for s in raw_symbols) if isinstance(raw_symbols, list) else ()

        raw_timeframes = manifest.get("timeframes", [])
        timeframes: tuple[str, ...] = tuple(str(t) for t in raw_timeframes) if isinstance(raw_timeframes, list) else ()

        session_text = _pick(sections, _SESSION_KEYS)
        sessions: tuple[str, ...] = tuple(
            s.strip() for s in re.split(r"[;,]", session_text) if s.strip()
        ) if session_text else ()

        entry_rules = _pick(sections, _ENTRY_KEYS)
        confirmation_rules = _pick(sections, _CONFIRM_KEYS)
        invalidation_rules = _pick(sections, _INVALIDATION_KEYS)

        exit_rules = _pick(sections, _EXIT_KEYS)
        stop_text = _pick(sections, _STOP_KEYS)
        if stop_text and exit_rules:
            exit_rules = f"{exit_rules} | SL: {stop_text}"
        elif stop_text:
            exit_rules = f"SL: {stop_text}"

        risk_rules = _pick(sections, _RISK_KEYS)

        return cls(
            strategy_id=strategy_id,
            version=version,
            owner=owner,
            symbols=symbols,
            timeframes=timeframes,
            sessions=sessions,
            entry_rules=entry_rules,
            confirmation_rules=confirmation_rules,
            invalidation_rules=invalidation_rules,
            exit_rules=exit_rules,
            risk_rules=risk_rules,
            parameters={},
            data_requirements={
                "symbols": list(symbols),
                "timeframes": list(timeframes),
            },
            qualification_policy_version="svos-v1",
            spec_hash=_spec_sha256(text),
        )

    def validate(self) -> list[str]:
        """Return a list of validation error strings; empty list means valid.

        These checks mirror and extend the ad-hoc regex checks in IntakeService._validate_spec().
        """
        errors: list[str] = []
        if not self.entry_rules:
            errors.append("SPEC-003: entry_rules is missing — spec must describe an entry condition")
        if not self.exit_rules:
            errors.append("SPEC-004: exit_rules is missing — spec must define a stop-loss or exit condition")
        if not self.risk_rules:
            errors.append("SPEC-005: risk_rules is missing — spec must state a risk or position sizing rule")
        if not self.symbols:
            errors.append("CAT-SYMBOLS: symbols list is empty — catalog entry must declare at least one instrument")
        if not self.timeframes:
            errors.append("CAT-TIMEFRAMES: timeframes list is empty — catalog entry must declare at least one timeframe")
        if not self.owner:
            errors.append("CAT-OWNER: owner is missing in catalog manifest")
        if not self.version:
            errors.append("CAT-VERSION: version is missing in catalog manifest")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "version": self.version,
            "owner": self.owner,
            "symbols": list(self.symbols),
            "timeframes": list(self.timeframes),
            "sessions": list(self.sessions),
            "entry_rules": self.entry_rules,
            "confirmation_rules": self.confirmation_rules,
            "invalidation_rules": self.invalidation_rules,
            "exit_rules": self.exit_rules,
            "risk_rules": self.risk_rules,
            "parameters": self.parameters,
            "data_requirements": self.data_requirements,
            "qualification_policy_version": self.qualification_policy_version,
            "spec_hash": self.spec_hash,
        }
