"""
S6 — Shadow Runner.

Main loop for shadow/paper trading mode.

Flow per tick:
  MarketFeed → Strategies → Regime+Score+Risk → PaperExecution → Journal

No real orders. DRY_RUN enforced by default.

Usage:
    python3 -m adaptive.run_shadow
    python3 -m adaptive.run_shadow --interval 60 --pairs EURUSD GBPUSD

Requires METAAPI_TOKEN and METAAPI_ACCOUNT_ID in .env (same as main bot).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── env ──────────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# ── adaptive imports ──────────────────────────────────────────────────────────
from adaptive.state.state_store import StateStore
from adaptive.filters.news_filter import NewsFilter
from adaptive.simulation.paper_execution import PaperExecution
from adaptive.journal.trade_journal import TradeJournal
from adaptive.engine.trade_router import route_signal
from adaptive.engine.risk_manager import register_open_position

from adaptive.strategies.london_breakout_strategy import generate_signals as lb_signals
from adaptive.strategies.ny_momentum_strategy import generate_signals as ny_signals
from adaptive.strategies.smc_session_strategy import generate_signals as smc_signals

# ── logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path("logs") / "adaptive_shadow.log"),
    ],
)
_log = logging.getLogger("adaptive.shadow")

PAIRS = ["EURUSD", "GBPUSD"]
DEFAULT_INTERVAL = 60  # seconds


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _build_feed(executor):
    from data.forex_data import ForexData
    from adaptive.data.market_feed import MarketFeed

    return MarketFeed(ForexData(executor))


async def _connect_executor():
    """
    Connect to MetaAPI broker.

    MT5Executor.connect() passes wait_synchronized({"timeoutInSeconds":60}) —
    the SDK expects a plain int, not a dict, causing TypeError.
    Workaround: replicate the connection flow here with the correct call,
    then inject the connected objects into the executor so its other methods
    (get_symbol_price, get_historical_candles, etc.) work normally.
    """
    from execution.mt5_executor import MT5Executor

    try:
        from metaapi_cloud_sdk import MetaApi
    except ImportError:
        _log.error("metaapi-cloud-sdk not installed.")
        return None

    token = os.environ.get("METAAPI_TOKEN", "")
    account_id = os.environ.get("METAAPI_ACCOUNT_ID", "")
    if not token or not account_id:
        _log.error("METAAPI_TOKEN or METAAPI_ACCOUNT_ID not set — aborting.")
        return None

    ex = MT5Executor(token, account_id)
    api = MetaApi(token)
    try:
        account = await api.metatrader_account_api.get_account(account_id)
        if account.state not in ("DEPLOYING", "DEPLOYED"):
            _log.info("Deploying MetaAPI account…")
            await account.deploy()
        _log.info("Waiting for broker connection…")
        await account.wait_connected()
        connection = account.get_rpc_connection()
        await connection.connect()
        await connection.wait_synchronized(60)  # fix: SDK expects int not dict
        _log.info("MT5 connected (account=%s)", account_id)
    except Exception as exc:
        _log.error("Connection failed: %s", exc)
        try:
            api.close()
        except Exception:
            pass
        return None

    # Inject so executor methods that use _connection work
    ex._api = api
    ex._account = account
    ex._connection = connection
    return ex


# ── Core tick ────────────────────────────────────────────────────────────────


async def _tick(
    feed,
    state_store: StateStore,
    news_filter: NewsFilter,
    paper: PaperExecution,
    journal: TradeJournal,
    pairs: list[str],
) -> None:
    """Run one scan cycle across all pairs and strategies."""

    # Daily reset check
    if state_store.needs_daily_reset():
        state_store.reset_daily()
        _log.info("Daily state reset.")

    for symbol in pairs:
        # ── News filter ──────────────────────────────────────────────────────
        news = news_filter.is_safe(symbol)
        if not news["safe_to_trade"]:
            _log.info("SKIP %s — news block (%s)", symbol, news["reason"])
            continue

        # ── Fetch candles ────────────────────────────────────────────────────
        try:
            m15 = await feed.get_candles(symbol, "M15", 200)
            h4 = await feed.get_candles(symbol, "H4", 100)
            m5 = await feed.get_candles(symbol, "M5", 100)
            spread = await feed.get_current_spread(symbol)
        except Exception as exc:
            _log.warning("Feed error %s: %s", symbol, exc)
            continue

        if len(m15) < 30:
            _log.debug("Insufficient bars for %s — skip", symbol)
            continue

        # ── Update open paper trades ─────────────────────────────────────────
        if m15:
            current_price = m15[-1]["close"]
            for t in paper.get_open():
                if t["pair"] == symbol:
                    closed = paper.update(t["trade_id"], current_price)
                    if closed:
                        journal.log_trade(closed)
                        _log.info(
                            "Trade closed: %s %s R=%.2f",
                            closed["pair"],
                            closed["status"],
                            closed["pnl_r"],
                        )

        # ── Generate signals from all strategies ─────────────────────────────
        all_signals = []
        try:
            all_signals += lb_signals(m15, symbol)
            all_signals += ny_signals(m15, symbol)
            all_signals += smc_signals(m15, h4, symbol)
        except Exception as exc:
            _log.warning("Strategy error %s: %s", symbol, exc)

        if not all_signals:
            continue

        # ── Build context ────────────────────────────────────────────────────
        session = feed.get_session()
        utc_hour = datetime.now(timezone.utc).hour
        context = {
            "htf_bias": _derive_htf_bias(h4),
            "utc_hour": utc_hour,
            "spread_pips": spread,
            "news_event": not news["safe_to_trade"],
        }

        # ── Route each signal ────────────────────────────────────────────────
        state = state_store.get()
        for sig in all_signals:
            result = route_signal(
                signal=sig,
                candles=m15,
                context=context,
                risk_state=state,
                dry_run=True,
            )
            journal.log_signal(sig, result)

            if result["decision"] == "APPROVED":
                trade_id = paper.open_trade(sig)
                state = register_open_position(sig, state)
                state_store.update(state)
                _log.info(
                    "APPROVED %s %s %s score=%s regime=%s id=%s",
                    sig.strategy,
                    sig.pair,
                    sig.direction,
                    result["score_result"].get("score", "?"),
                    result["regime"].get("regime", "?"),
                    trade_id,
                )
            else:
                _log.debug(
                    "REJECTED %s %s %s — %s",
                    sig.strategy,
                    sig.pair,
                    sig.direction,
                    result["rejection_reason"],
                )


def _derive_htf_bias(h4_candles: list[dict]) -> str:
    """Simple H4 bias: last close vs 20-bar mean."""
    if len(h4_candles) < 20:
        return "NEUTRAL"
    closes = [c["close"] for c in h4_candles[-20:]]
    mean = sum(closes) / len(closes)
    last = closes[-1]
    if last > mean * 1.001:
        return "BULLISH"
    if last < mean * 0.999:
        return "BEARISH"
    return "NEUTRAL"


# ── Main loop ─────────────────────────────────────────────────────────────────


async def run(pairs: list[str], interval: int) -> None:
    _log.info(
        "Shadow runner starting — pairs=%s interval=%ds DRY_RUN=True", pairs, interval
    )

    executor = await _connect_executor()
    if executor is None:
        return

    feed = await _build_feed(executor)
    state_store = StateStore()
    news_filter = NewsFilter()
    paper = PaperExecution()
    journal = TradeJournal()

    try:
        while True:
            try:
                await _tick(feed, state_store, news_filter, paper, journal, pairs)
            except Exception as exc:
                _log.error("Tick error: %s", exc, exc_info=True)
            await asyncio.sleep(interval)
    finally:
        _log.info("Shadow runner shutting down.")
        try:
            await executor.disconnect()
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Adaptive Engine shadow runner")
    parser.add_argument("--pairs", nargs="+", default=PAIRS)
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL)
    args = parser.parse_args()
    asyncio.run(run(args.pairs, args.interval))


if __name__ == "__main__":
    main()
