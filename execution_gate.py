from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from execution_simulator.database.execution_log import ExecutionLog


@dataclass(slots=True)
class ExecutionGateConfig:
    minimum_signal_match: float = 0.99
    maximum_slippage_difference_pip: float = 0.5
    maximum_pf_difference: float = 0.10
    maximum_missing_orders: float = 0.01


@dataclass(slots=True)
class ExecutionGateResult:
    approved: bool
    signal_match: float
    average_slippage_pip: float
    maximum_slippage_pip: float
    pf_difference: float
    missing_orders: int
    total_signals: int
    total_orders: int
    details: list[str]

    @property
    def status(self) -> str:
        return "APPROVED FOR DEMO" if self.approved else "BLOCKED"


class ExecutionGate:
    """Deterministic pass/fail gate for execution validation."""

    def __init__(
        self,
        config: ExecutionGateConfig | None = None,
        log_path: str | Path = "execution_validation/execution_validation.sqlite3",
    ) -> None:
        self.config = config or ExecutionGateConfig()
        self.log = ExecutionLog(log_path)

    def evaluate(
        self,
        *,
        total_signals: int,
        total_orders: int,
        average_slippage_pip: float,
        maximum_slippage_pip: float,
        backtest_pf: float,
        virtual_pf: float,
    ) -> ExecutionGateResult:
        details: list[str] = []
        signal_match = (total_orders / total_signals) if total_signals else 0.0
        missing_orders = max(total_signals - total_orders, 0)
        pf_difference = (
            abs(virtual_pf - backtest_pf) / backtest_pf if backtest_pf else 0.0
        )

        approved = True

        if signal_match < self.config.minimum_signal_match:
            approved = False
            details.append(
                f"Signal match {signal_match:.2%} below minimum {self.config.minimum_signal_match:.2%}"
            )
        if average_slippage_pip > self.config.maximum_slippage_difference_pip:
            approved = False
            details.append(
                f"Average slippage {average_slippage_pip:.2f} pip above maximum {self.config.maximum_slippage_difference_pip:.2f} pip"
            )
        if maximum_slippage_pip > self.config.maximum_slippage_difference_pip:
            approved = False
            details.append(
                f"Maximum slippage {maximum_slippage_pip:.2f} pip above maximum {self.config.maximum_slippage_difference_pip:.2f} pip"
            )
        if pf_difference > self.config.maximum_pf_difference:
            approved = False
            details.append(
                f"PF difference {pf_difference:.2%} above maximum {self.config.maximum_pf_difference:.2%}"
            )
        if (
            total_signals
            and (missing_orders / total_signals) > self.config.maximum_missing_orders
        ):
            approved = False
            details.append(
                f"Missing orders {(missing_orders / total_signals):.2%} above maximum {self.config.maximum_missing_orders:.2%}"
            )

        return ExecutionGateResult(
            approved=approved,
            signal_match=signal_match,
            average_slippage_pip=average_slippage_pip,
            maximum_slippage_pip=maximum_slippage_pip,
            pf_difference=pf_difference,
            missing_orders=missing_orders,
            total_signals=total_signals,
            total_orders=total_orders,
            details=details,
        )

    def summarize(self, result: ExecutionGateResult) -> str:
        lines = [
            "EXECUTION VALIDATION",
            "",
            f"Signal Match: {result.signal_match:.1%} {'PASS' if result.signal_match >= self.config.minimum_signal_match else 'FAIL'}",
            f"Slippage: {result.average_slippage_pip:.2f} pip {'PASS' if result.average_slippage_pip <= self.config.maximum_slippage_difference_pip else 'FAIL'}",
            f"PF Difference: {result.pf_difference:.1%} {'PASS' if result.pf_difference <= self.config.maximum_pf_difference else 'FAIL'}",
            "",
            f"STATUS: {result.status}",
        ]
        if result.details:
            lines += ["", "DETAILS:"]
            lines.extend(f"- {detail}" for detail in result.details)
        return "\n".join(lines)
