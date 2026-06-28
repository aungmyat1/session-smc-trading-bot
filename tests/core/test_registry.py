"""Tests for core.strategy_registry."""

import pytest
from core.signal import Signal
from core.base_strategy import BaseStrategy
from core.strategy_registry import (
    register_strategy, get_strategy, list_strategies, clear_registry,
    load_strategy_catalog, get_strategy_manifest, list_catalog_strategies,
    strategy_lifecycle_status, strategy_lifecycle_rank, is_strategy_approved,
    can_deploy_strategy, get_current_strategy_name, get_current_strategy_manifest,
    get_strategy_spec_path, get_strategy_spec_text, set_current_strategy,
)


class _DummyStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "DUMMY"

    def generate_signal(self, data: dict):
        return None


class _AnotherStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "ANOTHER"

    def generate_signal(self, data: dict):
        return None


@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield
    clear_registry()


class TestRegistry:
    def test_register_and_get(self):
        s = _DummyStrategy()
        register_strategy(s)
        assert get_strategy("DUMMY") is s

    def test_get_unknown_returns_none(self):
        assert get_strategy("NONEXISTENT") is None

    def test_list_empty(self):
        assert list_strategies() == []

    def test_list_sorted(self):
        register_strategy(_AnotherStrategy())
        register_strategy(_DummyStrategy())
        assert list_strategies() == ["ANOTHER", "DUMMY"]

    def test_overwrite_registration(self):
        s1 = _DummyStrategy()
        s2 = _DummyStrategy()
        register_strategy(s1)
        register_strategy(s2)
        assert get_strategy("DUMMY") is s2

    def test_base_strategy_is_abstract(self):
        with pytest.raises(TypeError):
            BaseStrategy()


class TestStrategyCatalog:
    def test_catalog_loads_default_entries(self):
        catalog = load_strategy_catalog()
        assert "ST-A2" in catalog
        assert catalog["ST-A2"]["approved"] is True
        assert catalog["D2E3"]["status"] == "research"
        assert get_current_strategy_name() == "ST-A2"

    def test_get_manifest(self):
        manifest = get_strategy_manifest("ST-A2")
        assert manifest is not None
        assert manifest["version"] == "2.1"
        current = get_current_strategy_manifest()
        assert current is not None
        assert current["status"] == "walk_forward"
        spec_path = get_strategy_spec_path("ST-A2")
        assert spec_path is not None and spec_path.name == "strategy_spec.md"
        spec_text = get_strategy_spec_text("ST-A2")
        assert spec_text is not None and spec_text.startswith("# Strategy: ST-A2")

    def test_list_catalog_strategies_sorted(self):
        strategies = list_catalog_strategies()
        assert strategies == sorted(strategies)
        assert "AdaptiveSMC" in strategies

    def test_lifecycle_status_normalized(self):
        assert strategy_lifecycle_status("ST-A2") == "walk_forward"
        assert strategy_lifecycle_rank("draft") < strategy_lifecycle_rank("live")

    def test_approval_and_deploy_gate(self):
        assert is_strategy_approved("ST-A2") is True
        assert can_deploy_strategy("ST-A2", target_stage="walk_forward") is True
        assert can_deploy_strategy("D2E3", target_stage="demo") is False

    def test_catalog_can_be_loaded_from_custom_path(self, tmp_path):
        spec = tmp_path / "spec.md"
        spec.write_text("# Custom Strategy\n", encoding="utf-8")
        custom = tmp_path / "strategy_catalog.yaml"
        custom.write_text(
            """
current_strategy: TestStrategy
strategies:
  TestStrategy:
    status: demo
    approved: true
    version: "1.0"
    strategy_spec_path: spec.md
""".strip()
        )
        catalog = load_strategy_catalog(custom)
        assert catalog["TestStrategy"]["status"] == "demo"
        assert get_strategy_manifest("TestStrategy", custom)["approved"] is True
        assert get_current_strategy_name(custom) == "TestStrategy"
        assert get_strategy_spec_path("TestStrategy", custom) == spec
        assert get_strategy_spec_text("TestStrategy", custom) == "# Custom Strategy\n"

    def test_set_current_strategy_updates_pointer(self, tmp_path):
        custom = tmp_path / "strategy_catalog.yaml"
        custom.write_text(
            """
current_strategy: OldStrategy
strategies:
  OldStrategy:
    status: research
    approved: false
    version: "1.0"
  NewStrategy:
    status: demo
    approved: true
    version: "1.0"
""".strip()
        )
        manifest = set_current_strategy("NewStrategy", custom)
        assert manifest["current"] is True
        assert get_current_strategy_name(custom) == "NewStrategy"
        assert get_strategy_manifest("OldStrategy", custom)["current"] is False
