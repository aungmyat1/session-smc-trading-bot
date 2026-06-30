"""
Trade logger — structured JSONL event log.

Emits one JSON object per line to logs/trades.jsonl (append-only).
Never truncates or overwrites existing data.

Events (all six must be used; add no others):
    SIGNAL_CREATED    — strategy produced a signal
    ORDER_SUBMITTED   — order sent to broker (or dry-run logged)
    ORDER_FILLED      — broker confirmed fill (or dry-run ack)
    ORDER_REJECTED    — any validation / circuit-breaker rejection
    POSITION_CLOSED   — position closed, R-outcome recorded
    ERROR             — unhandled exception in the order flow
"""

import json
import logging
from datetime import datetime, timezone
from typing import Iterator
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_LOG_FILE = Path("logs/trades.jsonl")

_VALID_EVENTS = frozenset({
    "SIGNAL_CREATED",
    "ORDER_SUBMITTED",
    "ORDER_FILLED",
    "ORDER_REJECTED",
    "POSITION_CLOSED",
    "ERROR",
})


class TradeLogger:
    """
    Append-only JSONL logger for the full trade lifecycle.

    Every method corresponds to one event type. Pass the relevant fields
    as keyword arguments; `ts` is auto-stamped in UTC.
    """

    def __init__(self, log_file: Path = DEFAULT_LOG_FILE) -> None:
        self._file = log_file
        self._file.parent.mkdir(parents=True, exist_ok=True)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _write(self, event: str, payload: dict) -> None:
        if event not in _VALID_EVENTS:
            raise ValueError(f"Unknown event type: {event!r}")
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **payload,
        }
        with self._file.open("a") as f:
            f.write(json.dumps(record) + "\n")
        logger.debug("TRADE_LOG %s %s", event, payload.get("symbol", ""))

    # ── Public event methods ──────────────────────────────────────────────────

    def signal_created(
        self, symbol: str, session: str, side: str,
        entry: float, sl: float, tp: float,
        sl_pips: float, reason: str = "",
        signal_ts: "str | None" = None,
    ) -> None:
        self._write("SIGNAL_CREATED", {
            "symbol": symbol, "session": session, "side": side,
            "entry": entry, "sl": sl, "tp": tp,
            "sl_pips": sl_pips, "reason": reason,
            "signal_ts": signal_ts,
        })

    def order_submitted(
        self, symbol: str, session: str, direction: str,
        volume: float, sl: float, tp: float,
        lots: float, equity: float, risk_pct: float,
        dry_run: bool = False,
    ) -> None:
        self._write("ORDER_SUBMITTED", {
            "symbol": symbol, "session": session, "direction": direction,
            "volume": volume, "sl": sl, "tp": tp,
            "lots": lots, "equity": equity, "risk_pct": risk_pct,
            "dry_run": dry_run,
        })

    def order_filled(
        self, symbol: str, order_id: str, entry_price: float,
        volume: float, sl: float, tp: float, dry_run: bool = False,
    ) -> None:
        self._write("ORDER_FILLED", {
            "symbol": symbol, "order_id": order_id,
            "entry_price": entry_price, "volume": volume,
            "sl": sl, "tp": tp, "dry_run": dry_run,
        })

    def order_rejected(self, symbol: str, reason: str, side: str = "") -> None:
        self._write("ORDER_REJECTED", {
            "symbol": symbol, "reason": reason, "side": side,
        })

    def position_closed(
        self, symbol: str, position_id: str,
        result_r: float, exit_reason: str,
    ) -> None:
        self._write("POSITION_CLOSED", {
            "symbol": symbol, "position_id": position_id,
            "result_r": result_r, "exit_reason": exit_reason,
        })

    def error(self, symbol: str, error_msg: str, context: str = "") -> None:
        self._write("ERROR", {
            "symbol": symbol, "error": error_msg, "context": context,
        })

    # ── Read-back (tests + reporting) ─────────────────────────────────────────

    def read_all(self) -> list[dict]:
        """Return every logged event as a list of dicts. Skips malformed lines."""
        return list(self.iter_events())

    def iter_events(self) -> Iterator[dict]:
        """Yield logged events one at a time to avoid loading large journals at once."""
        if not self._file.exists():
            return
        with self._file.open(encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed JSONL line: %r", line[:80])
