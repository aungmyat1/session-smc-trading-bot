"""Strategy rule validator — validates every institutional SMC/ICT trading rule."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from agents.testing.agent import Status, StageResult

logger = logging.getLogger(__name__)


class RuleStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"


@dataclass
class RuleResult:
    rule: str
    status: RuleStatus
    detail: str = ""


class StrategyValidator:
    """Validates all institutional SMC/ICT trading rules against config and code."""

    _CONFIG_CANDIDATES = [
        "config/strategy.yaml",
        "config/strategy_catalog.yaml",
        "config/validation.yaml",
        "config/risk.yaml",
    ]

    def __init__(self, root: Path, config: dict[str, Any]) -> None:
        self._root = root
        self._min_score: float = float(config.get("minimum_strategy_score", 80.0))
        self._min_rr: float = float(config.get("minimum_rr", 1.5))
        self._max_risk_pct: float = float(config.get("maximum_risk_pct", 2.0))
        self._max_daily_loss_pct: float = float(config.get("maximum_daily_loss", 5.0))

    def validate(self) -> StageResult:
        strategy_config = self._load_strategy_config()
        # Build corpus once and reuse across all validators.
        corpus = self._build_code_corpus()
        results: list[RuleResult] = []

        # Session rules
        results += self._validate_sessions(strategy_config, corpus)
        # Risk rules
        results += self._validate_risk(strategy_config, corpus)
        # Entry condition rules
        results += self._validate_entry_conditions(strategy_config, corpus)
        # SMC structure rules
        results += self._validate_smc_structures(strategy_config, corpus)
        # Weekend / market-closed protection
        results += self._validate_protection_rules(strategy_config, corpus)
        # Code-level checks
        results += self._validate_code_presence()

        n_pass = sum(1 for r in results if r.status == RuleStatus.PASS)
        n_warn = sum(1 for r in results if r.status == RuleStatus.WARNING)
        n_fail = sum(1 for r in results if r.status == RuleStatus.FAIL)
        total = len(results)
        # WARNINGs count as half credit; hard FAILs count as zero.
        score = round(((n_pass + n_warn * 0.5) / total * 100.0) if total > 0 else 0.0, 1)

        errors = [f"{r.rule}: {r.detail}" for r in results if r.status == RuleStatus.FAIL]
        warnings = [f"{r.rule}: {r.detail}" for r in results if r.status == RuleStatus.WARNING]

        # Fail only when hard FAIL rules exist or score falls below minimum.
        status = Status.FAIL if (n_fail > 0 or score < self._min_score) else Status.PASS

        return StageResult(
            name="strategy_validation",
            status=status,
            score=score,
            details={
                "total_rules": total,
                "passed": n_pass,
                "warnings": n_warn,
                "failed": n_fail,
                "rule_results": [{"rule": r.rule, "status": r.status.value, "detail": r.detail} for r in results],
            },
            errors=errors,
            warnings=warnings,
        )

    # -------------------------------------------------------------------------
    # Config loading
    # -------------------------------------------------------------------------

    def _load_strategy_config(self) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for rel in self._CONFIG_CANDIDATES:
            p = self._root / rel
            if p.exists():
                try:
                    data = yaml.safe_load(p.read_text()) or {}
                    merged.update(data)
                    logger.debug("Loaded strategy config: %s", p)
                except yaml.YAMLError as exc:
                    logger.warning("Could not parse %s: %s", p, exc)
        return merged

    # -------------------------------------------------------------------------
    # Rule groups
    # -------------------------------------------------------------------------

    def _validate_sessions(self, cfg: dict[str, Any], corpus: str = "") -> list[RuleResult]:
        results: list[RuleResult] = []
        # Accept session definition in config OR in source code.
        sessions_key_found = (
            any(k in cfg for k in ("sessions", "kill_zones", "session_filter", "london", "new_york"))
            or any(kw in corpus for kw in ("session_filter", "london_session", "london", "kill_zone"))
        )
        results.append(RuleResult(
            "SESSION_DEFINITION",
            RuleStatus.PASS if sessions_key_found else RuleStatus.WARNING,
            "" if sessions_key_found else "No session definition found in config or code",
        ))

        required_sessions = {"london", "new_york", "asian"}
        for sess in required_sessions:
            defined = self._cfg_contains(cfg, sess) or sess.replace("_", "") in corpus
            results.append(RuleResult(
                f"SESSION_{sess.upper()}",
                RuleStatus.PASS if defined else RuleStatus.WARNING,
                "" if defined else f"{sess} session not found in config or code",
            ))

        kill_zones = self._cfg_contains(cfg, "kill_zone") or self._cfg_contains(cfg, "killzone")
        results.append(RuleResult(
            "KILL_ZONES",
            RuleStatus.PASS if kill_zones else RuleStatus.WARNING,
            "" if kill_zones else "Kill zone definition not found in config",
        ))
        return results

    def _validate_risk(self, cfg: dict[str, Any], corpus: str = "") -> list[RuleResult]:
        results: list[RuleResult] = []

        # Risk-reward
        rr_val = self._extract_numeric(cfg, ["rr", "risk_reward", "reward_ratio", "min_rr"])
        if rr_val is None:
            results.append(RuleResult("RISK_REWARD", RuleStatus.WARNING, "RR not found in config"))
        elif rr_val < self._min_rr:
            results.append(RuleResult("RISK_REWARD", RuleStatus.FAIL, f"RR={rr_val} below minimum {self._min_rr}"))
        else:
            results.append(RuleResult("RISK_REWARD", RuleStatus.PASS))

        # Max risk per trade
        risk_pct = self._extract_numeric(cfg, ["risk_pct", "risk_percent", "max_risk", "position_risk"])
        if risk_pct is None:
            results.append(RuleResult("MAX_RISK_PER_TRADE", RuleStatus.WARNING, "risk_pct not found"))
        elif risk_pct > self._max_risk_pct:
            results.append(RuleResult("MAX_RISK_PER_TRADE", RuleStatus.FAIL, f"risk_pct={risk_pct}% exceeds {self._max_risk_pct}%"))
        else:
            results.append(RuleResult("MAX_RISK_PER_TRADE", RuleStatus.PASS))

        # Max daily loss
        daily_loss = self._extract_numeric(cfg, ["max_daily_loss", "daily_loss_limit", "daily_drawdown"])
        if daily_loss is None:
            results.append(RuleResult("MAX_DAILY_LOSS", RuleStatus.WARNING, "max_daily_loss not found"))
        elif daily_loss > self._max_daily_loss_pct:
            results.append(RuleResult("MAX_DAILY_LOSS", RuleStatus.FAIL, f"max_daily_loss={daily_loss}% exceeds {self._max_daily_loss_pct}%"))
        else:
            results.append(RuleResult("MAX_DAILY_LOSS", RuleStatus.PASS))

        # Stop loss required — check config and code
        sl_defined = (
            self._cfg_contains(cfg, "stop_loss")
            or self._cfg_contains(cfg, "sl")
            or "stop_loss" in corpus
            or "sl_price" in corpus
            or "stoploss" in corpus
        )
        results.append(RuleResult(
            "STOP_LOSS_REQUIRED",
            RuleStatus.PASS if sl_defined else RuleStatus.FAIL,
            "" if sl_defined else "Stop-loss implementation not found — mandatory",
        ))

        return results

    def _validate_entry_conditions(self, cfg: dict[str, Any], corpus: str = "") -> list[RuleResult]:
        results: list[RuleResult] = []
        checks = [
            ("BIAS_REQUIRED", ["bias", "daily_bias", "direction"]),
            ("PREMIUM_DISCOUNT", ["premium", "discount", "equilibrium"]),
            ("LIQUIDITY_SWEEP", ["liquidity", "sweep", "bsl", "ssl"]),
            ("INVALID_ENTRY_GUARD", ["invalid_entry", "entry_guard", "filter"]),
            ("DUPLICATE_ENTRY_GUARD", ["duplicate", "one_trade", "single_position"]),
        ]
        for rule_name, keys in checks:
            found = any(self._cfg_contains(cfg, k) for k in keys) or any(k in corpus for k in keys)
            results.append(RuleResult(
                rule_name,
                RuleStatus.PASS if found else RuleStatus.WARNING,
                "" if found else f"Keywords {keys} not found in config or code",
            ))
        return results

    def _validate_smc_structures(self, cfg: dict[str, Any], corpus: str = "") -> list[RuleResult]:
        results: list[RuleResult] = []
        structures = [
            ("BOS", ["bos", "break_of_structure", "breakofstructure"]),
            ("CHOCH", ["choch", "change_of_character", "changeofcharacter"]),
            ("FVG", ["fvg", "fair_value_gap", "imbalance"]),
            ("ORDER_BLOCK", ["order_block", "orderblock", "ob_"]),
            ("MITIGATION", ["mitigation", "mitigated"]),
        ]
        for rule_name, keys in structures:
            found = any(self._cfg_contains(cfg, k) for k in keys) or any(k in corpus for k in keys)
            results.append(RuleResult(
                rule_name,
                RuleStatus.PASS if found else RuleStatus.WARNING,
                "" if found else f"SMC structure {rule_name} not found in config or code",
            ))
        return results

    def _validate_protection_rules(self, cfg: dict[str, Any], corpus: str = "") -> list[RuleResult]:
        results: list[RuleResult] = []
        weekend = (
            self._cfg_contains(cfg, "weekend")
            or self._cfg_contains(cfg, "friday_close")
            or "weekend" in corpus
            or "friday" in corpus
        )
        results.append(RuleResult(
            "WEEKEND_PROTECTION",
            RuleStatus.PASS if weekend else RuleStatus.WARNING,
            "" if weekend else "Weekend protection not found in config or code",
        ))
        market_closed = (
            self._cfg_contains(cfg, "market_closed")
            or self._cfg_contains(cfg, "market_hours")
            or "market_closed" in corpus
            or "is_market_open" in corpus
            or "market_hours" in corpus
        )
        results.append(RuleResult(
            "MARKET_CLOSED_PROTECTION",
            RuleStatus.PASS if market_closed else RuleStatus.WARNING,
            "" if market_closed else "Market-closed protection not found in config or code",
        ))
        return results

    # Directories to scan for SMC code presence (excludes tests and cache).
    _CODE_SCAN_DIRS = ["strategies", "strategy", "strategy_validation", "core", "src", "svos"]
    _CODE_EXCLUDE = {"__pycache__", ".git", "archive", "tests"}

    def _validate_code_presence(self) -> list[RuleResult]:
        """Verify that key SMC and risk components are implemented in source code."""
        # Build a searchable corpus from all non-test Python source files.
        corpus = self._build_code_corpus()

        checks: list[tuple[str, list[str]]] = [
            ("SMC_BOS_IMPL", ["break_of_structure", "bos", "BreakOfStructure"]),
            ("SMC_CHOCH_IMPL", ["change_of_character", "choch", "ChangeOfCharacter"]),
            ("SMC_FVG_IMPL", ["fair_value_gap", "fvg", "FairValueGap"]),
            ("SMC_ORDER_BLOCK_IMPL", ["order_block", "OrderBlock", "ob_"]),
            ("SMC_LIQUIDITY_IMPL", ["liquidity", "sweep", "bsl", "ssl"]),
            ("SESSION_FILTER_IMPL", ["session", "london", "new_york", "kill_zone"]),
            ("RISK_ENGINE_IMPL", ["risk", "stop_loss", "position_size", "RiskEngine"]),
            ("STRATEGY_ADAPTER_IMPL", ["adapter", "Adapter", "strategy_"]),
        ]

        results: list[RuleResult] = []
        for rule_name, keywords in checks:
            found = any(kw.lower() in corpus for kw in keywords)
            results.append(RuleResult(
                rule_name,
                RuleStatus.PASS if found else RuleStatus.WARNING,
                "" if found else f"No source file contains any of {keywords}",
            ))

        # Check for validator pipeline (formal institutional validation).
        has_institutional = "institutional" in corpus or "strategy_validation" in corpus
        results.append(RuleResult(
            "INSTITUTIONAL_VALIDATOR",
            RuleStatus.PASS if has_institutional else RuleStatus.WARNING,
            "" if has_institutional else "Institutional validation pipeline not found",
        ))

        return results

    def _build_code_corpus(self) -> str:
        """Return concatenated lower-case contents of all scanned source files."""
        parts: list[str] = []
        for scan_dir in self._CODE_SCAN_DIRS:
            d = self._root / scan_dir
            if not d.exists():
                continue
            for py in d.rglob("*.py"):
                if self._CODE_EXCLUDE.intersection(py.parts):
                    continue
                try:
                    parts.append(py.read_text(errors="replace").lower())
                except OSError:
                    pass
        return " ".join(parts)

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _cfg_contains(cfg: dict[str, Any], key: str) -> bool:
        """Return True if `key` appears anywhere in the config (keys or string values)."""
        key_lower = key.lower()
        raw = str(cfg).lower()
        return key_lower in raw

    @staticmethod
    def _extract_numeric(cfg: dict[str, Any], keys: list[str]) -> float | None:
        for k in keys:
            if k in cfg:
                try:
                    return float(cfg[k])
                except (TypeError, ValueError):
                    pass
            # Search nested dicts one level deep.
            for v in cfg.values():
                if isinstance(v, dict) and k in v:
                    try:
                        return float(v[k])
                    except (TypeError, ValueError):
                        pass
        return None
