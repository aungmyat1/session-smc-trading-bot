/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

export enum SMCStatus {
  WAITING = "WAITING",
  PASSED = "PASSED",
  FAILED = "FAILED",
  BLOCKED = "BLOCKED"
}

export enum TrendBias {
  BULLISH = "BULLISH",
  BEARISH = "BEARISH",
  NEUTRAL = "NEUTRAL"
}

export enum SystemStatus {
  ACTIVE = "ACTIVE",
  CONNECTED = "CONNECTED",
  WARNING = "WARNING",
  ERROR = "ERROR",
  DISCONNECTED = "DISCONNECTED"
}

export interface PipelineStage {
  status: SMCStatus;
  reason: string;
  timestamp: string;
}

export interface LivePipeline {
  htfBias: PipelineStage;
  liquiditySweep: PipelineStage;
  choch: PipelineStage;
  bos: PipelineStage;
  orderBlock: PipelineStage;
  fvg: PipelineStage;
  confluence: PipelineStage;
  killZone: PipelineStage;
  spread: PipelineStage;
  riskCheck: PipelineStage;
  positionSize: PipelineStage;
  ready: PipelineStage;
}

export interface SMCObject {
  id: string;
  type: "OB" | "FVG" | "LIQUIDITY";
  rangeStart: number;
  rangeEnd: number;
  strength: "HIGH" | "MEDIUM" | "LOW";
  status: "UNMITIGATED" | "MITIGATED" | "SWEPT";
  age: number; // in candles
}

export interface Candle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface PairState {
  symbol: string;
  price: number;
  trend: TrendBias;
  htfBias: TrendBias;
  spread: number; // in pips
  atr: number; // in pips
  swingHigh: number;
  swingLow: number;
  pipeline: LivePipeline;
  activeObjects: SMCObject[];
  candles: Candle[];
}

export interface SignalChecklist {
  htfBias: boolean;
  bos: boolean;
  choch: boolean;
  orderBlock: boolean;
  fvg: boolean;
  killZone: boolean;
  spread: boolean;
  risk: boolean;
  positionSize: boolean;
  qualityScore: number; // 0 to 100
}

export interface RejectionLog {
  id: string;
  timestamp: string;
  pair: string;
  rule: string;
  reason: string;
  metrics: string;
}

export interface PendingTrade {
  type: "BUY" | "SELL";
  entry: number;
  sl: number;
  tp: number;
  riskPercent: number;
  riskAmount: number;
  rr: number;
  lotSize: number;
  confidence: number; // 0 to 100
  expectedProfit: number;
  expectedLoss: number;
  reason: string;
}

export interface ExecutedTrade {
  id: string;
  pair: string;
  type: "BUY" | "SELL";
  lots: number;
  entry: number;
  exit: number;
  sl: number;
  tp: number;
  pnl: number;
  status: "PROFIT" | "LOSS" | "BREAKEAVEN" | "ACTIVE";
  entryTime: string;
  exitTime: string;
  duration: string; // duration string e.g. "45m 12s"
  exitReason: string; // e.g. "TP Hit", "SL Hit", "Manual Close"
  mae: number; // Maximum Adverse Excursion (in pips)
  mfe: number; // Maximum Favorable Excursion (in pips)
  latency: number; // execution latency in ms
  slippage: number; // slippage in pips
  commission: number; // commission in USD
  realRr: number; // realized risk reward
  explanation: string[]; // passed rules list
}

export interface ServiceHealth {
  name: string;
  status: SystemStatus;
  latency: number; // ms
  heartbeat: string;
}

export interface SystemHealth {
  broker: ServiceHealth;
  redis: ServiceHealth;
  database: ServiceHealth;
  riskEngine: ServiceHealth;
  executionEngine: ServiceHealth;
  strategyEngine: ServiceHealth;
  websocket: ServiceHealth;
  clockSync: string;
}

export interface SessionAnalytics {
  signalsQualified: number;
  signalsRejected: number;
  signalsExecuted: number;
  winRate: number; // e.g. 64.28
  avgRr: number;
  avgSpread: number;
  dailyRiskUsed: number; // percent
}

export interface EventLog {
  id: string;
  timestamp: string;
  level: "INFO" | "WARNING" | "CRITICAL" | "SUCCESS";
  message: string;
}

export interface StrategyPackage {
  id: string;
  name: string;
  version: string;
  signature: string;
  symbols: string[];
  broker_adapter: "Bybit" | "MT5" | "Binance";
  // The mock server sends a simple label; the real backend
  // (dashboard/strategy_service.py) sends the actual per-strategy risk rule
  // thresholds as an object. Both are valid — render accordingly.
  risk_profile: "Low" | "Medium" | "Aggressive" | Record<string, number>;
  execution_rules: string[];
  validation_score: number;
  status: "running" | "paused" | "stopped";
  lastSignalTime: string;
  entryFrequency: string;
  latency: number;
  errorLogs: string[];
}

export interface RiskControls {
  maxDailyLoss: number;
  maxOpenPositions: number;
  maxLeverage: string;
  autoDisableConditions: {
    newsEvent: boolean;
    latencySpike: boolean;
    lossExceeded: boolean;
  };
}

export interface BrokerConnection {
  status: "CONNECTED" | "DISCONNECTED" | "RECONNECTING";
  latency: number;
  orderSuccessRate: number;
  heartbeat: string;
  apiCalls: number;
}

export interface SystemResources {
  cpu: number;
  ram: number;
  disk: number;
}

export interface LiveDashboardState {
  pairs: Record<string, PairState>;
  selectedPair: string;
  health: SystemHealth;
  analytics: SessionAnalytics;
  rejections: RejectionLog[];
  activeTrade: PendingTrade | null;
  history: ExecutedTrade[];
  events: EventLog[];
  isTradingPaused: boolean;
  strategyPackages: StrategyPackage[];
  activeDeployments: StrategyPackage[];
  riskControls: RiskControls;
  brokerConnection: BrokerConnection;
  systemResources: SystemResources;
  failedOrders: string[];
  retryQueue: string[];
}
