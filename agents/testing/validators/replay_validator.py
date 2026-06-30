"""Historical replay validator — validates replay metrics against acceptance thresholds."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from agents.testing.agent import Status, StageResult

logger = logging.getLogger(__name__)

# Specific replay report locations — intentionally narrow to avoid
# misidentifying unrelated JSON files (test results, baselines) as replay reports.
_REPORT_CANDIDATES = [
    "reports/replay_report.json",
    "data/svos/reports/replay",
    "data/svos/reports/phase2",
    "data/reports/replay",
]


class ReplayValidator:
    """Validates historical replay output metrics against configured thresholds.

    If no replay report is found, the stage returns SKIP rather than FAIL —
    replay is an upstream SVOS stage and may not have run yet.
    """

    def __init__(self, root: Path, config: dict[str, Any]) -> None:
        self._root = root
        self._min_profit_factor: float = float(config.get("minimum_profit_factor", 1.0))
        self._min_win_rate: float = float(config.get("minimum_win_rate", 0.40))
        self._min_rr: float = float(config.get("minimum_rr", 1.5))
        self._max_drawdown: float = float(config.get("maximum_drawdown", 20.0))
        self._min_trades: int = int(config.get("minimum_trades", 50))

    def validate(self) -> StageResult:
        report = self._find_report()
        if report is None:
            return StageResult(
                name="historical_replay",
                status=Status.SKIP,
                score=100.0,
                details={"reason": "no replay report found — run SVOS Phase 2 first"},
            )

        errors: list[str] = []
        warnings: list[str] = []
        checks_passed = 0
        checks_total = 0

        def check(
            field: str,
            actual: float | None,
            threshold: float,
            *,
            above: bool = True,
            label: str | None = None,
        ) -> None:
            nonlocal checks_passed, checks_total
            checks_total += 1
            lbl = label or field
            if actual is None:
                warnings.append(f"{lbl}: not present in report")
                return
            ok = (actual >= threshold) if above else (actual <= threshold)
            if ok:
                checks_passed += 1
            else:
                direction = "≥" if above else "≤"
                errors.append(f"{lbl}: {actual} fails {direction} {threshold}")

        metrics = report.get("metrics", report)  # support flat or nested structure
        check(
            "signal_count",
            metrics.get("trade_count") or metrics.get("signal_count"),
            self._min_trades,
            label="SIGNAL_COUNT",
        )
        check(
            "profit_factor",
            metrics.get("profit_factor"),
            self._min_profit_factor,
            label="PROFIT_FACTOR",
        )
        check("win_rate", metrics.get("win_rate"), self._min_win_rate, label="WIN_RATE")
        check(
            "avg_rr",
            metrics.get("avg_rr") or metrics.get("average_rr"),
            self._min_rr,
            label="AVG_RR",
        )
        check(
            "max_drawdown",
            metrics.get("max_drawdown") or metrics.get("drawdown_pct"),
            self._max_drawdown,
            above=False,
            label="MAX_DRAWDOWN",
        )

        # Validate data integrity fields (not scored, just advisory).
        for integrity_field in ("missed_trades", "duplicate_trades", "invalid_fills"):
            val = metrics.get(integrity_field)
            if val is not None and val > 0:
                warnings.append(
                    f"{integrity_field}: {val} (non-zero — inspect replay log)"
                )

        score = round(
            (checks_passed / checks_total * 100.0) if checks_total > 0 else 0.0, 1
        )
        return StageResult(
            name="historical_replay",
            status=Status.FAIL if errors else Status.PASS,
            score=score,
            details={
                "report_source": str(report.get("_source", "unknown")),
                "checks_passed": checks_passed,
                "checks_total": checks_total,
                "metrics": metrics,
            },
            errors=errors,
            warnings=warnings,
        )

    def _find_report(self) -> dict[str, Any] | None:
        # 1. Direct file candidates
        for rel in _REPORT_CANDIDATES:
            p = self._root / rel
            if p.is_file() and p.suffix == ".json":
                return self._load_json(p)
            if p.is_dir():
                # Pick the newest JSON in the directory tree.
                jsons = sorted(
                    p.rglob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True
                )
                if jsons:
                    data = self._load_json(jsons[0])
                    if data:
                        data["_source"] = str(jsons[0])
                        return data
        return None

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any] | None:
        try:
            data = json.loads(path.read_text())
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Cannot load replay report %s: %s", path, exc)
        return None
