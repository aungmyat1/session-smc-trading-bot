from __future__ import annotations

from statistics import mean

from .module_base import AuditModule
from .models import AuditContext, AuditResult


class RegimeAuditModule(AuditModule):
    name = "regime_audit"

    def audit(self, context: AuditContext) -> AuditResult:
        breakdown = context.regime_breakdown or {}
        if not breakdown and context.trades:
            buckets = {}
            for trade in context.trades:
                if not isinstance(trade, dict):
                    continue
                regime = str(trade.get("regime") or trade.get("session") or "unknown")
                buckets.setdefault(regime, []).append(
                    float(trade.get("std_net_r", trade.get("net_r", 0.0)) or 0.0)
                )
            breakdown = {
                regime: {
                    "trade_count": len(values),
                    "profit_factor": round(
                        (
                            sum(v for v in values if v > 0)
                            / abs(sum(v for v in values if v <= 0))
                            if any(v <= 0 for v in values)
                            else (sum(v for v in values if v > 0) if values else 0.0)
                        ),
                        4,
                    ),
                    "win_rate": (
                        round(sum(1 for v in values if v > 0) / len(values), 4)
                        if values
                        else 0.0
                    ),
                    "expectancy": round(mean(values), 4) if values else 0.0,
                    "max_drawdown": 0.0,
                }
                for regime, values in buckets.items()
            }
        if not breakdown:
            return AuditResult(
                self.name,
                "NOT_VERIFIED",
                0.0,
                recommendation="Provide regime segmentation",
            )
        bad = [
            name
            for name, metrics in breakdown.items()
            if float(metrics.get("profit_factor", 0.0)) < 1.0
        ]
        score = max(0.0, 100.0 - len(bad) * 15.0)
        return AuditResult(
            self.name,
            "PASS" if not bad else "PARTIAL",
            score,
            metrics=breakdown,
            warnings=[f"underperforming_regime:{name}" for name in bad],
            recommendation=(
                "Review regime-specific failures before deployment"
                if bad
                else "Proceed"
            ),
        )


class VolatilityAuditModule(AuditModule):
    name = "volatility"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        vols = [
            float(c.get("atr", 0.0))
            for c in context.candles
            if isinstance(c, dict) and c.get("atr") is not None
        ]
        if not vols:
            return AuditResult(
                self.name,
                "NOT_VERIFIED",
                0.0,
                recommendation="Provide ATR/volatility samples",
            )
        return AuditResult(
            self.name,
            "PASS",
            100.0,
            metrics={"avg_atr": sum(vols) / len(vols)},
            recommendation="Proceed",
        )


class TrendAuditModule(AuditModule):
    name = "trend"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        if not context.trades:
            return AuditResult(
                self.name,
                "NOT_VERIFIED",
                0.0,
                recommendation="Provide trade outcomes by trend regime",
            )
        trend_count = sum(
            1
            for trade in context.trades
            if isinstance(trade, dict)
            and str(trade.get("trend", "")).lower() in {"trend", "trending"}
        )
        return AuditResult(
            self.name,
            "PASS" if trend_count else "PARTIAL",
            100.0 if trend_count else 60.0,
            metrics={"trend_trades": trend_count},
            recommendation="Verify trend regime segmentation",
        )


class SessionRegimeAuditModule(AuditModule):
    name = "session_regime"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        sessions = {
            str(trade.get("session", "")).lower()
            for trade in context.trades
            if isinstance(trade, dict)
        }
        if not sessions:
            return AuditResult(
                self.name, "NOT_VERIFIED", 0.0, recommendation="Provide session tags"
            )
        return AuditResult(
            self.name,
            "PASS",
            100.0 if len(sessions) >= 2 else 70.0,
            metrics={"sessions": sorted(sessions)},
            recommendation="Proceed",
        )


class SeasonalityAuditModule(AuditModule):
    name = "seasonality"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        if not context.trades:
            return AuditResult(
                self.name,
                "NOT_VERIFIED",
                0.0,
                recommendation="Provide time-series trades",
            )
        months = {
            str(trade.get("timestamp", ""))[:7]
            for trade in context.trades
            if isinstance(trade, dict) and trade.get("timestamp")
        }
        return AuditResult(
            self.name,
            "PASS" if len(months) >= 2 else "PARTIAL",
            100.0 if len(months) >= 2 else 65.0,
            metrics={"months": sorted(months)},
            recommendation="Check monthly and quarterly stability",
        )


class NewsAuditModule(AuditModule):
    name = "news"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        markers = context.notes.get("news_events", [])
        if not markers:
            return AuditResult(
                self.name,
                "NOT_VERIFIED",
                0.0,
                recommendation="Provide news-impact samples",
            )
        blocked = [item for item in markers if not bool(item.get("passed", True))]
        return AuditResult(
            self.name,
            "PASS" if not blocked else "PARTIAL",
            100.0 if not blocked else 60.0,
            metrics={"news_samples": len(markers), "blocked": len(blocked)},
            recommendation="Confirm news blackout logic",
        )
