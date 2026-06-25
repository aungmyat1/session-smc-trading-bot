"""
Tests for RESEARCH-01: research/logger.py

Covers:
  - All six log_*() functions create their file on first call
  - Header written exactly once per file
  - Rows append correctly (CSV round-trip)
  - Multiple rows preserve all data
  - run_id links records across tables
  - generate_run_id() is unique and format-stable
  - _append_row creates missing parent directories
"""

import csv
import shutil
import tempfile
import unittest
from pathlib import Path

import research.logger as rl
from research.logger import (
    BacktestRun,
    GateRejection,
    MarketCondition,
    SignalRecord,
    StrategyVersion,
    TradeRecord,
    generate_run_id,
    log_backtest_run,
    log_market_condition,
    log_rejection,
    log_signal,
    log_strategy_version,
    log_trade,
    new_signal_id,
    new_trade_id,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _sample_run(run_id: str = "TEST-RUN-001") -> BacktestRun:
    return BacktestRun(
        run_id=run_id,
        timestamp_utc="2024-01-15T07:00:00Z",
        strategy_id="SA",
        strategy_version="0.1.0",
        symbol="EURUSD",
        timeframe="M15",
        start_date="2021-06-21",
        end_date="2026-06-19",
        rr=3.0,
        spread_model="standard",
        spread_pips=1.4,
        trade_count=142,
        win_count=58,
        loss_count=84,
        gross_pf=1.52,
        net_pf_std=1.41,
        net_pf_2x=1.22,
        win_rate_pct=40.8,
        avg_r=0.27,
        max_dd_r=8.3,
        total_net_r=38.3,
        gate_passed=True,
        notes="first run",
    )


def _sample_trade(run_id: str = "TEST-RUN-001") -> TradeRecord:
    return TradeRecord(
        trade_id=new_trade_id(),
        run_id=run_id,
        timestamp_utc="2024-01-16T07:15:00Z",
        symbol="EURUSD",
        session="london",
        side="long",
        entry=1.08500,
        stop_loss=1.08300,
        take_profit=1.09100,
        sl_pips=20.0,
        rr=3.0,
        exit_price=1.09100,
        exit_reason="tp",
        bars_held=12,
        gross_r=3.0,
        spread_cost_r=0.07,
        net_r=2.93,
        asian_high=1.08650,
        asian_low=1.08320,
        asian_range_pips=33.0,
        htf_bias="bullish",
        sweep_bar_time="2024-01-16T07:00:00Z",
        displacement_bar_time="2024-01-16T07:15:00Z",
    )


def _sample_signal(run_id: str = "TEST-RUN-001") -> SignalRecord:
    return SignalRecord(
        signal_id=new_signal_id(),
        run_id=run_id,
        timestamp_utc="2024-01-16T07:15:00Z",
        symbol="EURUSD",
        session="london",
        side="long",
        entry=1.08500,
        stop_loss=1.08300,
        take_profit=1.09100,
        sl_pips=20.0,
        rr=3.0,
        asian_high=1.08650,
        asian_low=1.08320,
        asian_range_pips=33.0,
        htf_bias="bullish",
        sweep_bar_time="2024-01-16T07:00:00Z",
        displacement_bar_time="2024-01-16T07:15:00Z",
        fired=True,
    )


def _sample_rejection(run_id: str = "TEST-RUN-001") -> GateRejection:
    return GateRejection(
        rejection_id="rej-001",
        run_id=run_id,
        timestamp_utc="2024-01-16T07:00:00Z",
        symbol="EURUSD",
        session="london",
        gate_name="range_too_small",
        reason="Asian range 12.0 pips < 15.0 pip minimum",
        bar_time="2024-01-16T07:00:00Z",
        asian_range_pips=12.0,
        htf_bias="bullish",
        price=1.08500,
    )


def _sample_condition(run_id: str = "TEST-RUN-001") -> MarketCondition:
    return MarketCondition(
        condition_id="cond-001",
        run_id=run_id,
        timestamp_utc="2024-01-16T07:00:00Z",
        symbol="EURUSD",
        session="london",
        htf_bias="bullish",
        atr_pips=8.5,
        asian_range_pips=33.0,
        asian_high=1.08650,
        asian_low=1.08320,
        price_close=1.08500,
    )


def _sample_version() -> StrategyVersion:
    return StrategyVersion(
        version_id="ver-001",
        strategy_id="SA",
        created_utc="2024-01-15T00:00:00Z",
        rr=3.0,
        sl_buffer_pips=2.0,
        displacement_atr_mult=1.2,
        min_asian_range_pips_eurusd=15.0,
        min_asian_range_pips_gbpusd=20.0,
        swing_n=2,
        atr_period=14,
        notes="baseline",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Base test class — redirects all writes to a temp directory
# ─────────────────────────────────────────────────────────────────────────────

class ResearchLoggerTestCase(unittest.TestCase):
    _original_base: Path

    @classmethod
    def setUpClass(cls):
        cls._original_base = rl._BASE_DIR

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        rl._set_base_dir(self.tmpdir)

    def tearDown(self):
        rl._set_base_dir(self._original_base)
        shutil.rmtree(self.tmpdir, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
class TestGenerateRunId(unittest.TestCase):

    def test_format(self):
        """run_id = YYYYMMDDTHHMMSS-<6hex>"""
        rid = generate_run_id()
        parts = rid.split("-")
        self.assertEqual(len(parts), 2)
        ts, suffix = parts
        self.assertEqual(len(ts), 15)   # YYYYMMDDTHHMMSS
        self.assertTrue(ts[8] == "T")
        self.assertEqual(len(suffix), 6)
        int(suffix, 16)                 # must be valid hex

    def test_uniqueness(self):
        ids = {generate_run_id() for _ in range(50)}
        self.assertEqual(len(ids), 50)


# ─────────────────────────────────────────────────────────────────────────────
class TestLogBacktestRun(ResearchLoggerTestCase):

    def test_creates_file(self):
        log_backtest_run(_sample_run())
        self.assertTrue((self.tmpdir / "backtest_runs.csv").exists())

    def test_header_and_row(self):
        log_backtest_run(_sample_run())
        rows = _read_csv(self.tmpdir / "backtest_runs.csv")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["run_id"], "TEST-RUN-001")
        self.assertEqual(rows[0]["strategy_id"], "SA")
        self.assertEqual(rows[0]["trade_count"], "142")
        self.assertEqual(rows[0]["gate_passed"], "True")

    def test_appends_multiple_rows(self):
        log_backtest_run(_sample_run("RUN-001"))
        log_backtest_run(_sample_run("RUN-002"))
        rows = _read_csv(self.tmpdir / "backtest_runs.csv")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["run_id"], "RUN-001")
        self.assertEqual(rows[1]["run_id"], "RUN-002")

    def test_header_written_exactly_once(self):
        for i in range(5):
            log_backtest_run(_sample_run(f"RUN-{i:03d}"))
        content = (self.tmpdir / "backtest_runs.csv").read_text()
        self.assertEqual(content.count("run_id"), 1)

    def test_notes_field_default_empty(self):
        r = _sample_run()
        r.notes = ""
        log_backtest_run(r)
        rows = _read_csv(self.tmpdir / "backtest_runs.csv")
        self.assertEqual(rows[0]["notes"], "")

    def test_float_precision(self):
        log_backtest_run(_sample_run())
        rows = _read_csv(self.tmpdir / "backtest_runs.csv")
        self.assertAlmostEqual(float(rows[0]["net_pf_std"]), 1.41, places=2)


# ─────────────────────────────────────────────────────────────────────────────
class TestLogTrade(ResearchLoggerTestCase):

    def test_creates_file(self):
        log_trade(_sample_trade())
        self.assertTrue((self.tmpdir / "trades.csv").exists())

    def test_row_round_trip(self):
        t = _sample_trade("RUN-A")
        log_trade(t)
        rows = _read_csv(self.tmpdir / "trades.csv")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["run_id"], "RUN-A")
        self.assertEqual(rows[0]["session"], "london")
        self.assertEqual(rows[0]["side"], "long")
        self.assertEqual(rows[0]["exit_reason"], "tp")
        self.assertAlmostEqual(float(rows[0]["net_r"]), 2.93, places=2)

    def test_appends_two_trades(self):
        log_trade(_sample_trade())
        log_trade(_sample_trade())
        rows = _read_csv(self.tmpdir / "trades.csv")
        self.assertEqual(len(rows), 2)

    def test_header_written_once(self):
        log_trade(_sample_trade())
        log_trade(_sample_trade())
        content = (self.tmpdir / "trades.csv").read_text()
        self.assertEqual(content.count("trade_id"), 1)


# ─────────────────────────────────────────────────────────────────────────────
class TestLogSignal(ResearchLoggerTestCase):

    def test_creates_file(self):
        log_signal(_sample_signal())
        self.assertTrue((self.tmpdir / "signal_log.csv").exists())

    def test_fired_true_stored(self):
        log_signal(_sample_signal())
        rows = _read_csv(self.tmpdir / "signal_log.csv")
        self.assertEqual(rows[0]["fired"], "True")
        self.assertEqual(rows[0]["rejection_reason"], "")

    def test_fired_false_with_reason(self):
        s = _sample_signal()
        s.fired = False
        s.rejection_reason = "already_traded"
        log_signal(s)
        rows = _read_csv(self.tmpdir / "signal_log.csv")
        self.assertEqual(rows[0]["fired"], "False")
        self.assertEqual(rows[0]["rejection_reason"], "already_traded")


# ─────────────────────────────────────────────────────────────────────────────
class TestLogRejection(ResearchLoggerTestCase):

    def test_creates_file(self):
        log_rejection(_sample_rejection())
        self.assertTrue((self.tmpdir / "gate_rejections.csv").exists())

    def test_row_data(self):
        log_rejection(_sample_rejection())
        rows = _read_csv(self.tmpdir / "gate_rejections.csv")
        self.assertEqual(rows[0]["gate_name"], "range_too_small")
        self.assertAlmostEqual(float(rows[0]["asian_range_pips"]), 12.0, places=1)

    def test_appends_multiple(self):
        for _ in range(3):
            log_rejection(_sample_rejection())
        rows = _read_csv(self.tmpdir / "gate_rejections.csv")
        self.assertEqual(len(rows), 3)

    def test_header_once(self):
        log_rejection(_sample_rejection())
        log_rejection(_sample_rejection())
        content = (self.tmpdir / "gate_rejections.csv").read_text()
        self.assertEqual(content.count("rejection_id"), 1)


# ─────────────────────────────────────────────────────────────────────────────
class TestLogMarketCondition(ResearchLoggerTestCase):

    def test_creates_file(self):
        log_market_condition(_sample_condition())
        self.assertTrue((self.tmpdir / "market_conditions.csv").exists())

    def test_row_data(self):
        log_market_condition(_sample_condition())
        rows = _read_csv(self.tmpdir / "market_conditions.csv")
        self.assertEqual(rows[0]["htf_bias"], "bullish")
        self.assertAlmostEqual(float(rows[0]["atr_pips"]), 8.5, places=1)


# ─────────────────────────────────────────────────────────────────────────────
class TestLogStrategyVersion(ResearchLoggerTestCase):

    def test_creates_file(self):
        log_strategy_version(_sample_version())
        self.assertTrue((self.tmpdir / "strategy_versions.csv").exists())

    def test_row_data(self):
        log_strategy_version(_sample_version())
        rows = _read_csv(self.tmpdir / "strategy_versions.csv")
        self.assertEqual(rows[0]["strategy_id"], "SA")
        self.assertEqual(rows[0]["swing_n"], "2")
        self.assertAlmostEqual(float(rows[0]["displacement_atr_mult"]), 1.2, places=1)


# ─────────────────────────────────────────────────────────────────────────────
class TestRunIdLinking(ResearchLoggerTestCase):
    """run_id must join backtest_runs ↔ trades ↔ gate_rejections correctly."""

    def test_run_id_links_across_tables(self):
        run_id = generate_run_id()

        log_backtest_run(_sample_run(run_id))
        log_trade(_sample_trade(run_id))
        log_rejection(_sample_rejection(run_id))

        runs = _read_csv(self.tmpdir / "backtest_runs.csv")
        trades = _read_csv(self.tmpdir / "trades.csv")
        rejections = _read_csv(self.tmpdir / "gate_rejections.csv")

        self.assertEqual(runs[0]["run_id"], run_id)
        self.assertEqual(trades[0]["run_id"], run_id)
        self.assertEqual(rejections[0]["run_id"], run_id)

    def test_two_runs_stay_separate(self):
        run_a = generate_run_id()
        run_b = generate_run_id()

        log_trade(_sample_trade(run_a))
        log_trade(_sample_trade(run_b))

        rows = _read_csv(self.tmpdir / "trades.csv")
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]["run_id"], rows[1]["run_id"])


# ─────────────────────────────────────────────────────────────────────────────
class TestAppendRowEdgeCases(ResearchLoggerTestCase):

    def test_creates_parent_directories(self):
        """_append_row must create nested dirs if base_dir doesn't exist yet."""
        nested = self.tmpdir / "a" / "b" / "c"
        rl._set_base_dir(nested)
        log_backtest_run(_sample_run())
        self.assertTrue((nested / "backtest_runs.csv").exists())

    def test_pre_existing_empty_file_gets_header(self):
        """Empty file (0 bytes) → header written on first write."""
        path = self.tmpdir / "backtest_runs.csv"
        path.touch()
        self.assertEqual(path.stat().st_size, 0)
        log_backtest_run(_sample_run())
        rows = _read_csv(path)
        self.assertEqual(len(rows), 1)

    def test_pre_existing_file_with_data_no_duplicate_header(self):
        """File already has rows → no second header appended."""
        log_backtest_run(_sample_run("RUN-1"))
        log_backtest_run(_sample_run("RUN-2"))
        content = (self.tmpdir / "backtest_runs.csv").read_text()
        self.assertEqual(content.count("run_id"), 1)
        rows = _read_csv(self.tmpdir / "backtest_runs.csv")
        self.assertEqual(len(rows), 2)

    def test_all_six_files_independent(self):
        """Writing to one CSV never corrupts another."""
        log_backtest_run(_sample_run())
        log_trade(_sample_trade())
        log_signal(_sample_signal())
        log_rejection(_sample_rejection())
        log_market_condition(_sample_condition())
        log_strategy_version(_sample_version())

        for fname in [
            "backtest_runs.csv", "trades.csv", "signal_log.csv",
            "gate_rejections.csv", "market_conditions.csv", "strategy_versions.csv",
        ]:
            rows = _read_csv(self.tmpdir / fname)
            self.assertEqual(len(rows), 1, msg=f"{fname} should have 1 row")


if __name__ == "__main__":
    unittest.main()
