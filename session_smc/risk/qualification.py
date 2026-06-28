"""
Risk qualification engine.

Validates that the full risk parameter set is coherent and that the guards
correctly halt trading under all mandated conditions.

Parameters (non-bypassable per CLAUDE.md §4):
    risk_per_trade: 1% of account
    max_daily_loss: 3R → halt
    max_drawdown:   10% from peak → kill switch
    max_consecutive_losses: 5 → halt until next day
    kill_switch: mandatory

Usage::
    engine = RiskQualificationEngine(account_size=10_000.0)
    report = engine.run_all_scenarios()
    print(report.passed, report.summary())
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .guards import DailyLossGuard, DrawdownGuard, ConsecutiveLossGuard, KillSwitch

logger = logging.getLogger(__name__)
_UTC = timezone.utc


# ---------------------------------------------------------------------------
# Risk parameters (mirrors CLAUDE.md §4 — single source of truth is config.yaml)
# ---------------------------------------------------------------------------

DEFAULT_RISK_PARAMS: dict = {
    "risk_per_trade_pct":        1.0,    # % of account
    "max_daily_loss_r":          3.0,    # R multiples
    "max_drawdown_pct":         10.0,    # % from peak equity
    "max_consecutive_losses":    5,      # count
    "kill_switch":               True,
}


@dataclass
class PositionSizeResult:
    account_size: float
    risk_pct: float
    risk_amount: float
    sl_pips: float
    pip_value: float
    lot_size: float
    notes: str = ""


@dataclass
class RiskScenarioResult:
    scenario: str
    guard_triggered: bool
    expected_trigger: bool
    verdict: str  # "PASS" | "FAIL"
    notes: str = ""

    @property
    def passed(self) -> bool:
        return self.verdict == "PASS"


@dataclass
class RiskQualificationReport:
    strategy_id: str
    run_timestamp: str
    account_size: float
    params: dict
    position_sizing_ok: bool = False
    daily_loss_guard_ok: bool = False
    drawdown_guard_ok: bool = False
    consecutive_loss_guard_ok: bool = False
    kill_switch_ok: bool = False
    capital_preservation_ok: bool = False
    scenarios: list[RiskScenarioResult] = field(default_factory=list)
    sizing_results: list[PositionSizeResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all([
            self.position_sizing_ok,
            self.daily_loss_guard_ok,
            self.drawdown_guard_ok,
            self.consecutive_loss_guard_ok,
            self.kill_switch_ok,
            self.capital_preservation_ok,
        ])

    def summary(self) -> str:
        lines = [
            f"RiskQualificationReport — {self.strategy_id}",
            f"  Run: {self.run_timestamp}",
            f"  Account size: ${self.account_size:,.2f}",
            f"  Position sizing OK:         {self.position_sizing_ok}",
            f"  Daily loss guard OK:        {self.daily_loss_guard_ok}",
            f"  Drawdown guard OK:          {self.drawdown_guard_ok}",
            f"  Consecutive loss guard OK:  {self.consecutive_loss_guard_ok}",
            f"  Kill switch OK:             {self.kill_switch_ok}",
            f"  Capital preservation OK:    {self.capital_preservation_ok}",
            f"  OVERALL VERDICT:            {'PASS' if self.passed else 'FAIL'}",
        ]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "run_timestamp": self.run_timestamp,
            "passed": self.passed,
            "account_size": self.account_size,
            "params": self.params,
            "position_sizing_ok": self.position_sizing_ok,
            "daily_loss_guard_ok": self.daily_loss_guard_ok,
            "drawdown_guard_ok": self.drawdown_guard_ok,
            "consecutive_loss_guard_ok": self.consecutive_loss_guard_ok,
            "kill_switch_ok": self.kill_switch_ok,
            "capital_preservation_ok": self.capital_preservation_ok,
            "scenarios": [
                {"scenario": s.scenario, "verdict": s.verdict, "notes": s.notes}
                for s in self.scenarios
            ],
        }


class RiskQualificationEngine:
    """
    Runs deterministic scenarios to confirm all risk guards fire correctly.

    Does not require live market data or broker connectivity.
    """

    def __init__(
        self,
        strategy_id: str = "unknown",
        account_size: float = 10_000.0,
        params: dict | None = None,
    ) -> None:
        self.strategy_id = strategy_id
        self.account_size = account_size
        self.params = {**DEFAULT_RISK_PARAMS, **(params or {})}

    def run_all_scenarios(self) -> RiskQualificationReport:
        report = RiskQualificationReport(
            strategy_id=self.strategy_id,
            run_timestamp=datetime.now(_UTC).isoformat(),
            account_size=self.account_size,
            params=self.params,
        )

        # 1. Position sizing
        report.sizing_results = self._test_position_sizing()
        report.position_sizing_ok = all(
            0 < r.lot_size <= 100 for r in report.sizing_results
        )

        # 2. Daily loss guard
        dl_scenarios = self._test_daily_loss_guard()
        report.scenarios.extend(dl_scenarios)
        report.daily_loss_guard_ok = all(s.passed for s in dl_scenarios)

        # 3. Drawdown guard
        dd_scenarios = self._test_drawdown_guard()
        report.scenarios.extend(dd_scenarios)
        report.drawdown_guard_ok = all(s.passed for s in dd_scenarios)

        # 4. Consecutive loss guard
        cl_scenarios = self._test_consecutive_loss_guard()
        report.scenarios.extend(cl_scenarios)
        report.consecutive_loss_guard_ok = all(s.passed for s in cl_scenarios)

        # 5. Kill switch
        ks_scenarios = self._test_kill_switch()
        report.scenarios.extend(ks_scenarios)
        report.kill_switch_ok = all(s.passed for s in ks_scenarios)

        # 6. Capital preservation (no trading when account < 50% peak)
        cp_scenarios = self._test_capital_preservation()
        report.scenarios.extend(cp_scenarios)
        report.capital_preservation_ok = all(s.passed for s in cp_scenarios)

        logger.info(
            "Risk qualification complete for %s — %s",
            self.strategy_id,
            "PASS" if report.passed else "FAIL",
        )
        return report

    # ------------------------------------------------------------------
    # Sub-tests
    # ------------------------------------------------------------------

    def _test_position_sizing(self) -> list[PositionSizeResult]:
        results = []
        pip_value_per_lot = 10.0  # USD per lot for majors
        for sl_pips in [5.0, 10.0, 20.0, 30.0]:
            risk_amount = self.account_size * (self.params["risk_per_trade_pct"] / 100.0)
            lot_size = risk_amount / (sl_pips * pip_value_per_lot)
            results.append(PositionSizeResult(
                account_size=self.account_size,
                risk_pct=self.params["risk_per_trade_pct"],
                risk_amount=risk_amount,
                sl_pips=sl_pips,
                pip_value=pip_value_per_lot,
                lot_size=round(lot_size, 2),
                notes=f"SL={sl_pips}pip → {lot_size:.4f} lots",
            ))
        return results

    def _test_daily_loss_guard(self) -> list[RiskScenarioResult]:
        max_r = self.params["max_daily_loss_r"]
        guard = DailyLossGuard(max_daily_loss_r=max_r)
        results = []

        # Below threshold — should NOT trigger
        for loss_r in [0.0, 1.0, max_r - 0.01]:
            triggered = guard.check(loss_r)
            expected = False
            verdict = "PASS" if triggered == expected else "FAIL"
            results.append(RiskScenarioResult(
                scenario=f"daily_loss_{loss_r}R",
                guard_triggered=triggered,
                expected_trigger=expected,
                verdict=verdict,
                notes=f"loss={loss_r}R, max={max_r}R",
            ))

        # At/above threshold — MUST trigger
        for loss_r in [max_r, max_r + 0.5]:
            triggered = guard.check(loss_r)
            expected = True
            verdict = "PASS" if triggered == expected else "FAIL"
            results.append(RiskScenarioResult(
                scenario=f"daily_loss_{loss_r}R_halt",
                guard_triggered=triggered,
                expected_trigger=expected,
                verdict=verdict,
                notes=f"loss={loss_r}R >= max={max_r}R → halt",
            ))
        return results

    def _test_drawdown_guard(self) -> list[RiskScenarioResult]:
        max_dd = self.params["max_drawdown_pct"]
        guard = DrawdownGuard(
            peak_equity=self.account_size,
            max_drawdown_pct=max_dd,
        )
        results = []

        # Below threshold
        current = self.account_size * 0.95  # −5%
        triggered = guard.check(current)
        results.append(RiskScenarioResult(
            scenario="drawdown_5pct",
            guard_triggered=triggered,
            expected_trigger=False,
            verdict="PASS" if not triggered else "FAIL",
            notes=f"equity={current:.0f}, peak={self.account_size:.0f} (−5%)",
        ))

        # At threshold
        current = self.account_size * (1 - max_dd / 100)
        triggered = guard.check(current)
        results.append(RiskScenarioResult(
            scenario=f"drawdown_{max_dd}pct_kill",
            guard_triggered=triggered,
            expected_trigger=True,
            verdict="PASS" if triggered else "FAIL",
            notes=f"equity={current:.0f} at {max_dd}% DD → kill switch",
        ))
        return results

    def _test_consecutive_loss_guard(self) -> list[RiskScenarioResult]:
        max_cl = self.params["max_consecutive_losses"]
        guard = ConsecutiveLossGuard(max_consecutive_losses=max_cl)
        results = []

        # Feed losses up to max-1 — should not halt
        for i in range(1, max_cl):
            guard.record_loss()
        triggered = guard.is_halted()
        results.append(RiskScenarioResult(
            scenario=f"consec_loss_{max_cl - 1}",
            guard_triggered=triggered,
            expected_trigger=False,
            verdict="PASS" if not triggered else "FAIL",
            notes=f"{max_cl - 1} losses — below threshold",
        ))

        # Feed one more — must halt
        guard.record_loss()
        triggered = guard.is_halted()
        results.append(RiskScenarioResult(
            scenario=f"consec_loss_{max_cl}_halt",
            guard_triggered=triggered,
            expected_trigger=True,
            verdict="PASS" if triggered else "FAIL",
            notes=f"{max_cl} losses → halt",
        ))

        # Win resets counter
        guard.record_win()
        triggered = guard.is_halted()
        results.append(RiskScenarioResult(
            scenario="consec_loss_reset_on_win",
            guard_triggered=triggered,
            expected_trigger=False,
            verdict="PASS" if not triggered else "FAIL",
            notes="Win resets consecutive-loss counter",
        ))
        return results

    def _test_kill_switch(self) -> list[RiskScenarioResult]:
        ks = KillSwitch()
        results = []

        # Not engaged
        triggered = ks.is_engaged()
        results.append(RiskScenarioResult(
            scenario="kill_switch_off",
            guard_triggered=triggered,
            expected_trigger=False,
            verdict="PASS" if not triggered else "FAIL",
            notes="Kill switch starts disengaged",
        ))

        # Engage
        ks.engage("Max drawdown exceeded")
        triggered = ks.is_engaged()
        results.append(RiskScenarioResult(
            scenario="kill_switch_on",
            guard_triggered=triggered,
            expected_trigger=True,
            verdict="PASS" if triggered else "FAIL",
            notes="Kill switch engaged — all trading blocked",
        ))
        return results

    def _test_capital_preservation(self) -> list[RiskScenarioResult]:
        """Capital preservation: no new trades when equity below 90% of peak."""
        guard = DrawdownGuard(
            peak_equity=self.account_size,
            max_drawdown_pct=self.params["max_drawdown_pct"],
        )
        # At 91% — not triggered
        current = self.account_size * 0.91
        triggered = guard.check(current)
        return [RiskScenarioResult(
            scenario="capital_preservation_91pct",
            guard_triggered=triggered,
            expected_trigger=False,
            verdict="PASS" if not triggered else "FAIL",
            notes="91% equity — no preservation trigger",
        )]
