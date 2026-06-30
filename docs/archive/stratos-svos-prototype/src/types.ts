/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

export enum ValidationStage {
  INTAKE = "Strategy Intake",
  AUDIT = "Strategy Audit",
  REFINEMENT = "AI Strategy Refinement",
  REPLAY = "Historical Replay",
  STATISTICAL = "Statistical Validation",
  ROBUSTNESS = "Robustness Validation",
  VIRTUAL_DEMO = "Virtual Demo Validation",
  VERIFICATION_READY = "Verification Ready",
  EXECUTION = "Execution Validation",
  LIVE_DEMO = "Live Demo",
  PRODUCTION_APPROVAL = "Production Approval"
}

export interface StrategyParameters {
  [key: string]: number | string | boolean;
}

export interface RiskRules {
  stopLossPct: number;
  takeProfitPct: number;
  maxPositionSizePct: number;
  dailyLossLimitPct: number;
}

export interface StrategyRules {
  assetClass: string;
  symbol: string;
  timeframe: string;
  entryConditions: string[];
  exitConditions: string[];
  riskRules: RiskRules;
  parameters: StrategyParameters;
}

// 1. Audit Stage Types
export interface LogicalDefect {
  id: string;
  type: "ambiguity" | "contradiction" | "missing_parameter" | "execution_conflict" | "undefined_condition";
  severity: "high" | "medium" | "low";
  title: string;
  description: string;
  affectedRule: string;
  resolution?: string;
}

export interface AuditReport {
  checkedAt: string;
  isPassed: boolean;
  score: number; // 0-100
  logicalDefects: LogicalDefect[];
  recommendations: string[];
}

// 2. Refinement Stage Types
export interface RefinementSuggestion {
  id: string;
  originalRule: string;
  refinedRule: string;
  reason: string;
  applied: boolean;
}

export interface RefinementReport {
  refinedAt: string;
  summary: string;
  changesApplied: RefinementSuggestion[];
}

// 3. Historical Replay Types
export interface Trade {
  id: string;
  type: "BUY" | "SELL";
  entryTime: string;
  entryPrice: number;
  exitTime: string;
  exitPrice: number;
  quantity: number;
  profit: number;
  profitPct: number;
  status: "OPEN" | "CLOSED";
  pnlCumulative: number;
}

export interface EquityPoint {
  time: string;
  price: number;
  equity: number;
  drawdown: number;
}

export interface ReplayReport {
  runAt: string;
  periodStart: string;
  periodEnd: string;
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  winRate: number; // 0-1
  profitFactor: number;
  maxDrawdown: number; // 0-1
  totalReturnPct: number;
  equityCurve: EquityPoint[];
  trades: Trade[];
}

// 4. Statistical Validation Types
export interface MonteCarloPath {
  id: string;
  finalReturn: number;
  maxDrawdown: number;
  path: number[]; // points over simulated time
}

export interface StatisticalReport {
  validatedAt: string;
  sharpeRatio: number;
  sortinoRatio: number;
  tStat: number;
  pValue: number; // statistical significance
  isPassed: boolean;
  monteCarloPercentiles: {
    p10: number; // 10th percentile
    p50: number; // median
    p90: number; // 90th percentile
  };
  regimePerformance: {
    bullMarketReturnPct: number;
    bearMarketReturnPct: number;
    highVolatilityReturnPct: number;
    lowVolatilityReturnPct: number;
  };
}

// 5. Robustness Validation Types
export interface ParameterSweepPoint {
  paramValue: number;
  sharpeRatio: number;
  winRate: number;
  totalReturnPct: number;
}

export interface StressTestScenario {
  name: string;
  description: string;
  returnPct: number;
  maxDrawdownPct: number;
  notes: string;
}

export interface RobustnessReport {
  testedAt: string;
  parameterSensitivity: {
    parameterName: string;
    sweepPoints: ParameterSweepPoint[];
  };
  stressScenarios: StressTestScenario[];
  noiseTestPassed: boolean;
  slippageSensitivityPct: number; // drag per 1bp slippage
}

// 6. Virtual Demo Types
export interface BrokerSimulationLog {
  time: string;
  level: "INFO" | "WARNING" | "ERROR" | "EXECUTION";
  message: string;
  latencyMs: number;
  spreadBps: number;
  slippageBps: number;
}

export interface VirtualDemoReport {
  startedAt: string;
  durationHours: number;
  simulatedOrdersSubmitted: number;
  simulatedOrdersFilled: number;
  simulatedOrdersRejected: number;
  averageLatencyMs: number;
  slippageCostPct: number;
  simulatedProfitPct: number;
  executionLogs: BrokerSimulationLog[];
}

// 7. Execution Validation Types
export interface SafetyCheckResult {
  ruleName: string;
  description: string;
  status: "PASSED" | "FAILED" | "WARNING";
  actualValue: string;
  thresholdValue: string;
}

export interface ExecutionSafetyReport {
  testedAt: string;
  signalIntegrityScore: number; // 0-100
  apiLatencyP99Ms: number;
  circuitBreakerTriggered: boolean;
  reconnectionSuccessRatePct: number;
  safetyChecks: SafetyCheckResult[];
}

// 8. Production Approval Types
export interface ApprovalSignOff {
  role: string;
  approver: string;
  signedAt: string;
  comments: string;
  approved: boolean;
}

export interface ProductionApprovalReport {
  approvedAt: string;
  governanceHash: string;
  certificateId: string;
  deploymentUrl?: string;
  signoffs: ApprovalSignOff[];
  riskCapLimitUsd: number;
}

// Governance Ledger Record
export interface GovernanceRecord {
  id: string;
  timestamp: string;
  actor: string;
  action: string;
  fromStage: ValidationStage | "NONE";
  toStage: ValidationStage;
  hash: string;
  evidenceSummary: string;
  details: string;
}

export interface VersionHistoryPoint {
  version: string;
  date: string;
  auditScore: number;
  safetyScore: number;
  backtestReturnPct: number;
  status?: string;
}

export interface Strategy {
  id: string;
  name: string;
  version: string;
  description: string;
  author: string;
  createdAt: string;
  updatedAt: string;
  status: ValidationStage;
  rules: StrategyRules;
  evidence: {
    audit?: AuditReport;
    refinement?: RefinementReport;
    replay?: ReplayReport;
    statistics?: StatisticalReport;
    robustness?: RobustnessReport;
    virtualDemo?: VirtualDemoReport;
    executionSafety?: ExecutionSafetyReport;
    productionApproval?: ProductionApprovalReport;
  };
  auditLog: GovernanceRecord[];
  versionHistory?: VersionHistoryPoint[];
}
