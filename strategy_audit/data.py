from __future__ import annotations

from datetime import datetime
from typing import Any

from ._helpers import _clean_text
from .module_base import AuditModule
from .models import AuditContext, AuditResult


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


class DataAuditModule(AuditModule):
    name = "data_audit"

    def audit(self, context: AuditContext) -> AuditResult:
        candles = context.candles
        if not candles:
            return AuditResult(
                self.name,
                "NOT_VERIFIED",
                0.0,
                recommendation="Provide candle data for data integrity checks",
            )
        anomalies: list[str] = []
        timestamps = []
        seen = set()
        for candle in candles:
            ts = _clean_text(candle.get("time") if isinstance(candle, dict) else None)
            if ts in seen:
                anomalies.append(f"duplicate_bar:{ts}")
            seen.add(ts)
            dt = _parse_ts(ts)
            if dt is None:
                anomalies.append(f"bad_timestamp:{ts}")
            else:
                timestamps.append(dt)
            if isinstance(candle, dict):
                if float(candle.get("high", 0.0)) < float(candle.get("low", 0.0)):
                    anomalies.append(f"invalid_ohlc:{ts}")
        if timestamps and timestamps != sorted(timestamps):
            anomalies.append("timestamp_ordering")
        weekend_leaks = [t for t in timestamps if t.weekday() >= 5]
        if weekend_leaks:
            anomalies.append(f"weekend_leakage:{len(weekend_leaks)}")
        score = max(0.0, 100.0 - len(anomalies) * 15.0)
        return AuditResult(
            name=self.name,
            status="PASS" if not anomalies else "PARTIAL" if score >= 60 else "FAIL",
            score=score,
            warnings=anomalies,
            errors=[] if score >= 60 else anomalies,
            metrics={"candle_count": len(candles), "anomaly_count": len(anomalies)},
            recommendation=(
                "Repair the data before using it for qualification"
                if anomalies
                else "Proceed to statistical audit"
            ),
            details={"anomalies": anomalies},
        )


class SpreadAuditModule(AuditModule):
    name = "spread_audit"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        spreads = [
            float(row.get("spread_pips", 0.0))
            for row in context.notes.get("spread_samples", [])
            if isinstance(row, dict)
        ]
        if not spreads:
            return AuditResult(
                self.name, "NOT_VERIFIED", 0.0, recommendation="Provide spread samples"
            )
        anomalies = [
            value
            for value in spreads
            if value <= 0 or value > float(context.notes.get("max_spread_pips", 5.0))
        ]
        score = max(0.0, 100.0 - len(anomalies) * 20.0)
        return AuditResult(
            self.name,
            "PASS" if not anomalies else "PARTIAL",
            score,
            warnings=[f"spread:{v}" for v in anomalies],
            metrics={
                "sample_count": len(spreads),
                "mean_spread": sum(spreads) / len(spreads),
            },
            recommendation="Review spread outliers" if anomalies else "Proceed",
        )


class SessionAuditModule(AuditModule):
    name = "session_audit"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        sessions = {
            str(row.get("session", "")).lower()
            for row in context.trades
            if isinstance(row, dict) and row.get("session")
        }
        if not sessions:
            return AuditResult(
                self.name,
                "NOT_VERIFIED",
                0.0,
                recommendation="Provide session-tagged trades",
            )
        score = 100.0 if len(sessions) >= 2 else 75.0
        return AuditResult(
            self.name,
            "PASS" if len(sessions) >= 2 else "PARTIAL",
            score,
            metrics={"sessions": sorted(sessions)},
            recommendation="Verify session coverage across the intended trading windows",
        )


class TimestampAuditModule(AuditModule):
    name = "timestamp_audit"
    mandatory = False

    def audit(self, context: AuditContext) -> AuditResult:
        timestamps = [
            row.get("timestamp")
            for row in context.trades
            if isinstance(row, dict) and row.get("timestamp")
        ]
        if not timestamps:
            return AuditResult(
                self.name,
                "NOT_VERIFIED",
                0.0,
                recommendation="Provide timestamped trades",
            )
        if timestamps != sorted(timestamps):
            return AuditResult(
                self.name,
                "PARTIAL",
                60.0,
                warnings=["trade timestamps are not ordered"],
                recommendation="Sort event streams chronologically",
            )
        return AuditResult(
            self.name,
            "PASS",
            100.0,
            metrics={"trade_count": len(timestamps)},
            recommendation="Proceed",
        )


class IntegrityAuditModule(AuditModule):
    name = "integrity_audit"
    mandatory = True

    def audit(self, context: AuditContext) -> AuditResult:
        checks = [
            DataAuditModule().audit(context),
            TimestampAuditModule().audit(context),
        ]
        score = sum(item.score for item in checks) / len(checks)
        status = (
            "PASS"
            if all(
                item.status == "PASS" or item.status == "NOT_VERIFIED"
                for item in checks
            )
            else "PARTIAL"
        )
        return AuditResult(
            self.name,
            status,
            score,
            warnings=[w for item in checks for w in item.warnings],
            errors=[e for item in checks for e in item.errors],
            metrics={"submodules": {item.name: item.status for item in checks}},
            recommendation="Fix data integrity issues before performance evaluation",
            details={"submodule_results": [item.to_dict() for item in checks]},
        )
