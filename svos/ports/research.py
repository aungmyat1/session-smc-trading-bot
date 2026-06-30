"""Research pipeline port interfaces.

These Protocol classes define the contracts that research engine adapters must satisfy.
They contain no implementation — only method signatures and docstrings describing
the required return structure.

Concrete implementations live in svos/adapters/research_engines.py.
The application services in svos/application/ consume these ports, not the adapters.

All methods return plain dict so the application layer remains framework-agnostic.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AuditPort(Protocol):
    """Contract for Phase-1 strategy audit engines."""

    def run_audit(
        self,
        strategy: str,
        specification: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Run a strategy audit.

        Returns::

            {
                "status": "PASS" | "FAIL" | "FIX",
                "overall_score": float,           # 0.0–100.0
                "readiness_decision": str,         # e.g. "READY_FOR_REPLAY"
                "critical_issues": list[str],
                "warnings": list[str],
                "validator_results": list[dict],
                "recommendations": list[dict],
            }
        """
        ...


@runtime_checkable
class ReplayPort(Protocol):
    """Contract for Phase-2 historical replay engines."""

    def run_replay(
        self,
        strategy: str,
        dataset_id: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Replay a strategy over historical data.

        Returns::

            {
                "status": "PASS" | "FAIL" | "FIX",
                "trades": list[dict],              # individual trade records
                "trade_count": int,
                "checks": list[dict],              # rule-compliance check results
                "summary": dict,                   # aggregate stats
                "passed": bool,
            }
        """
        ...


@runtime_checkable
class BacktestPort(Protocol):
    """Contract for Phase-3 statistical validation (backtest) engines."""

    def run_backtest(
        self,
        strategy: str,
        dataset_id: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Run statistical validation on a trade set.

        Returns::

            {
                "status": "PASS" | "FAIL" | "FIX",
                "metrics": {
                    "trade_count": int,
                    "profit_factor": float,
                    "profit_factor_2x": float,
                    "expectancy": float,
                    "max_drawdown": float,
                    "win_rate": float,
                    "spread_included": bool,
                },
                "checks": list[dict],              # gate check results
                "passed": bool,
            }
        """
        ...


@runtime_checkable
class RobustnessPort(Protocol):
    """Contract for Phase-4 robustness validation engines."""

    def run_robustness(
        self,
        strategy: str,
        trades: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Run robustness tests on a trade set.

        Returns::

            {
                "status": "PASS" | "FAIL" | "FIX",
                "walk_forward": {"passed": bool, ...},
                "monte_carlo": {"passed": bool, ...},
                "sensitivity": {"passed": bool, ...},
                "regime": {"passed": bool, ...},
                "passed": bool,
            }
        """
        ...


@runtime_checkable
class VirtualDemoPort(Protocol):
    """Contract for Phase-5 virtual demo execution engines."""

    def run_virtual_demo(
        self,
        strategy: str,
        signals: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute a virtual demo run against a signal set.

        Returns::

            {
                "status": "PASS" | "FAIL",
                "drift_checks": list[dict],        # per-metric drift results
                "summary": {
                    "signal_count": int,
                    "filled_count": int,
                    "fill_rate": float,
                    "virtual_pf": float,
                    "expected_pf": float | None,
                },
                "passed": bool,
            }
        """
        ...
