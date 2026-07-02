export interface SessionState {
  authenticated: boolean;
  actor: string;
  role: string;
  auth_mode: string;
  permitted_actions: string[];
  mutation_allowed: boolean;
  trading_mode: string;
  demo_only: boolean;
  live_trading_enabled: boolean;
  fetched_at: string;
}

export interface ReportSummary {
  report_id?: string;
  id?: string;
  report_type?: string;
  title?: string;
  created_at?: string;
  generated_at?: string;
  filename?: string;
  path?: string;
}

export interface ReportDetail extends ReportSummary {
  content: string;
  reviewed_at?: string;
  fetched_at?: string;
}

export interface PipelineStage {
  stage_num: number;
  stage: string;
  stage_label: string;
  status: string;
  score: number;
  promotion_allowed: boolean;
  generated_at: string;
  metrics: Record<string, unknown>;
  findings: Array<Record<string, unknown>>;
  hard_gate_results: Array<Record<string, unknown>>;
  warnings: Array<Record<string, unknown> | string>;
  remediation: Array<Record<string, unknown> | string>;
}

export interface StrategyPipelineReport {
  strategy_id: string;
  strategy_name: string;
  strategy_version: string;
  run_id: string;
  generated_at: string;
  overall_status: string;
  latest_passed_stage: string;
  stages: PipelineStage[];
}

export interface IncidentRecord {
  incident_id?: string;
  id?: string;
  title?: string;
  severity?: string;
  status?: string;
  message?: string;
  summary?: string;
  created_at?: string;
  timestamp?: string;
  reviewed_at?: string;
  [key: string]: unknown;
}

export interface LiveOverview {
  account_balance: number;
  equity: number;
  unrealized_pnl: number;
  realized_pnl: number;
  daily_pnl: number;
  weekly_pnl: number;
  monthly_pnl: number;
  margin: number;
  free_margin: number;
  margin_level_pct: number;
  drawdown_pct: number;
  todays_risk: number;
  open_positions: number;
  pending_orders: number;
  broker_status: string;
  market_status: string;
  connection_health: string;
  last_update_time: string;
}

export interface PositionItem {
  id: string;
  symbol: string;
  direction: string;
  volume: number;
  entry_price: number;
  current_price: number;
  stop_loss: number;
  take_profit: number;
  unrealized_pnl: number;
  strategy_name: string;
  status: string;
  open_time: string;
  holding_time: string;
  magic?: number | string;
}

export interface OrderItem {
  id: string;
  symbol: string;
  direction: string;
  volume: number;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  status: string;
  created_at: string;
  comment: string;
}

export interface RiskWarning {
  level: string;
  message: string;
}

export interface LiveSnapshot {
  overview: LiveOverview;
  portfolio: {
    summary: Record<string, number>;
    equity_curve: Array<{ time: string; value: number }>;
    exposure: Record<string, number>;
    asset_allocation: Array<{ symbol: string; volume: number }>;
    symbol_distribution: Array<{ symbol: string; count: number }>;
    daily_statistics: Record<string, number>;
    monthly_statistics: Record<string, number>;
    performance_metrics: Record<string, number>;
  };
  positions: {
    items: PositionItem[];
    count: number;
  };
  orders: {
    pending: OrderItem[];
    filled: OrderItem[];
    cancelled: OrderItem[];
    rejected: OrderItem[];
    all: OrderItem[];
  };
  trade_history: {
    trades: Array<Record<string, string | number | null>>;
  };
  execution_monitor: {
    current_execution_queue: Array<Record<string, string | number>>;
    execution_latency_ms: number;
    order_status: string;
    fill_status: string;
    broker_response: string;
    retry_count: number;
    processing_time_ms: number;
    broker_status: string;
  };
  risk_dashboard: {
    daily_risk: number;
    open_risk: number;
    exposure: number;
    current_drawdown_pct: number;
    maximum_drawdown_pct: number;
    position_size: number;
    margin_usage_pct: number;
    risk_limits: Record<string, unknown>;
    daily_loss_limit: number;
    consecutive_losses: number;
    free_margin: number;
    warnings: RiskWarning[];
  };
  broker_status: {
    broker_connection: string;
    mt5_status: string;
    metaapi_status: string;
    ping_ms: number;
    server_time: string;
    account_type: string;
    market_open_status: string;
    spread: number;
    connection_quality: string;
    server: string;
    broker_response: string;
    last_heartbeat: string;
  };
  market_watch: {
    symbols: Array<{ symbol: string; bid: number; ask: number; spread_pips: number; time: string }>;
    watchlist: string[];
  };
  trading_chart: {
    symbol: string;
    timeframe: string;
    candles: Array<{ time: string; open: number; high: number; low: number; close: number; volume?: number }>;
  };
  system: {
    trading_mode: string;
    demo_only: boolean;
    live_trading_enabled: boolean;
    vantage_demo_configured: boolean;
    metaapi_configured: boolean;
    emergency_stop: {
      active?: boolean;
      reason?: string;
      scope?: string;
      activated_by?: string;
      activated_at?: string;
      cleared_at?: string;
      cleared_by?: string;
    };
  };
  fetched_at: string;
}

export interface StrategySummary {
  id: string;
  name: string;
  version: string;
  description: string;
  author: string;
  createdAt: string;
  updatedAt: string;
  status: string;
  rules: Record<string, unknown>;
  evidence: Record<string, unknown>;
  auditLog: Array<Record<string, unknown>>;
  versionHistory: Array<Record<string, unknown>>;
}

export interface RegistryStrategy {
  strategy: string;
  current_stage: string;
  latest_version: string;
  evidence_count: number;
  transition_count: number;
  version_count: number;
  supported_brokers: string[];
  supported_symbols: string[];
  release: Record<string, unknown>;
  deployments: Array<Record<string, unknown>>;
  rollbacks: Array<Record<string, unknown>>;
  manifest: Record<string, unknown>;
}

export interface DeploymentRecord {
  deployment_id: string;
  strategy: string;
  version: string;
  status: string;
  target: string;
  requested_at: string;
  actor: string;
  notes: string;
  live_trading_enabled: boolean;
  report_count: number;
  last_report_at: string;
}

export interface SvosSnapshot {
  overview: Record<string, unknown>;
  strategies: StrategySummary[];
  reports: {
    reports: ReportSummary[];
    latest: Record<string, ReportSummary>;
    generated_at: string;
    fetched_at: string;
  };
  governance: Record<string, unknown>;
  readiness: Record<string, unknown>;
  deployments: DeploymentRecord[];
  registry: {
    strategies: RegistryStrategy[];
    strategy_count: number;
    deployment_count: number;
    rollback_count: number;
    lifecycle_stages?: string[];
    fetched_at: string;
  };
  productionHealth: Record<string, unknown> | null;
  rgm: Record<string, unknown>;
  smo: {
    recent_incidents?: IncidentRecord[];
    recent_audit?: Array<Record<string, unknown>>;
    latest_reports?: Record<string, ReportSummary>;
    runner_status?: Record<string, unknown>;
    database_status?: Record<string, unknown>;
    execution_status?: Record<string, unknown>;
    risk_status?: Record<string, unknown>;
    incident_reviewed?: Record<string, string>;
    monitoring_status?: string;
    recommendation_badge?: string;
    unacknowledged_incident_count?: number;
    control_timeline?: Array<Record<string, unknown>>;
    emergency_stop?: Record<string, unknown>;
    [key: string]: unknown;
  };
  latestReports: {
    latest: Record<string, ReportSummary>;
    reviewed: Record<string, string>;
    recommendation_badge: string;
    generated_at: string;
    fetched_at: string;
  };
  fetched_at: string;
}

export interface RequestState<T> {
  data: T | null;
  loading: boolean;
  error: string;
  lastSuccessAt: number | null;
}
