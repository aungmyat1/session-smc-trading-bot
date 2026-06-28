"""Tests for core.strategy_registry."""

import pytest
from core.base_strategy import BaseStrategy
from core.strategy_registry import (
    register_strategy, get_strategy, list_strategies, clear_registry,
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
