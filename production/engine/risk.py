"""Fail-closed System 2 risk firewall."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from production.engine.execution_pipeline import ExecutionIntent, RiskDecision


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    equity: float
    balance: float
    free_margin: float
    daily_pnl: float = 0.0
    drawdown_percent: float = 0.0
    healthy: bool = True


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    timestamp: datetime
    spread_pips: float
    latency_ms: float = 0.0
    session: str = ""
    news_blackout: bool = False


@dataclass(frozen=True, slots=True)
class RiskContext:
    account: AccountSnapshot | None
    market: MarketSnapshot | None
    positions: tuple[Mapping[str, Any], ...] = ()
    pending_signal_ids: frozenset[str] = field(default_factory=frozenset)


class RiskFirewall:
    """Evaluate package policy without permissive defaults."""

    REQUIRED_POLICY = frozenset({"max_spread_pips", "max_daily_loss", "max_drawdown_percent", "max_positions", "max_risk_percent", "min_free_margin"})

    def __init__(self, policy: Mapping[str, Any], *, now: Callable[[], datetime] | None = None) -> None:
        self.policy = dict(policy)
        self.now = now or (lambda: datetime.now(timezone.utc))

    def evaluate(self, intent: ExecutionIntent, context: RiskContext | None = None) -> RiskDecision:
        missing = sorted(self.REQUIRED_POLICY - self.policy.keys())
        if missing:
            return RiskDecision(False, "POLICY_INCOMPLETE", {"missing": missing})
        if context is None or context.account is None or context.market is None:
            return RiskDecision(False, "RISK_CONTEXT_UNAVAILABLE")
        account, market = context.account, context.market
        current = self.now().astimezone(timezone.utc)
        age = (current - market.timestamp.astimezone(timezone.utc)).total_seconds()
        checks: list[tuple[bool, str]] = [
            (account.healthy, "ACCOUNT_UNHEALTHY"),
            (age <= float(self.policy.get("max_market_age_seconds", 30)), "STALE_MARKET_DATA"),
            (market.latency_ms <= float(self.policy.get("max_latency_ms", 2000)), "LATENCY_LIMIT"),
            (market.spread_pips <= float(self.policy["max_spread_pips"]), "SPREAD_LIMIT"),
            (account.daily_pnl > -abs(float(self.policy["max_daily_loss"])), "DAILY_LOSS_LIMIT"),
            (account.drawdown_percent < float(self.policy["max_drawdown_percent"]), "DRAWDOWN_LIMIT"),
            (account.free_margin >= float(self.policy["min_free_margin"]), "MARGIN_LIMIT"),
            (len(context.positions) < int(self.policy["max_positions"]), "POSITION_LIMIT"),
            (not any(str(p.get("symbol", "")) == intent.symbol for p in context.positions), "POSITION_EXISTS_FOR_SYMBOL"),
            (intent.intent_id not in context.pending_signal_ids, "DUPLICATE_INTENT"),
            (not market.news_blackout, "NEWS_BLACKOUT"),
            (current.weekday() < 5 or bool(self.policy.get("allow_weekends", False)), "WEEKEND_BLOCK"),
        ]
        sessions = tuple(self.policy.get("sessions", ()))
        if sessions:
            checks.append((market.session in sessions, "SESSION_BLOCK"))
        risk_pct = float(intent.metadata.get("risk_percent", 0.0))
        checks.append((0 < risk_pct <= float(self.policy["max_risk_percent"]), "RISK_PERCENT_LIMIT"))
        if intent.side.lower() in {"buy", "long"}:
            checks.append((intent.stop_loss is not None and intent.take_profit is not None and intent.stop_loss < intent.take_profit, "INVALID_ORDER_GEOMETRY"))
        elif intent.side.lower() in {"sell", "short"}:
            checks.append((intent.stop_loss is not None and intent.take_profit is not None and intent.stop_loss > intent.take_profit, "INVALID_ORDER_GEOMETRY"))
        else:
            checks.append((False, "INVALID_SIDE"))
        for passed, reason in checks:
            if not passed:
                return RiskDecision(False, reason)
        return RiskDecision(True, "APPROVED", {"policy_id": self.policy.get("policy_id", "")})
