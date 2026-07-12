CREATE SCHEMA IF NOT EXISTS research;

CREATE TABLE IF NOT EXISTS research.market_bars (
  symbol TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  timestamp_utc TIMESTAMPTZ NOT NULL,
  open DOUBLE PRECISION NOT NULL,
  high DOUBLE PRECISION NOT NULL,
  low DOUBLE PRECISION NOT NULL,
  close DOUBLE PRECISION NOT NULL,
  volume DOUBLE PRECISION,
  dataset_id TEXT NOT NULL,
  PRIMARY KEY (symbol, timeframe, timestamp_utc, dataset_id)
);

CREATE TABLE IF NOT EXISTS research.tick_data (
  symbol TEXT NOT NULL,
  timestamp_utc TIMESTAMPTZ NOT NULL,
  bid DOUBLE PRECISION,
  ask DOUBLE PRECISION,
  spread DOUBLE PRECISION,
  price DOUBLE PRECISION,
  quantity DOUBLE PRECISION,
  side TEXT,
  volume DOUBLE PRECISION,
  dataset_id TEXT NOT NULL,
  PRIMARY KEY (symbol, timestamp_utc, dataset_id)
);

CREATE TABLE IF NOT EXISTS research.smc_events (
  symbol TEXT NOT NULL,
  timestamp_utc TIMESTAMPTZ NOT NULL,
  event_type TEXT NOT NULL,
  direction TEXT NOT NULL,
  price DOUBLE PRECISION NOT NULL,
  strength DOUBLE PRECISION,
  dataset_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS research.market_regimes (
  symbol TEXT NOT NULL,
  timestamp_utc TIMESTAMPTZ NOT NULL,
  regime TEXT NOT NULL,
  volatility_score DOUBLE PRECISION NOT NULL,
  trend_score DOUBLE PRECISION NOT NULL,
  dataset_id TEXT NOT NULL,
  PRIMARY KEY (symbol, timestamp_utc, dataset_id)
);

CREATE TABLE IF NOT EXISTS research.cost_models (
  symbol TEXT NOT NULL,
  model_json JSONB NOT NULL,
  dataset_id TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (symbol, dataset_id)
);

CREATE TABLE IF NOT EXISTS research.data_quality (
  path TEXT NOT NULL,
  metrics_json JSONB NOT NULL,
  status TEXT NOT NULL,
  dataset_id TEXT NOT NULL,
  PRIMARY KEY (path, dataset_id)
);

CREATE TABLE IF NOT EXISTS research.dataset_manifests (
  dataset_id TEXT PRIMARY KEY,
  manifest_json JSONB NOT NULL,
  loaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_research_market_bars_symbol_time
  ON research.market_bars (symbol, timeframe, timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_research_tick_data_symbol_time
  ON research.tick_data (symbol, timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_research_smc_events_symbol_type_time
  ON research.smc_events (symbol, event_type, timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_research_market_regimes_symbol_regime_time
  ON research.market_regimes (symbol, regime, timestamp_utc);
