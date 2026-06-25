-- =====================================================
-- TRADING RESEARCH DATABASE - COMPLETE SCHEMA
-- PostgreSQL 16+
-- =====================================================

-- Create schemas
CREATE SCHEMA IF NOT EXISTS market;
CREATE SCHEMA IF NOT EXISTS research;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS config;

SET search_path TO public, market, research, analytics, config;

-- =====================================================
-- SCHEMA: market
-- =====================================================

CREATE TABLE IF NOT EXISTS market.instruments (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) UNIQUE NOT NULL,
    asset_type VARCHAR(20) NOT NULL,
    broker_symbol VARCHAR(30),
    base_currency VARCHAR(10),
    quote_currency VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS market.candles (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    open NUMERIC(12,5),
    high NUMERIC(12,5),
    low NUMERIC(12,5),
    close NUMERIC(12,5),
    volume BIGINT,
    bid NUMERIC(12,5),
    ask NUMERIC(12,5),
    spread NUMERIC(8,5),
    source VARCHAR(30),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, timeframe, timestamp)
);

CREATE INDEX idx_candles_symbol_tf_time ON market.candles(symbol, timeframe, timestamp);

CREATE TABLE IF NOT EXISTS market.smc_events (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    event_type VARCHAR(30) NOT NULL,
    event_price NUMERIC(12,5),
    strength_score NUMERIC(5,2),
    metadata_json JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_smc_symbol_time ON market.smc_events(symbol, timestamp);
CREATE INDEX idx_smc_event_type ON market.smc_events(event_type);
CREATE INDEX idx_smc_tf ON market.smc_events(timeframe);

-- =====================================================
-- SCHEMA: research
-- =====================================================

CREATE TABLE IF NOT EXISTS research.strategies (
    id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(100) NOT NULL,
    version VARCHAR(20) NOT NULL,
    description TEXT,
    rules_json JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS research.replay_runs (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(50) UNIQUE NOT NULL,
    strategy_id INTEGER REFERENCES research.strategies(id),
    symbol VARCHAR(20),
    start_date DATE,
    end_date DATE,
    data_source VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS research.trades (
    id BIGSERIAL PRIMARY KEY,
    trade_id VARCHAR(50) UNIQUE NOT NULL,
    run_id VARCHAR(50) REFERENCES research.replay_runs(run_id),
    strategy_id INTEGER REFERENCES research.strategies(id),
    
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10),
    session VARCHAR(20),
    
    direction VARCHAR(10) CHECK (direction IN ('LONG', 'SHORT')),
    
    entry_time TIMESTAMP,
    exit_time TIMESTAMP,
    
    entry_price NUMERIC(12,5),
    stop_price NUMERIC(12,5),
    take_profit NUMERIC(12,5),
    
    risk_reward NUMERIC(5,2),
    
    result_r NUMERIC(8,2),
    profit_loss NUMERIC(12,2),
    
    exit_reason VARCHAR(30),
    spread NUMERIC(8,5),
    market_condition VARCHAR(30),
    entry_reason TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_trades_strategy ON research.trades(strategy_id);
CREATE INDEX idx_trades_symbol ON research.trades(symbol);
CREATE INDEX idx_trades_session ON research.trades(session);
CREATE INDEX idx_trades_entry_time ON research.trades(entry_time);
CREATE INDEX idx_trades_result_r ON research.trades(result_r);
CREATE INDEX idx_trades_run_id ON research.trades(run_id);

CREATE TABLE IF NOT EXISTS research.trade_features (
    id BIGSERIAL PRIMARY KEY,
    trade_id VARCHAR(50) REFERENCES research.trades(trade_id),
    
    bos_present BOOLEAN,
    choch_present BOOLEAN,
    fvg_present BOOLEAN,
    liquidity_sweep_present BOOLEAN,
    
    fvg_size NUMERIC(8,5),
    bos_strength NUMERIC(5,2),
    sweep_distance NUMERIC(8,5),
    
    feature_json JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS research.daily_equity (
    id BIGSERIAL PRIMARY KEY,
    run_id VARCHAR(50) REFERENCES research.replay_runs(run_id),
    date DATE NOT NULL,
    starting_balance NUMERIC(15,2),
    ending_balance NUMERIC(15,2),
    daily_r NUMERIC(8,2),
    drawdown NUMERIC(8,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, date)
);

-- =====================================================
-- SCHEMA: analytics
-- =====================================================

CREATE TABLE IF NOT EXISTS analytics.strategy_metrics (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(50) REFERENCES research.replay_runs(run_id),
    strategy VARCHAR(100),
    
    total_trades INTEGER,
    winning_trades INTEGER,
    losing_trades INTEGER,
    
    win_rate NUMERIC(5,2),
    profit_factor NUMERIC(8,2),
    expectancy NUMERIC(8,2),
    
    average_win NUMERIC(8,2),
    average_loss NUMERIC(8,2),
    
    max_drawdown NUMERIC(8,4),
    net_r NUMERIC(10,2),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analytics.monthly_metrics (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(50),
    month VARCHAR(7),
    trades INTEGER,
    win_rate NUMERIC(5,2),
    profit_factor NUMERIC(8,2),
    net_r NUMERIC(10,2),
    drawdown NUMERIC(8,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analytics.optimization_results (
    id SERIAL PRIMARY KEY,
    strategy_id INTEGER REFERENCES research.strategies(id),
    parameter_name VARCHAR(50),
    parameter_value TEXT,
    
    trade_count INTEGER,
    profit_factor NUMERIC(8,2),
    expectancy NUMERIC(8,2),
    max_drawdown NUMERIC(8,4),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analytics.experiment_log (
    id SERIAL PRIMARY KEY,
    experiment_name VARCHAR(200),
    hypothesis TEXT,
    change_description TEXT,
    result TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- SCHEMA: config
-- =====================================================

CREATE TABLE IF NOT EXISTS config.system_config (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default instruments
INSERT INTO market.instruments (symbol, asset_type, base_currency, quote_currency) VALUES
('EURUSD', 'forex', 'EUR', 'USD'),
('GBPUSD', 'forex', 'GBP', 'USD'),
('XAUUSD', 'commodity', 'XAU', 'USD')
ON CONFLICT (symbol) DO NOTHING;