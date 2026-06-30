"""Tests for svos.shared.specification.StrategySpecification."""

from __future__ import annotations

import pytest

from svos.shared.specification import StrategySpecification, _spec_sha256


_FULL_SPEC = """Strategy: London BOS Reversal
Instrument: EURUSD
Timeframe: M15
Session: London killzone 07:00-10:00 UTC
Entry Rules: Enter long after liquidity sweep of prior session low with BOS and CHoCH confirmation.
Confirmation: H1 bias must be bullish; wait for market structure flip before entry.
Invalidation: No CHoCH within 3 candles; high-impact news within session window.
Exit Rules: Take profit at 2R; break-even at 1R.
Stop Loss: 2 pips below the swept low.
Risk Model: 0.3% fixed fractional risk per trade. Kill switch at 2R daily loss.
Position Sizing: 0.01 lots per 1000 USD equity.
"""

_MINIMAL_SPEC = "Buy when price goes up. Sell when it goes down."

_MANIFEST = {
    "name": "London-BOS",
    "version": "1.0",
    "owner": "quant",
    "symbols": ["EURUSD"],
    "timeframes": ["M15"],
}


def test_from_text_returns_specification():
    spec = StrategySpecification.from_text(_FULL_SPEC, _MANIFEST)
    assert isinstance(spec, StrategySpecification)
    assert spec.version == "1.0"
    assert spec.owner == "quant"
    assert "EURUSD" in spec.symbols
    assert "M15" in spec.timeframes


def test_entry_rules_extracted():
    spec = StrategySpecification.from_text(_FULL_SPEC, _MANIFEST)
    assert "liquidity sweep" in spec.entry_rules.lower() or "enter" in spec.entry_rules.lower()


def test_exit_rules_include_stop():
    spec = StrategySpecification.from_text(_FULL_SPEC, _MANIFEST)
    assert spec.exit_rules


def test_risk_rules_extracted():
    spec = StrategySpecification.from_text(_FULL_SPEC, _MANIFEST)
    assert spec.risk_rules


def test_sessions_parsed():
    spec = StrategySpecification.from_text(_FULL_SPEC, _MANIFEST)
    assert len(spec.sessions) >= 1
    assert any("london" in s.lower() or "killzone" in s.lower() or "07" in s for s in spec.sessions)


def test_spec_hash_is_sha256():
    spec = StrategySpecification.from_text(_FULL_SPEC, _MANIFEST)
    expected = _spec_sha256(_FULL_SPEC)
    assert spec.spec_hash == expected
    assert len(spec.spec_hash) == 64


def test_spec_hash_changes_on_text_change():
    spec1 = StrategySpecification.from_text(_FULL_SPEC, _MANIFEST)
    spec2 = StrategySpecification.from_text(_FULL_SPEC + "\nAddendum: extra rule.", _MANIFEST)
    assert spec1.spec_hash != spec2.spec_hash


def test_spec_hash_stable_same_input():
    spec1 = StrategySpecification.from_text(_FULL_SPEC, _MANIFEST)
    spec2 = StrategySpecification.from_text(_FULL_SPEC, _MANIFEST)
    assert spec1.spec_hash == spec2.spec_hash


def test_validate_pass_on_full_spec():
    spec = StrategySpecification.from_text(_FULL_SPEC, _MANIFEST)
    errors = spec.validate()
    assert errors == [], f"Expected no errors, got: {errors}"


def test_validate_fails_on_missing_entry_rules():
    spec = StrategySpecification.from_text(_MINIMAL_SPEC, _MANIFEST)
    errors = spec.validate()
    assert any("SPEC-003" in e or "entry_rules" in e for e in errors)


def test_validate_fails_on_missing_risk_rules():
    spec = StrategySpecification.from_text(_MINIMAL_SPEC, _MANIFEST)
    errors = spec.validate()
    assert any("SPEC-005" in e or "risk_rules" in e for e in errors)


def test_validate_fails_on_empty_symbols():
    no_symbols_manifest = {**_MANIFEST, "symbols": []}
    spec = StrategySpecification.from_text(_FULL_SPEC, no_symbols_manifest)
    errors = spec.validate()
    assert any("symbols" in e.lower() for e in errors)


def test_validate_fails_on_missing_owner():
    no_owner = {**_MANIFEST, "owner": ""}
    spec = StrategySpecification.from_text(_FULL_SPEC, no_owner)
    errors = spec.validate()
    assert any("owner" in e.lower() for e in errors)


def test_to_dict_is_serializable():
    import json
    spec = StrategySpecification.from_text(_FULL_SPEC, _MANIFEST)
    d = spec.to_dict()
    assert json.dumps(d)  # no TypeError


def test_to_dict_has_expected_keys():
    spec = StrategySpecification.from_text(_FULL_SPEC, _MANIFEST)
    d = spec.to_dict()
    for key in ("entry_rules", "exit_rules", "risk_rules", "spec_hash", "symbols", "timeframes"):
        assert key in d, f"Missing key: {key}"


def test_frozen_immutable():
    spec = StrategySpecification.from_text(_FULL_SPEC, _MANIFEST)
    with pytest.raises((AttributeError, TypeError)):
        spec.entry_rules = "mutated"  # type: ignore[misc]


def test_data_requirements_populated():
    spec = StrategySpecification.from_text(_FULL_SPEC, _MANIFEST)
    assert spec.data_requirements.get("symbols") == ["EURUSD"]
    assert spec.data_requirements.get("timeframes") == ["M15"]
