-- =====================================================================
-- TRADING RESEARCH DATABASE — Schema v2
-- PostgreSQL 16+
--
-- Upgrades over v1 (archive/Database-F-prototype/scripts/init.sql):
--   • research.trades: added setup_type, sl_pips, spread_cost_pips,
--     cost_in_r, gross_result_r, net_result_r, tp1_hit,
--     session_high, session_low, session_range_pips
--   • research.replay_runs: added scenario column
--   • research.trade_features: added spread_scenario column
--   • research.daily_equity: added equity_r column
--   • analytics.phase0_gate: NEW — gate pass/fail verdict per run
--   • market.asian_ranges: NEW — daily Asian session range
--   • market.session_ranges: NEW — per-session range + classification
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS market;
CREATE SCHEMA IF NOT EXISTS research;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS config;

SET search_path TO public, market, research, analytics, config;

-- =====================================================================
-- market schema
-- =====================================================================

CREATE TABLE IF NOT EXISTS market.instruments (
    id             SERIAL PRIMARY KEY,
    symbol         VARCHAR(20) UNIQUE NOT NULL,
    asset_type     VARCHAR(20) NOT NULL,
    broker_symbol  VARCHAR(30),
    base_currency  VARCHAR(10),
    quote_currency VARCHAR(10),
    pip_size       NUMERIC(10,6) DEFAULT 0.0001,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Candle store — kept for optional import of live broker candles
CREATE TABLE IF NOT EXISTS market.candles (
    id        BIGSERIAL PRIMARY KEY,
    symbol    VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    open      NUMERIC(12,5),
    high      NUMERIC(12,5),
    low       NUMERIC(12,5),
    close     NUMERIC(12,5),
    volume    BIGINT,
    bid       NUMERIC(12,5),
    ask       NUMERIC(12,5),
    spread    NUMERIC(8,5),
    source    VARCHAR(30),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, timeframe, timestamp)
);
CREATE INDEX IF NOT EXISTS idx_candles_symbol_tf_time
    ON market.candles(symbol, timeframe, timestamp);

-- Asian session range — built by pipeline/02_build_features.py
CREATE TABLE IF NOT EXISTS market.asian_ranges (
    id               BIGSERIAL PRIMARY KEY,
    symbol           VARCHAR(20) NOT NULL,
    date             DATE NOT NULL,
    asian_high       NUMERIC(12,5) NOT NULL,
    asian_low        NUMERIC(12,5) NOT NULL,
    asian_mid        NUMERIC(12,5) NOT NULL,
    asian_range_pips NUMERIC(8,2)  NOT NULL,
    asian_volume     BIGINT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, date)
);
CREATE INDEX IF NOT EXISTS idx_asian_ranges_symbol_date
    ON market.asian_ranges(symbol, date);

-- Session range per trading day — built by pipeline/02_build_features.py
CREATE TABLE IF NOT EXISTS market.session_ranges (
    id                  BIGSERIAL PRIMARY KEY,
    symbol              VARCHAR(20) NOT NULL,
    date                DATE        NOT NULL,
    session             VARCHAR(20) NOT NULL,  -- 'london' | 'newyork'
    session_high        NUMERIC(12,5) NOT NULL,
    session_low         NUMERIC(12,5) NOT NULL,
    session_mid         NUMERIC(12,5) NOT NULL,
    session_range_pips  NUMERIC(8,2)  NOT NULL,
    session_type        VARCHAR(10),           -- 'RANGE' | 'TREND' | 'MIXED'
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, date, session)
);
CREATE INDEX IF NOT EXISTS idx_session_ranges_symbol_date
    ON market.session_ranges(symbol, date);

-- Generic SMC event store (kept for ad-hoc feature logging)
CREATE TABLE IF NOT EXISTS market.smc_events (
    id             BIGSERIAL PRIMARY KEY,
    symbol         VARCHAR(20) NOT NULL,
    timeframe      VARCHAR(10) NOT NULL,
    timestamp      TIMESTAMP   NOT NULL,
    event_type     VARCHAR(30) NOT NULL,
    event_price    NUMERIC(12,5),
    strength_score NUMERIC(5,2),
    metadata_json  JSONB,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_smc_symbol_time   ON market.smc_events(symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_smc_event_type    ON market.smc_events(event_type);

-- =====================================================================
-- research schema
-- =====================================================================

CREATE TABLE IF NOT EXISTS research.strategies (
    id             SERIAL PRIMARY KEY,
    strategy_name  VARCHAR(100) NOT NULL,
    version        VARCHAR(20)  NOT NULL,
    description    TEXT,
    rules_json     JSONB,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status         VARCHAR(20) DEFAULT 'active',
    UNIQUE(strategy_name, version)
);

CREATE TABLE IF NOT EXISTS research.replay_runs (
    id          SERIAL PRIMARY KEY,
    run_id      VARCHAR(100) UNIQUE NOT NULL,
    strategy_id INTEGER REFERENCES research.strategies(id),
    symbol      VARCHAR(20),
    start_date  DATE,
    end_date    DATE,
    scenario    VARCHAR(20) DEFAULT 'standard',  -- 'standard' | 'stress_2x'
    data_source VARCHAR(50),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Upgraded trades table — all fields required for net-of-fees analysis
CREATE TABLE IF NOT EXISTS research.trades (
    id                  BIGSERIAL PRIMARY KEY,
    trade_id            VARCHAR(150) UNIQUE NOT NULL,
    run_id              VARCHAR(100) REFERENCES research.replay_runs(run_id),
    strategy_id         INTEGER REFERENCES research.strategies(id),

    symbol              VARCHAR(20) NOT NULL,
    session             VARCHAR(20),           -- 'london' | 'newyork'
    direction           VARCHAR(10) CHECK (direction IN ('long', 'short')),
    setup_type          VARCHAR(5)  DEFAULT 'A',

    entry_time          TIMESTAMP,
    exit_time           TIMESTAMP,
    entry_price         NUMERIC(12,5),
    stop_price          NUMERIC(12,5),
    take_profit         NUMERIC(12,5),        -- TP1 price
    tp2_price           NUMERIC(12,5),        -- TP2 price
    sl_pips             NUMERIC(8,2),
    risk_reward         NUMERIC(5,2),

    -- Cost model (CLAUDE.md §1 — net-of-fees mandatory)
    spread_cost_pips    NUMERIC(8,2),         -- spread + commission in pips
    cost_in_r           NUMERIC(8,4),         -- spread_cost_pips / sl_pips

    -- Results
    gross_result_r      NUMERIC(8,4),         -- before costs
    net_result_r        NUMERIC(8,4),         -- after costs (the only number that matters)
    exit_reason         VARCHAR(30),           -- SL_HIT | TP1_THEN_BE | TP2_HIT | SESSION_END | DATA_END
    tp1_hit             BOOLEAN DEFAULT FALSE,

    -- Session context (for slice analysis)
    session_high        NUMERIC(12,5),
    session_low         NUMERIC(12,5),
    session_range_pips  NUMERIC(8,2),

    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trades_run_id     ON research.trades(run_id);
CREATE INDEX IF NOT EXISTS idx_trades_symbol     ON research.trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_session    ON research.trades(session);
CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON research.trades(entry_time);
CREATE INDEX IF NOT EXISTS idx_trades_net_r      ON research.trades(net_result_r);
CREATE INDEX IF NOT EXISTS idx_trades_exit_reason ON research.trades(exit_reason);

-- Per-trade SMC features — for drill-down analysis of which gates fire most
CREATE TABLE IF NOT EXISTS research.trade_features (
    id                       BIGSERIAL PRIMARY KEY,
    trade_id                 VARCHAR(150) REFERENCES research.trades(trade_id),
    bos_present              BOOLEAN,
    choch_present            BOOLEAN,
    fvg_present              BOOLEAN,
    liquidity_sweep_present  BOOLEAN,
    spread_scenario          VARCHAR(20),  -- 'standard' | 'stress_2x'
    feature_json             JSONB,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(trade_id)
);

-- Day-by-day equity curve in R-multiples
CREATE TABLE IF NOT EXISTS research.daily_equity (
    id               BIGSERIAL PRIMARY KEY,
    run_id           VARCHAR(100) REFERENCES research.replay_runs(run_id),
    date             DATE NOT NULL,
    daily_r          NUMERIC(8,4),   -- net R for the day
    equity_r         NUMERIC(10,4),  -- cumulative net R from run start
    drawdown         NUMERIC(8,6),   -- fractional drawdown from peak equity
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, date)
);

-- =====================================================================
-- analytics schema
-- =====================================================================

CREATE TABLE IF NOT EXISTS analytics.strategy_metrics (
    id              SERIAL PRIMARY KEY,
    run_id          VARCHAR(100) REFERENCES research.replay_runs(run_id),
    strategy        VARCHAR(100),
    total_trades    INTEGER,
    winning_trades  INTEGER,
    losing_trades   INTEGER,
    win_rate        NUMERIC(5,2),
    profit_factor   NUMERIC(8,4),
    expectancy      NUMERIC(8,4),
    average_win     NUMERIC(8,4),
    average_loss    NUMERIC(8,4),
    max_drawdown    NUMERIC(8,4),
    net_r           NUMERIC(10,2),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analytics.monthly_metrics (
    id              SERIAL PRIMARY KEY,
    run_id          VARCHAR(100) REFERENCES research.replay_runs(run_id),
    month           VARCHAR(7),   -- 'YYYY-MM'
    trades          INTEGER,
    win_rate        NUMERIC(5,2),
    profit_factor   NUMERIC(8,4),
    net_r           NUMERIC(10,2),
    drawdown        NUMERIC(8,4),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analytics.optimization_results (
    id               SERIAL PRIMARY KEY,
    strategy_id      INTEGER REFERENCES research.strategies(id),
    parameter_name   VARCHAR(50),
    parameter_value  TEXT,
    trade_count      INTEGER,
    profit_factor    NUMERIC(8,4),
    expectancy       NUMERIC(8,4),
    max_drawdown     NUMERIC(8,4),
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Phase-0 gate verdict table — permanent record, one row per run
CREATE TABLE IF NOT EXISTS analytics.phase0_gate (
    id               SERIAL PRIMARY KEY,
    run_id           VARCHAR(100) UNIQUE NOT NULL,
    symbol           VARCHAR(20),
    scenario         VARCHAR(20),   -- 'standard' | 'stress_2x'
    n_trades         INTEGER,
    net_pf           NUMERIC(8,4),
    min_trades_req   INTEGER,
    min_pf_req       NUMERIC(8,4),
    gate_pass        BOOLEAN,
    evaluated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes            TEXT
);

CREATE TABLE IF NOT EXISTS analytics.experiment_log (
    id                  SERIAL PRIMARY KEY,
    experiment_name     VARCHAR(200),
    hypothesis          TEXT,
    change_description  TEXT,
    result              TEXT,
    verdict_log_ref     VARCHAR(20),  -- e.g. 'ST-A', 'ST-B'
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================================
-- config schema
-- =====================================================================

CREATE TABLE IF NOT EXISTS config.system_config (
    key         VARCHAR(100) PRIMARY KEY,
    value       TEXT,
    description TEXT,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================================
-- Seed data
-- =====================================================================

INSERT INTO market.instruments (symbol, asset_type, base_currency, quote_currency, pip_size)
VALUES
    ('EURUSD', 'forex', 'EUR', 'USD', 0.0001),
    ('GBPUSD', 'forex', 'GBP', 'USD', 0.0001)
ON CONFLICT (symbol) DO NOTHING;

INSERT INTO config.system_config (key, value, description) VALUES
    ('LIVE_TRADING',   'false',  'Must remain false until Phase-1 gate passes AND 30-day paper clean'),
    ('SPREAD_EURUSD',  '0.8',    'Standard spread pips — VT Markets'),
    ('SPREAD_GBPUSD',  '1.2',    'Standard spread pips — VT Markets'),
    ('COMMISSION_RT',  '0.6',    'Round-trip commission pips — VT Markets Standard'),
    ('PHASE0_MIN_N',   '50',     'Minimum trade count for Phase-0 gate'),
    ('PHASE0_MIN_PF',  '1.0',    'Minimum net profit factor for Phase-0 gate')
ON CONFLICT (key) DO NOTHING;
