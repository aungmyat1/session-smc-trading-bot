from __future__ import annotations

from pathlib import Path

import yaml

from shared.configuration.symbols import enabled_symbols, symbol_metadata, validate_symbol


def test_btcusdt_is_research_crypto_and_not_execution_enabled() -> None:
    metadata = symbol_metadata("BTC/USDT")

    assert metadata.symbol == "BTCUSDT"
    assert metadata.asset_class == "crypto"
    assert metadata.quote_currency == "USDT"
    assert metadata.market_type == "spot_or_perpetual_research"
    assert metadata.session_model == "crypto_24_7"
    assert metadata.timezone == "UTC"
    assert metadata.pip_model == "crypto_tick"
    assert metadata.default_data_timeframe == "M1"
    assert metadata.live_execution_allowed is False
    assert "BTCUSDT" in enabled_symbols("research")
    assert "BTCUSDT" not in enabled_symbols("execution")
    assert validate_symbol("BTCUSDT", scope="research").valid
    assert not validate_symbol("BTCUSDT", scope="execution").valid
    assert not validate_symbol("BTCUSDT", scope="live_execution").valid


def test_btcusd_is_dukascopy_research_only_crypto() -> None:
    metadata = symbol_metadata("BTCUSD")
    assert metadata.asset_class == "crypto"
    assert metadata.market_type == "dukascopy_cfd_research"
    assert metadata.session_model == "crypto_24_7"
    assert "BTCUSD" in enabled_symbols("research")
    assert "BTCUSD" not in enabled_symbols("execution")
    assert not validate_symbol("BTCUSD", scope="live_execution").valid


def test_btcusdt_uses_crypto_sessions_not_forex_sessions() -> None:
    for session in ("Asia", "London", "NewYork", "Overlap", "Weekend", "24_7"):
        assert validate_symbol("BTCUSDT", session=session).valid
    rejected = validate_symbol("BTCUSDT", session="Crypto24h")
    assert not rejected.valid


def test_crypto_validation_warns_when_market_assumptions_are_missing() -> None:
    result = validate_symbol(
        "BTCUSDT",
        metadata_override={
            "data_source": None,
            "fee_model": None,
            "tick_size": None,
            "price_precision": None,
            "slippage_model": None,
            "trading_hours": None,
            "funding_cost": None,
        },
    )

    assert result.valid
    assert len(result.warnings) == 7
    assert any("fee_model" in warning for warning in result.warnings)
    assert any("funding_cost" in warning for warning in result.warnings)


def test_existing_symbol_scope_is_unchanged() -> None:
    assert enabled_symbols("research")[:3] == ("EURUSD", "GBPUSD", "XAUUSD")
    assert enabled_symbols("execution") == ("EURUSD", "GBPUSD", "XAUUSD")
    assert symbol_metadata("EURUSD").pip_model == "forex_pip"
    assert symbol_metadata("GBPUSD").pip_model == "forex_pip"
    assert symbol_metadata("XAUUSD").asset_class == "metals"


def test_catalog_groups_are_consistent_with_metadata() -> None:
    catalog = yaml.safe_load((Path(__file__).resolve().parents[2] / "config" / "symbols.yaml").read_text())
    grouped = {
        symbol: asset_class
        for asset_class, symbols in catalog["supported_symbols"].items()
        for symbol in symbols
    }
    for symbol, details in catalog["symbols"].items():
        expected_group = "metals" if details["asset_class"] == "metals" else details["asset_class"]
        assert grouped[symbol] == expected_group
