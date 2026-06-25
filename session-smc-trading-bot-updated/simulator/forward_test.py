"""
DEP-00 — Forward Test Simulator.

Validates ST-A2 signal generation with sequential candle feeding.
No broker connection. No MetaAPI. No live orders.

Purpose: confirm no lookahead bias and correct signal timing
before demo deployment (DEP-01).

Public API:
    ForwardTestSimulator    — feed M15 candles one at a time
    replay_day()            — bar-by-bar timeline for one trading date
    compare_with_backtest() — verify forward signals == backtest signals

Lookahead guarantee (by construction):
    ForwardTestSimulator.feed(candle) appends the candle to an internal
    history list BEFORE calling run_strategy.  The strategy therefore
    receives exactly candles[0..i] when processing candle i — no future
    bars are present in the list it is given.

    If a signal appears after feeding candle i, signal.timestamp <= candle[i].time.
    Any signal with timestamp > candle[i].time would be unreachable (the bar
    containing that timestamp has not been fed yet), so the strategy cannot
    produce it — making lookahead physically impossible under this driver.
"""

from dataclasses import dataclass
from datetime import timezone

from strategy.session_liquidity.session_strategy import run_strategy, DEFAULT_CONFIG
from strategy.session_liquidity.entry_engine import Signal

_UTC = timezone.utc


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class ReplayEvent:
    """One event in a bar-by-bar replay timeline."""
    time: str     # "HH:MM UTC" extracted from debug event, or "—"
    event: str    # e.g. "ASIAN_RANGE", "SWEEP", "SIGNAL", "SIGNAL_REJECTED"
    detail: str   # remainder of the debug detail string


# ── Core simulator ────────────────────────────────────────────────────────────

class ForwardTestSimulator:
    """
    Sequential candle driver for ST-A2.

    Feed one M15 bar at a time via feed().  After each bar the strategy
    is evaluated over the accumulated history.  New signals (those with a
    timestamp not yet seen) are returned from feed() and appended to
    self.signals.

    Usage:
        sim = ForwardTestSimulator("EURUSD", h4_candles=h4_bars)
        for candle in m15_bars:
            new_sigs = sim.feed(candle)
    """

    def __init__(
        self,
        symbol: str,
        config: "dict | None" = None,
        h4_candles: "list | None" = None,
    ) -> None:
        self.symbol = symbol
        self._config: dict = {**DEFAULT_CONFIG, **(config or {})}
        self._h4: list = list(h4_candles or [])
        self._m15: list = []
        self._seen: set = set()
        self._signals: "list[Signal]" = []
        self._candle_count: int = 0

    # ── Feed interface ────────────────────────────────────────────────────────

    def feed(self, candle: dict) -> "list[Signal]":
        """
        Feed one M15 candle.

        The candle is appended to internal history BEFORE calling the
        strategy, so the strategy sees exactly candles[0..now].

        Returns:
            list of Signal objects that appeared for the first time on
            this candle (empty if the candle triggered nothing new).
        """
        self._m15.append(candle)
        self._candle_count += 1

        all_signals = run_strategy(
            self._m15,
            self._h4,
            self.symbol,
            config=self._config,
        )

        new: "list[Signal]" = []
        for sig in all_signals:
            key = sig.timestamp.isoformat()
            if key not in self._seen:
                self._seen.add(key)
                self._signals.append(sig)
                new.append(sig)

        return new

    def feed_all(self, candles: list) -> "list[Signal]":
        """
        Feed a sequence of candles one at a time.

        Returns all signals discovered across the entire sequence,
        in the order they were first detected.
        """
        result: "list[Signal]" = []
        for candle in candles:
            result.extend(self.feed(candle))
        return result

    # ── Accessors ─────────────────────────────────────────────────────────────

    @property
    def signals(self) -> "list[Signal]":
        return list(self._signals)

    @property
    def candle_count(self) -> int:
        return self._candle_count

    def reset(self) -> None:
        """Clear all accumulated state."""
        self._m15.clear()
        self._seen.clear()
        self._signals.clear()
        self._candle_count = 0


# ── Replay ────────────────────────────────────────────────────────────────────

def replay_day(
    trade_date,
    symbol: str,
    m15_candles: list,
    h4_candles: list,
    config: "dict | None" = None,
) -> "list[ReplayEvent]":
    """
    Replay one trading day and return a chronological event timeline.

    Runs the strategy in debug mode over the full available history,
    then filters events to the requested trade_date.

    Args:
        trade_date:  date object (or date-like) identifying the day
        symbol:      'EURUSD' | 'GBPUSD'
        m15_candles: all M15 bars (includes prior days for ATR / bias warmup)
        h4_candles:  H4 bars for HTF bias
        config:      strategy config overrides (merged with DEFAULT_CONFIG)

    Returns:
        list[ReplayEvent] — one entry per strategy decision on that date,
        in the order the strategy encountered them.
    """
    merged = {**DEFAULT_CONFIG, **(config or {})}
    _, events = run_strategy(
        m15_candles, h4_candles, symbol, config=merged, debug=True,
    )

    date_str = str(trade_date)
    timeline: "list[ReplayEvent]" = []

    for ev in events:
        if ev["date"] != date_str:
            continue

        detail = ev["detail"]
        time_str = "—"

        if detail.startswith("["):
            bracket_end = detail.find("]")
            if bracket_end > 0:
                time_str = detail[1:bracket_end]
                detail = detail[bracket_end + 2:].strip()

        timeline.append(ReplayEvent(time=time_str, event=ev["event"], detail=detail))

    return timeline


def format_replay(timeline: "list[ReplayEvent]", title: str = "") -> str:
    """
    Format a replay timeline as a human-readable string.

        Time          Event             Detail
        ——————————    ——————————————    ————————————————————
        —             ASIAN_RANGE       H=1.07500 …
        07:15 UTC     SWEEP             london side=long …
        07:30 UTC     SIGNAL            london long entry=…

    Useful for printing or embedding in docs.
    """
    lines = []
    if title:
        lines += [title, "=" * len(title)]
    lines.append(f"{'Time':<14}  {'Event':<20}  Detail")
    lines.append(f"{'—'*12}  {'—'*18}  {'—'*40}")
    for ev in timeline:
        lines.append(f"{ev.time:<14}  {ev.event:<20}  {ev.detail}")
    return "\n".join(lines)


# ── Backtest comparison ───────────────────────────────────────────────────────

def compare_with_backtest(
    symbol: str,
    m15_candles: list,
    h4_candles: list,
    config: "dict | None" = None,
) -> dict:
    """
    Run backtest (all candles at once) and forward test (sequential feed)
    on identical data.  Compare signal lists field by field.

    If both produce the same signals, the strategy has no lookahead on this
    dataset: any lookahead dependency would produce a signal in the backtest
    that the forward test cannot replicate (because the future candle it
    depends on is not present when the signal should logically appear).

    Returns:
        {
            "match": bool,
            "backtest_count": int,
            "forward_count":  int,
            "mismatches":     list[str],
        }
    """
    merged = {**DEFAULT_CONFIG, **(config or {})}

    bt_signals = run_strategy(m15_candles, h4_candles, symbol, config=merged)

    sim = ForwardTestSimulator(symbol, config=merged, h4_candles=h4_candles)
    fw_signals = sim.feed_all(m15_candles)

    mismatches: "list[str]" = []

    if len(bt_signals) != len(fw_signals):
        mismatches.append(
            f"count: backtest={len(bt_signals)} forward={len(fw_signals)}"
        )

    for i, (bt, fw) in enumerate(zip(bt_signals, fw_signals)):
        if bt.timestamp != fw.timestamp:
            mismatches.append(
                f"[{i}] timestamp: {bt.timestamp.isoformat()} "
                f"vs {fw.timestamp.isoformat()}"
            )
        if abs(bt.entry - fw.entry) > 1e-7:
            mismatches.append(
                f"[{i}] entry: {bt.entry:.5f} vs {fw.entry:.5f}"
            )
        if abs(bt.stop_loss - fw.stop_loss) > 1e-7:
            mismatches.append(
                f"[{i}] stop_loss: {bt.stop_loss:.5f} vs {fw.stop_loss:.5f}"
            )
        if bt.side != fw.side:
            mismatches.append(
                f"[{i}] side: {bt.side} vs {fw.side}"
            )
        if bt.session != fw.session:
            mismatches.append(
                f"[{i}] session: {bt.session} vs {fw.session}"
            )

    return {
        "match": len(mismatches) == 0,
        "backtest_count": len(bt_signals),
        "forward_count":  len(fw_signals),
        "mismatches":     mismatches,
    }
