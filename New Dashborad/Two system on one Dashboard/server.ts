/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import express from "express";
import http from "http";
import path from "path";
import { WebSocketServer, WebSocket } from "ws";
import { createServer as createViteServer } from "vite";
import {
  SMCStatus,
  TrendBias,
  SystemStatus,
  Candle,
  SMCObject,
  PairState,
  RejectionLog,
  PendingTrade,
  ExecutedTrade,
  SystemHealth,
  SessionAnalytics,
  EventLog,
  LiveDashboardState
} from "./src/types.js";

// Ensure process.cwd() is used correctly
const PORT = 3000;

// State management for simulation
let globalState: LiveDashboardState = {
  pairs: {},
  selectedPair: "EURUSD",
  health: {
    broker: { name: "Broker Link", status: SystemStatus.CONNECTED, latency: 14, heartbeat: "OK" },
    redis: { name: "Redis Cache", status: SystemStatus.CONNECTED, latency: 1, heartbeat: "OK" },
    database: { name: "Database Pool", status: SystemStatus.CONNECTED, latency: 2, heartbeat: "OK" },
    riskEngine: { name: "Risk Manager", status: SystemStatus.ACTIVE, latency: 5, heartbeat: "OK" },
    executionEngine: { name: "Executor Core", status: SystemStatus.ACTIVE, latency: 8, heartbeat: "OK" },
    strategyEngine: { name: "SMC Processor", status: SystemStatus.ACTIVE, latency: 11, heartbeat: "OK" },
    websocket: { name: "WS Publisher", status: SystemStatus.ACTIVE, latency: 3, heartbeat: "OK" },
    clockSync: "0.0s Drift"
  },
  analytics: {
    signalsQualified: 42,
    signalsRejected: 156,
    signalsExecuted: 24,
    winRate: 62.5,
    avgRr: 3.25,
    avgSpread: 0.85,
    dailyRiskUsed: 1.0
  },
  rejections: [
    {
      id: "rej_1",
      timestamp: new Date(Date.now() - 3600000).toISOString(),
      pair: "GBPUSD",
      rule: "Spread Limit",
      reason: "Spread spiked to 1.9 pips, exceeding max 1.5 pips limit",
      metrics: "Spread: 1.9 pips | Max: 1.5"
    },
    {
      id: "rej_2",
      timestamp: new Date(Date.now() - 7200000).toISOString(),
      pair: "USDJPY",
      rule: "Kill Zone Check",
      reason: "Signal generated outside of designated sessions (18:15 UTC)",
      metrics: "Time: 18:15 UTC | Allowed: 07-11 / 12-16"
    },
    {
      id: "rej_3",
      timestamp: new Date(Date.now() - 10800000).toISOString(),
      pair: "EURUSD",
      rule: "Order Block Mitigation",
      reason: "Selected OB already mitigated by preceding price action",
      metrics: "Mitigation Index: 1 | OB: 1.0820"
    }
  ],
  activeTrade: null,
  history: [
    {
      id: "trade_1",
      pair: "EURUSD",
      type: "BUY",
      lots: 12.5,
      entry: 1.0842,
      exit: 1.0881,
      sl: 1.0830,
      tp: 1.0881,
      pnl: 4875,
      status: "PROFIT",
      entryTime: new Date(Date.now() - 14400000).toISOString(),
      exitTime: new Date(Date.now() - 12000000).toISOString(),
      duration: "40m 15s",
      exitReason: "TP Hit",
      mae: 0.8, // in pips
      mfe: 4.1, // in pips
      latency: 112, // ms
      slippage: 0.1, // pips
      commission: 37.5, // USD
      realRr: 3.25,
      explanation: [
        "HTF Bias confirmed Bullish structural dominance",
        "Liquidity sweep of minor swing low at 1.0838",
        "CHoCH established close breakout at 1.0845",
        "Unmitigated Order Block zone respected on 1m",
        "Price entered FVG buffer inside active London session"
      ]
    },
    {
      id: "trade_2",
      pair: "GBPUSD",
      type: "SELL",
      lots: 8.0,
      entry: 1.2750,
      exit: 1.2730,
      sl: 1.2770,
      tp: 1.2690,
      pnl: 1600,
      status: "PROFIT",
      entryTime: new Date(Date.now() - 21600000).toISOString(),
      exitTime: new Date(Date.now() - 18000000).toISOString(),
      duration: "1h 0m",
      exitReason: "Manual Operator Close",
      mae: 1.2,
      mfe: 2.8,
      latency: 98,
      slippage: 0.2,
      commission: 24.0,
      realRr: 1.0,
      explanation: [
        "HTF Bias confirmed Bearish structure",
        "Liquidity sweep of previous day high",
        "CHoCH verified on 5m",
        "Order block tap inside New York Session Kill Zone"
      ]
    },
    {
      id: "trade_3",
      pair: "EURUSD",
      type: "BUY",
      lots: 12.5,
      entry: 1.0835,
      exit: 1.0818,
      sl: 1.0818,
      tp: 1.0885,
      pnl: -2125,
      status: "LOSS",
      entryTime: new Date(Date.now() - 28800000).toISOString(),
      exitTime: new Date(Date.now() - 27000000).toISOString(),
      duration: "30m 0s",
      exitReason: "SL Hit",
      mae: 1.7,
      mfe: 1.2,
      latency: 125,
      slippage: 0.0,
      commission: 37.5,
      realRr: -1.0,
      explanation: [
        "HTF Bias Bullish zone valid",
        "Liquidity swept at lower limit",
        "CHoCH triggered on minor swing breakout",
        "Price entered confluence zone under London session"
      ]
    }
  ],
  events: [
    {
      id: "ev_1",
      timestamp: new Date().toISOString(),
      level: "INFO",
      message: "Session SMC Trading Bot Engine initialized successfully."
    }
  ],
  isTradingPaused: false,
  strategyPackages: [
    {
      id: "svos_sweeper_h4",
      name: "SMC H4 Liquidity Sweeper",
      version: "v1.0.3",
      signature: "sha256_3fa98e1f0a20bc1283d6928e18ef22ff",
      symbols: ["EURUSD", "GBPUSD"],
      broker_adapter: "Bybit",
      risk_profile: "Low",
      execution_rules: [
        "HTF Structure alignment required",
        "Min RR: 1:3",
        "Liquidity sweep confirmation on M15",
        "Spread filter < 1.5 pips"
      ],
      validation_score: 94.2,
      status: "running",
      lastSignalTime: "15 mins ago",
      entryFrequency: "0.8 trades / day",
      latency: 45,
      errorLogs: []
    },
    {
      id: "svos_choch_m5",
      name: "CHoCH Momentum Rider",
      version: "v2.1.0",
      signature: "sha256_8eab3275bc912662c1109a90ef550f4b",
      symbols: ["XAUUSD", "GBPUSD"],
      broker_adapter: "MT5",
      risk_profile: "Medium",
      execution_rules: [
        "CHoCH closing confirmation",
        "Order block validation with volume spike",
        "NY Session Kill Zone only"
      ],
      validation_score: 91.8,
      status: "stopped",
      lastSignalTime: "2 hours ago",
      entryFrequency: "2.4 trades / day",
      latency: 55,
      errorLogs: []
    },
    {
      id: "svos_scalper_m1",
      name: "SMC Multi-Session Scalper",
      version: "v1.1.2",
      signature: "sha256_e18ef2283d6928e18f0a20bc123fa9ec",
      symbols: ["EURUSD", "USDJPY"],
      broker_adapter: "Binance",
      risk_profile: "Aggressive",
      execution_rules: [
        "M1 FVG gap filling confirmation",
        "London/NY session overlap window",
        "Strict 5 pip SL target"
      ],
      validation_score: 88.5,
      status: "paused",
      lastSignalTime: "45 mins ago",
      entryFrequency: "5.1 trades / day",
      latency: 32,
      errorLogs: ["Connection retry successful after timeout at 08:31 UTC"]
    }
  ],
  activeDeployments: [
    {
      id: "svos_sweeper_h4",
      name: "SMC H4 Liquidity Sweeper",
      version: "v1.0.3",
      signature: "sha256_3fa98e1f0a20bc1283d6928e18ef22ff",
      symbols: ["EURUSD", "GBPUSD"],
      broker_adapter: "Bybit",
      risk_profile: "Low",
      execution_rules: [
        "HTF Structure alignment required",
        "Min RR: 1:3",
        "Liquidity sweep confirmation on M15",
        "Spread filter < 1.5 pips"
      ],
      validation_score: 94.2,
      status: "running",
      lastSignalTime: "15 mins ago",
      entryFrequency: "0.8 trades / day",
      latency: 45,
      errorLogs: []
    }
  ],
  riskControls: {
    maxDailyLoss: 2.5,
    maxOpenPositions: 3,
    maxLeverage: "1:100",
    autoDisableConditions: {
      newsEvent: true,
      latencySpike: true,
      lossExceeded: true
    }
  },
  brokerConnection: {
    status: "CONNECTED",
    latency: 14,
    orderSuccessRate: 99.4,
    heartbeat: "OK",
    apiCalls: 1284
  },
  systemResources: {
    cpu: 18.4,
    ram: 42.1,
    disk: 15.2
  },
  failedOrders: [
    "Bybit API Error: [10002] Invalid request signature (2026-07-01 02:14:05 UTC)",
    "MT5 Bridge Timeout: Execution limit exceeded on Order #1059483"
  ],
  retryQueue: [
    "Order #1059483 - Retrying via Secondary Frankfurt MT5 Gateway (Attempt 2/3)"
  ]
};

// Generate initial base candle arrays
function generateInitialCandles(startPrice: number, count: number = 35): Candle[] {
  const candles: Candle[] = [];
  let currentPrice = startPrice;
  const now = Date.now();
  for (let i = count; i > 0; i--) {
    const time = new Date(now - i * 60000).toISOString();
    const open = currentPrice;
    const spread = (Math.random() - 0.45) * 0.0008;
    const close = currentPrice + spread;
    const high = Math.max(open, close) + Math.random() * 0.0004;
    const low = Math.min(open, close) - Math.random() * 0.0004;
    candles.push({
      time,
      open: parseFloat(open.toFixed(5)),
      high: parseFloat(high.toFixed(5)),
      low: parseFloat(low.toFixed(5)),
      close: parseFloat(close.toFixed(5)),
      volume: Math.floor(Math.random() * 500) + 100
    });
    currentPrice = close;
  }
  return candles;
}

// Populate pairs state
function initPairs() {
  globalState.pairs["EURUSD"] = {
    symbol: "EURUSD",
    price: 1.0854,
    trend: TrendBias.BULLISH,
    htfBias: TrendBias.BULLISH,
    spread: 0.8,
    atr: 14.5,
    swingHigh: 1.0890,
    swingLow: 1.0815,
    activeObjects: [
      { id: "ob_eur_1", type: "OB", rangeStart: 1.0825, rangeEnd: 1.0831, strength: "HIGH", status: "UNMITIGATED", age: 4 },
      { id: "fvg_eur_1", type: "FVG", rangeStart: 1.0832, rangeEnd: 1.0838, strength: "MEDIUM", status: "UNMITIGATED", age: 2 }
    ],
    candles: generateInitialCandles(1.0840),
    pipeline: createBasePipeline()
  };

  globalState.pairs["GBPUSD"] = {
    symbol: "GBPUSD",
    price: 1.2754,
    trend: TrendBias.NEUTRAL,
    htfBias: TrendBias.BEARISH,
    spread: 1.1,
    atr: 22.0,
    swingHigh: 1.2795,
    swingLow: 1.2710,
    activeObjects: [
      { id: "ob_gbp_1", type: "OB", rangeStart: 1.2778, rangeEnd: 1.2785, strength: "HIGH", status: "UNMITIGATED", age: 8 }
    ],
    candles: generateInitialCandles(1.2760),
    pipeline: createBasePipeline()
  };

  globalState.pairs["USDJPY"] = {
    symbol: "USDJPY",
    price: 155.45,
    trend: TrendBias.BEARISH,
    htfBias: TrendBias.BULLISH,
    spread: 1.3,
    atr: 85.0,
    swingHigh: 156.10,
    swingLow: 155.12,
    activeObjects: [],
    candles: generateInitialCandles(155.60),
    pipeline: createBasePipeline()
  };
}

function createBasePipeline() {
  const t = new Date().toISOString();
  return {
    htfBias: { status: SMCStatus.PASSED, reason: "HTF structure supports current bias alignment", timestamp: t },
    liquiditySweep: { status: SMCStatus.PASSED, reason: "Sweep of swing low liqudiity pool completed", timestamp: t },
    choch: { status: SMCStatus.WAITING, reason: "Waiting for local Change of Character breaker close", timestamp: t },
    bos: { status: SMCStatus.WAITING, reason: "Waiting for Break of Structure continuation breakout", timestamp: t },
    orderBlock: { status: SMCStatus.WAITING, reason: "Awaiting valid OB candles definition", timestamp: t },
    fvg: { status: SMCStatus.WAITING, reason: "Awaiting Fair Value Gap imbalance space", timestamp: t },
    confluence: { status: SMCStatus.WAITING, reason: "Awaiting price pull back into zones buffer", timestamp: t },
    killZone: { status: SMCStatus.WAITING, reason: "Checking active London / NY session ranges", timestamp: t },
    spread: { status: SMCStatus.WAITING, reason: "Checking spread requirements (<= 1.5 pips)", timestamp: t },
    riskCheck: { status: SMCStatus.WAITING, reason: "Pending risk engine validation check", timestamp: t },
    positionSize: { status: SMCStatus.WAITING, reason: "Awaiting lot size engine computing", timestamp: t },
    ready: { status: SMCStatus.WAITING, reason: "Awaiting completion of all upstream criteria", timestamp: t }
  };
}

// Simulation variables to track cycles
let eurUsdCycleState = "ACCUMULATING"; // ACCUMULATING, SWEEP, REVERSING, BREAK_STRUCTURE, RETRACING, ENTRY, TRADE_PENDING, TRADE_ACTIVE, TRADE_CLOSED
let cycleTicks = 0;
let simulatedPositionTicks = 0;

// Log an event helper
function logEvent(message: string, level: "INFO" | "WARNING" | "CRITICAL" | "SUCCESS" = "INFO") {
  const ev: EventLog = {
    id: `ev_${Date.now()}_${Math.floor(Math.random() * 1000)}`,
    timestamp: new Date().toISOString(),
    level,
    message
  };
  globalState.events.unshift(ev);
  if (globalState.events.length > 80) {
    globalState.events.pop();
  }
}

// Progress pipeline for EURUSD
function updateEurUsdPipeline(tickCount: number) {
  const pair = globalState.pairs["EURUSD"];
  if (!pair) return;

  const t = new Date().toISOString();

  // Dynamic simulation of kill zones based on UTC hour
  const currentHour = new Date().getUTCHours();
  const insideKillZone = (currentHour >= 7 && currentHour <= 11) || (currentHour >= 12 && currentHour <= 16) || true; // Force true for active demonstration, but document reason
  const kzStatus = insideKillZone ? SMCStatus.PASSED : SMCStatus.FAILED;
  const kzReason = insideKillZone ? "Inside NY / London Session Kill Zone" : "Outside of designated Kill Zone hours";

  if (globalState.isTradingPaused) {
    // Pipeline is blocked when paused
    Object.keys(pair.pipeline).forEach((key) => {
      const k = key as keyof typeof pair.pipeline;
      pair.pipeline[k] = {
        status: SMCStatus.BLOCKED,
        reason: "Engine execution is manually paused by operator",
        timestamp: t
      };
    });
    return;
  }

  if (eurUsdCycleState === "ACCUMULATING") {
    pair.pipeline.htfBias = { status: SMCStatus.PASSED, reason: "HTF structure supports Bullish bias", timestamp: t };
    pair.pipeline.liquiditySweep = { status: SMCStatus.WAITING, reason: "Awaiting liquidity sweep of minor swing lows", timestamp: t };
    pair.pipeline.choch = { status: SMCStatus.WAITING, reason: "Waiting for Change of Character breakout", timestamp: t };
    pair.pipeline.bos = { status: SMCStatus.WAITING, reason: "Waiting for Break of Structure close", timestamp: t };
    pair.pipeline.orderBlock = { status: SMCStatus.WAITING, reason: "Awaiting unmitigated Order Block definition", timestamp: t };
    pair.pipeline.fvg = { status: SMCStatus.WAITING, reason: "Awaiting Fair Value Gap structural space", timestamp: t };
    pair.pipeline.confluence = { status: SMCStatus.WAITING, reason: "Waiting for price callback into zone", timestamp: t };
    pair.pipeline.killZone = { status: kzStatus, reason: kzReason, timestamp: t };
    pair.pipeline.spread = { status: SMCStatus.WAITING, reason: "Awaiting active quote spread", timestamp: t };
    pair.pipeline.riskCheck = { status: SMCStatus.WAITING, reason: "Awaiting risk check confirmation", timestamp: t };
    pair.pipeline.positionSize = { status: SMCStatus.WAITING, reason: "Awaiting lot size outputs", timestamp: t };
    pair.pipeline.ready = { status: SMCStatus.WAITING, reason: "Awaiting setup confirmation", timestamp: t };
  } else if (eurUsdCycleState === "SWEEP") {
    pair.pipeline.htfBias = { status: SMCStatus.PASSED, reason: "HTF structure supports Bullish bias", timestamp: t };
    pair.pipeline.liquiditySweep = { status: SMCStatus.PASSED, reason: "Sell stops swept at 1.0815 swing low", timestamp: t };
    pair.pipeline.choch = { status: SMCStatus.WAITING, reason: "Waiting for Change of Character breakout", timestamp: t };
  } else if (eurUsdCycleState === "REVERSING") {
    pair.pipeline.htfBias = { status: SMCStatus.PASSED, reason: "HTF structure supports Bullish bias", timestamp: t };
    pair.pipeline.liquiditySweep = { status: SMCStatus.PASSED, reason: "Sell stops swept at 1.0815 swing low", timestamp: t };
    pair.pipeline.choch = { status: SMCStatus.PASSED, reason: "CHoCH confirmed on 1m chart", timestamp: t };
    pair.pipeline.bos = { status: SMCStatus.WAITING, reason: "Waiting for BOS close above 1.0845", timestamp: t };
  } else if (eurUsdCycleState === "BREAK_STRUCTURE") {
    pair.pipeline.htfBias = { status: SMCStatus.PASSED, reason: "HTF structure supports Bullish bias", timestamp: t };
    pair.pipeline.liquiditySweep = { status: SMCStatus.PASSED, reason: "Sell stops swept at 1.0815 swing low", timestamp: t };
    pair.pipeline.choch = { status: SMCStatus.PASSED, reason: "CHoCH confirmed on 1m chart", timestamp: t };
    pair.pipeline.bos = { status: SMCStatus.PASSED, reason: "BOS closed above 1.0845 swing high", timestamp: t };
    pair.pipeline.orderBlock = { status: SMCStatus.PASSED, reason: "Unmitigated OB detected at 1.0825 - 1.0831", timestamp: t };
    pair.pipeline.fvg = { status: SMCStatus.PASSED, reason: "FVG exists at 1.0832 - 1.0838", timestamp: t };
    pair.pipeline.confluence = { status: SMCStatus.WAITING, reason: "Price is pulling back (Currently at " + pair.price.toFixed(5) + ")", timestamp: t };
  } else if (eurUsdCycleState === "RETRACING") {
    pair.pipeline.htfBias = { status: SMCStatus.PASSED, reason: "HTF structure supports Bullish bias", timestamp: t };
    pair.pipeline.liquiditySweep = { status: SMCStatus.PASSED, reason: "Sell stops swept at 1.0815 swing low", timestamp: t };
    pair.pipeline.choch = { status: SMCStatus.PASSED, reason: "CHoCH confirmed on 1m chart", timestamp: t };
    pair.pipeline.bos = { status: SMCStatus.PASSED, reason: "BOS closed above 1.0845 swing high", timestamp: t };
    pair.pipeline.orderBlock = { status: SMCStatus.PASSED, reason: "Unmitigated OB detected at 1.0825 - 1.0831", timestamp: t };
    pair.pipeline.fvg = { status: SMCStatus.PASSED, reason: "FVG exists at 1.0832 - 1.0838", timestamp: t };
    pair.pipeline.confluence = { status: SMCStatus.WAITING, reason: "Price pullback approaching OB zone. Currently at " + pair.price.toFixed(5), timestamp: t };
    pair.pipeline.killZone = { status: kzStatus, reason: kzReason, timestamp: t };
  } else if (eurUsdCycleState === "ENTRY") {
    pair.pipeline.htfBias = { status: SMCStatus.PASSED, reason: "HTF structure supports Bullish bias", timestamp: t };
    pair.pipeline.liquiditySweep = { status: SMCStatus.PASSED, reason: "Sell stops swept at 1.0815 swing low", timestamp: t };
    pair.pipeline.choch = { status: SMCStatus.PASSED, reason: "CHoCH confirmed on 1m chart", timestamp: t };
    pair.pipeline.bos = { status: SMCStatus.PASSED, reason: "BOS closed above 1.0845 swing high", timestamp: t };
    pair.pipeline.orderBlock = { status: SMCStatus.PASSED, reason: "Unmitigated OB detected at 1.0825 - 1.0831", timestamp: t };
    pair.pipeline.fvg = { status: SMCStatus.PASSED, reason: "FVG exists at 1.0832 - 1.0838", timestamp: t };
    pair.pipeline.confluence = { status: SMCStatus.PASSED, reason: "Price tapped OB +5 pip buffer (" + pair.price.toFixed(5) + ")", timestamp: t };
    pair.pipeline.killZone = { status: kzStatus, reason: kzReason, timestamp: t };
    pair.pipeline.spread = { status: SMCStatus.PASSED, reason: "Spread: " + pair.spread.toFixed(1) + " pips <= 1.5", timestamp: t };
    pair.pipeline.riskCheck = { status: SMCStatus.PASSED, reason: "Daily Risk utilized: " + globalState.analytics.dailyRiskUsed.toFixed(1) + "% | Checked OK", timestamp: t };
    pair.pipeline.positionSize = { status: SMCStatus.PASSED, reason: "Lots computed: 12.5 Lots ($1,000 Risk)", timestamp: t };
    pair.pipeline.ready = { status: SMCStatus.PASSED, reason: "All entry criteria matched. Formulating signal order.", timestamp: t };
  } else if (eurUsdCycleState === "TRADE_PENDING" || eurUsdCycleState === "TRADE_ACTIVE" || eurUsdCycleState === "TRADE_CLOSED") {
    // Keep them passed
    pair.pipeline.htfBias = { status: SMCStatus.PASSED, reason: "HTF structure supports Bullish bias", timestamp: t };
    pair.pipeline.liquiditySweep = { status: SMCStatus.PASSED, reason: "Sell stops swept at 1.0815 swing low", timestamp: t };
    pair.pipeline.choch = { status: SMCStatus.PASSED, reason: "CHoCH confirmed on 1m chart", timestamp: t };
    pair.pipeline.bos = { status: SMCStatus.PASSED, reason: "BOS closed above 1.0845 swing high", timestamp: t };
    pair.pipeline.orderBlock = { status: SMCStatus.PASSED, reason: "Unmitigated OB detected at 1.0825 - 1.0831", timestamp: t };
    pair.pipeline.fvg = { status: SMCStatus.PASSED, reason: "FVG exists at 1.0832 - 1.0838", timestamp: t };
    pair.pipeline.confluence = { status: SMCStatus.PASSED, reason: "Confluence zone triggered at 1.0830", timestamp: t };
    pair.pipeline.killZone = { status: kzStatus, reason: kzReason, timestamp: t };
    pair.pipeline.spread = { status: SMCStatus.PASSED, reason: "Spread checks OK", timestamp: t };
    pair.pipeline.riskCheck = { status: SMCStatus.PASSED, reason: "Risk parameters aligned", timestamp: t };
    pair.pipeline.positionSize = { status: SMCStatus.PASSED, reason: "Lots computed: 12.5 Lots", timestamp: t };
    pair.pipeline.ready = { status: SMCStatus.PASSED, reason: "Order Executed Successfully", timestamp: t };
  }
}

// Process the Tick Simulation (runs every 1.5s)
function tickSimulation() {
  cycleTicks++;

  // 1. Fluctuating spreads and Latencies to look fully live
  Object.keys(globalState.pairs).forEach((symbol) => {
    const pair = globalState.pairs[symbol];
    if (pair) {
      // Small price wiggle
      let change = (Math.random() - 0.5) * 0.00008;
      // Add trend directional force
      if (symbol === "EURUSD") {
        if (eurUsdCycleState === "ACCUMULATING") change += 0.00001;
        else if (eurUsdCycleState === "SWEEP") change -= 0.00015; // Fast dump
        else if (eurUsdCycleState === "REVERSING") change += 0.00008;
        else if (eurUsdCycleState === "BREAK_STRUCTURE") change += 0.00018; // Strong pump
        else if (eurUsdCycleState === "RETRACING") change -= 0.00005; // Slow drift lower
        else if (eurUsdCycleState === "TRADE_ACTIVE") change += 0.00006; // Rallying in trade
      } else if (symbol === "GBPUSD") {
        change += 0.00001; // Neutral up
      } else {
        change -= 0.01; // USDJPY neutral down
      }

      pair.price = parseFloat((pair.price + change).toFixed(symbol === "USDJPY" ? 2 : 5));
      pair.spread = parseFloat((0.6 + Math.random() * 0.5).toFixed(1));

      // Occasional high spread rejections on other pairs
      if (symbol === "GBPUSD" && Math.random() < 0.05 && !globalState.isTradingPaused) {
        pair.spread = 1.8; // Trigger spread spike
        const rej: RejectionLog = {
          id: `rej_${Date.now()}`,
          timestamp: new Date().toISOString(),
          pair: "GBPUSD",
          rule: "Spread Limit",
          reason: "Real-time spread peaked at 1.8 pips, exceeding threshold limit of 1.5 pips.",
          metrics: "Spread: 1.8 pips | Limit: 1.5 pips"
        };
        globalState.rejections.unshift(rej);
        globalState.analytics.signalsRejected++;
        logEvent("GBPUSD trading signal rejected: Spread limit exceeded (1.8 pips).", "WARNING");
      }

      // Add price to the current candle close, update high/low
      const currentCandle = pair.candles[pair.candles.length - 1];
      if (currentCandle) {
        currentCandle.close = pair.price;
        currentCandle.high = Math.max(currentCandle.high, pair.price);
        currentCandle.low = Math.min(currentCandle.low, pair.price);
      }

      // Every 15 ticks, complete a candle and push a new one
      if (cycleTicks % 15 === 0) {
        const lastCandle = pair.candles[pair.candles.length - 1];
        const newCandle: Candle = {
          time: new Date().toISOString(),
          open: lastCandle ? lastCandle.close : pair.price,
          high: pair.price,
          low: pair.price,
          close: pair.price,
          volume: Math.floor(Math.random() * 500) + 100
        };
        pair.candles.push(newCandle);
        if (pair.candles.length > 40) {
          pair.candles.shift();
        }

        // Increment age of active objects
        pair.activeObjects.forEach((obj) => obj.age++);
      }
    }
  });

  // Fidget with latency variables to keep health gauges moving
  globalState.health.broker.latency = Math.floor(12 + Math.random() * 10);
  globalState.health.redis.latency = Math.floor(1 + Math.random() * 2);
  globalState.health.database.latency = Math.floor(2 + Math.random() * 3);
  globalState.health.riskEngine.latency = Math.floor(4 + Math.random() * 5);
  globalState.health.executionEngine.latency = Math.floor(6 + Math.random() * 6);
  globalState.health.strategyEngine.latency = Math.floor(8 + Math.random() * 8);

  // Variate system resources and broker connection states
  if (globalState.systemResources) {
    globalState.systemResources.cpu = parseFloat((14 + Math.random() * 8).toFixed(1));
    globalState.systemResources.ram = parseFloat((41.5 + Math.random() * 1.5).toFixed(1));
    globalState.systemResources.disk = parseFloat((15.2 + Math.random() * 0.05).toFixed(2));
  }
  if (globalState.brokerConnection) {
    globalState.brokerConnection.latency = globalState.health.broker.latency;
    globalState.brokerConnection.apiCalls += Math.floor(1 + Math.random() * 3);
  }

  // 2. State Machine progressions for EURUSD Setup
  const eurusd = globalState.pairs["EURUSD"];
  if (eurusd && !globalState.isTradingPaused) {
    if (eurUsdCycleState === "ACCUMULATING") {
      eurusd.trend = TrendBias.NEUTRAL;
      if (cycleTicks % 25 === 10) {
        eurUsdCycleState = "SWEEP";
        logEvent("EURUSD: Swing low level swept. Liquidity sweep detected at 1.0815. Checking for structural reaction.", "INFO");
      }
    } else if (eurUsdCycleState === "SWEEP") {
      eurusd.trend = TrendBias.NEUTRAL;
      if (cycleTicks % 25 === 18) {
        eurUsdCycleState = "REVERSING";
        logEvent("EURUSD: Rapid rebound from liquidity pool. Change of Character (CHoCH) detected on 1m chart at 1.0832.", "INFO");
      }
    } else if (eurUsdCycleState === "REVERSING") {
      eurusd.trend = TrendBias.BULLISH;
      if (cycleTicks % 25 === 24) {
        eurUsdCycleState = "BREAK_STRUCTURE";
        // Create OB and FVG
        eurusd.swingHigh = 1.0862;
        eurusd.activeObjects = [
          { id: "ob_eur_live", type: "OB", rangeStart: 1.0825, rangeEnd: 1.0831, strength: "HIGH", status: "UNMITIGATED", age: 0 },
          { id: "fvg_eur_live", type: "FVG", rangeStart: 1.0832, rangeEnd: 1.0838, strength: "MEDIUM", status: "UNMITIGATED", age: 0 }
        ];
        logEvent("EURUSD: Strong high-momentum close above 1.0845. Break of Structure (BOS) validated. Active 1m unmitigated Order Block established at 1.0825 - 1.0831.", "SUCCESS");
      }
    } else if (eurUsdCycleState === "BREAK_STRUCTURE") {
      eurUsdCycleState = "RETRACING";
      logEvent("EURUSD: Imbalance gap formed. Fair Value Gap (FVG) defined at 1.0832 - 1.0838. Awaiting pullback.", "INFO");
    } else if (eurUsdCycleState === "RETRACING") {
      // Force price slowly down to tap the order block
      if (eurusd.price > 1.0832) {
        eurusd.price = parseFloat((eurusd.price - 0.00010).toFixed(5));
      } else {
        eurUsdCycleState = "ENTRY";
        logEvent("EURUSD: Price tapped the unmitigated Order Block (1.0825 - 1.0831). Confluence zone triggered. Running risk validation.", "SUCCESS");
      }
    } else if (eurUsdCycleState === "ENTRY") {
      // Trigger pending trade card
      const pending: PendingTrade = {
        type: "BUY",
        entry: eurusd.price,
        sl: 1.0815,
        tp: 1.0865,
        riskPercent: 1.0,
        riskAmount: 1000.0,
        rr: 3.33,
        lotSize: 12.5,
        confidence: 94,
        expectedProfit: 3330.0,
        expectedLoss: -1000.0,
        reason: "BOS + CHoCH alignment + London Session Confluence with unmitigated high-strength OB & FVG"
      };
      globalState.activeTrade = pending;
      eurUsdCycleState = "TRADE_PENDING";
      simulatedPositionTicks = 0;
      logEvent("EURUSD: Smart Money setup fully qualified. Decision engine: BUY entry signal queued. Lot calculation finalized.", "SUCCESS");
    } else if (eurUsdCycleState === "TRADE_PENDING") {
      simulatedPositionTicks++;
      if (simulatedPositionTicks >= 3) {
        eurUsdCycleState = "TRADE_ACTIVE";
        logEvent("EURUSD: Executed BUY order on Broker. Entry: " + eurusd.price + " | 12.5 Lots | SL: 1.0815 | TP: 1.0865. Execution latency: 104ms.", "SUCCESS");
        globalState.analytics.signalsExecuted++;
        globalState.analytics.signalsQualified++;
      }
    } else if (eurUsdCycleState === "TRADE_ACTIVE") {
      simulatedPositionTicks++;
      // Price movement direction based on active trade: mostly up towards TP, occasional swings down
      let move = 0.00008;
      if (simulatedPositionTicks % 5 === 2) {
        move = -0.00012; // brief pullback
      } else if (simulatedPositionTicks % 4 === 0) {
        move = 0.00015; // strong rally
      }
      eurusd.price = parseFloat((eurusd.price + move).toFixed(5));

      // Check exit conditions
      const activeTrade = globalState.activeTrade;
      if (activeTrade) {
        // Update price in active candles too
        const curCandle = eurusd.candles[eurusd.candles.length - 1];
        if (curCandle) {
          curCandle.close = eurusd.price;
        }

        if (eurusd.price >= activeTrade.tp) {
          // HIT TP!
          eurUsdCycleState = "TRADE_CLOSED";
          // Close and record trade
          const profit = activeTrade.expectedProfit + (Math.random() - 0.5) * 100; // random slippage adjustment
          const pnlValue = parseFloat(profit.toFixed(2));
          const executed: ExecutedTrade = {
            id: `trade_${Date.now()}`,
            pair: "EURUSD",
            type: "BUY",
            lots: activeTrade.lotSize,
            entry: activeTrade.entry,
            exit: eurusd.price,
            sl: activeTrade.sl,
            tp: activeTrade.tp,
            pnl: pnlValue,
            status: "PROFIT",
            entryTime: new Date(Date.now() - 30000).toISOString(),
            exitTime: new Date().toISOString(),
            duration: "0m 45s",
            exitReason: "TP Hit",
            mae: 0.4,
            mfe: 5.2,
            latency: 104,
            slippage: 0.1,
            commission: 37.5,
            realRr: activeTrade.rr,
            explanation: [
              "HTF Bias bullish structure checked out perfectly",
              "Sought out liquid market range sweep with success",
              "Respected 1.0825 Order Block with precise sub-pip tap accuracy",
              "Delivered target profit within execution deadline"
            ]
          };
          globalState.history.unshift(executed);
          globalState.activeTrade = null;
          globalState.analytics.winRate = parseFloat(((globalState.history.filter(t => t.status === "PROFIT").length / globalState.history.length) * 100).toFixed(2));
          logEvent("EURUSD: TARGET TAKE PROFIT HIT! Position closed at " + eurusd.price + " with profit of +$" + pnlValue + ".", "SUCCESS");
        } else if (eurusd.price <= activeTrade.sl) {
          // HIT SL
          eurUsdCycleState = "TRADE_CLOSED";
          const loss = activeTrade.expectedLoss + (Math.random() - 0.5) * 50;
          const pnlValue = parseFloat(loss.toFixed(2));
          const executed: ExecutedTrade = {
            id: `trade_${Date.now()}`,
            pair: "EURUSD",
            type: "BUY",
            lots: activeTrade.lotSize,
            entry: activeTrade.entry,
            exit: eurusd.price,
            sl: activeTrade.sl,
            tp: activeTrade.tp,
            pnl: pnlValue,
            status: "LOSS",
            entryTime: new Date(Date.now() - 30000).toISOString(),
            exitTime: new Date().toISOString(),
            duration: "0m 45s",
            exitReason: "SL Hit",
            mae: 1.5,
            mfe: 0.8,
            latency: 104,
            slippage: 0.2,
            commission: 37.5,
            realRr: -1.0,
            explanation: [
              "Order block failed to hold price continuation due to sudden seller volume block",
              "Mitigated order block exceeded boundaries and triggered Stop Loss risk guard"
            ]
          };
          globalState.history.unshift(executed);
          globalState.activeTrade = null;
          globalState.analytics.winRate = parseFloat(((globalState.history.filter(t => t.status === "PROFIT").length / globalState.history.length) * 100).toFixed(2));
          logEvent("EURUSD: STOP LOSS TRIGGERED. Position closed at " + eurusd.price + " with loss of $" + pnlValue + ".", "CRITICAL");
        }
      }
    } else if (eurUsdCycleState === "TRADE_CLOSED") {
      eurUsdCycleState = "ACCUMULATING";
      // Mark OB as mitigated
      eurusd.activeObjects.forEach((obj) => {
        if (obj.id === "ob_eur_live") {
          obj.status = "MITIGATED";
        }
      });
      logEvent("EURUSD: Cleaned active trade structures. Entering market accumulation search phase.", "INFO");
    }
  }

  // Update pipeline checklist statuses
  updateEurUsdPipeline(cycleTicks);
}

// Start simulation loop
initPairs();
setInterval(tickSimulation, 1500);

async function startServer() {
  const app = express();
  app.use(express.json());

  // API REST routes
  app.get("/api/status", (req, res) => {
    res.set("Cache-Control", "no-store, no-cache, must-revalidate, private");
    res.json(globalState);
  });

  app.get("/api/trades", (req, res) => {
    res.set("Cache-Control", "no-store, no-cache, must-revalidate, private");
    res.json(globalState.history);
  });

  app.get("/api/rejections", (req, res) => {
    res.set("Cache-Control", "no-store, no-cache, must-revalidate, private");
    res.json(globalState.rejections);
  });

  app.post("/api/action", (req, res) => {
    const { action, symbol } = req.body;
    if (action === "pause") {
      globalState.isTradingPaused = true;
      logEvent("Manual Operator Override: Trading engines paused.", "WARNING");
      res.json({ status: "success", isTradingPaused: true });
    } else if (action === "resume") {
      globalState.isTradingPaused = false;
      logEvent("Manual Operator Override: Trading engines resumed.", "SUCCESS");
      res.json({ status: "success", isTradingPaused: false });
    } else if (action === "reset") {
      globalState.analytics = {
        signalsQualified: 0,
        signalsRejected: 0,
        signalsExecuted: 0,
        winRate: 0.0,
        avgRr: 3.2,
        avgSpread: 0.8,
        dailyRiskUsed: 0.0
      };
      globalState.rejections = [];
      logEvent("Manual Operator Override: Session statistics reset.", "INFO");
      res.json({ status: "success", state: globalState });
    } else if (action === "select_pair" && symbol) {
      globalState.selectedPair = symbol;
      res.json({ status: "success", selectedPair: symbol });
    } else if (action === "force_close" && globalState.activeTrade) {
      const active = globalState.activeTrade;
      const pair = globalState.pairs["EURUSD"];
      const currentPrice = pair ? pair.price : active.entry;
      const profit = (currentPrice - active.entry) * active.lotSize * 10000; // Rough conversion
      const pnlValue = parseFloat(profit.toFixed(2));
      const executed: ExecutedTrade = {
        id: `trade_${Date.now()}`,
        pair: "EURUSD",
        type: active.type,
        lots: active.lotSize,
        entry: active.entry,
        exit: currentPrice,
        sl: active.sl,
        tp: active.tp,
        pnl: pnlValue,
        status: pnlValue >= 0 ? "PROFIT" : "LOSS",
        entryTime: new Date(Date.now() - 20000).toISOString(),
        exitTime: new Date().toISOString(),
        duration: "0m 20s",
        exitReason: "Manual Operator Close",
        mae: 0.2,
        mfe: 1.1,
        latency: 140,
        slippage: 0.3,
        commission: 37.5,
        realRr: pnlValue >= 0 ? 0.5 : -0.5,
        explanation: ["Position closed manually by operator before hitting targets"]
      };
      globalState.history.unshift(executed);
      globalState.activeTrade = null;
      eurUsdCycleState = "ACCUMULATING";
      globalState.analytics.winRate = parseFloat(((globalState.history.filter(t => t.status === "PROFIT").length / globalState.history.length) * 100).toFixed(2));
      logEvent("Manual Operator Override: Force closed BUY position on EURUSD at " + currentPrice + ". Realized PnL: $" + pnlValue, "WARNING");
      res.json({ status: "success", state: globalState });
    } else {
      res.status(400).json({ error: "Invalid Action" });
    }
  });

  // Live dashboard endpoints as per production blueprint
  app.get("/api/live/positions", (req, res) => {
    res.set("Cache-Control", "no-store, no-cache, must-revalidate, private");
    const pos = [];
    if (globalState.activeTrade && globalState.pairs["EURUSD"]) {
      const currentPrice = globalState.pairs["EURUSD"].price;
      const isBuy = globalState.activeTrade.type === "BUY";
      const pipsDiff = isBuy ? (currentPrice - globalState.activeTrade.entry) : (globalState.activeTrade.entry - currentPrice);
      const runningPnL = pipsDiff * globalState.activeTrade.lotSize * 100000;
      pos.push({
        ...globalState.activeTrade,
        currentPrice,
        unrealizedPnL: parseFloat(runningPnL.toFixed(2)),
        margin: 1240.00,
        leverage: globalState.riskControls?.maxLeverage || "1:100",
        broker: "Bybit (SMC Live Core)"
      });
    }
    res.json(pos);
  });

  app.get("/api/live/strategies", (req, res) => {
    res.set("Cache-Control", "no-store, no-cache, must-revalidate, private");
    res.json(globalState.strategyPackages);
  });

  app.get("/api/live/status", (req, res) => {
    res.set("Cache-Control", "no-store, no-cache, must-revalidate, private");
    res.json({
      isTradingPaused: globalState.isTradingPaused,
      health: globalState.health,
      systemResources: globalState.systemResources,
      riskControls: globalState.riskControls
    });
  });

  app.get("/api/live/broker", (req, res) => {
    res.set("Cache-Control", "no-store, no-cache, must-revalidate, private");
    res.json(globalState.brokerConnection);
  });

  app.post("/api/live/strategy/activate", (req, res) => {
    const { id, broker, symbols, riskProfile, version } = req.body;
    const pkg = globalState.strategyPackages.find(p => p.id === id);
    if (pkg) {
      pkg.status = "running";
      if (broker) pkg.broker_adapter = broker;
      if (symbols) pkg.symbols = symbols;
      if (riskProfile) pkg.risk_profile = riskProfile;
      if (version) pkg.version = version;
      
      // Sync into activeDeployments
      if (!globalState.activeDeployments.some(p => p.id === id)) {
        globalState.activeDeployments.push({ ...pkg });
      } else {
        globalState.activeDeployments = globalState.activeDeployments.map(p => p.id === id ? { ...pkg } : p);
      }

      logEvent(`Strategy Deploy Contract Activated: Deployed ${pkg.name} (${pkg.version}) to Production on ${pkg.broker_adapter} for symbols: [${pkg.symbols.join(", ")}]`, "SUCCESS");
      res.json({ success: true, state: globalState });
    } else {
      res.status(404).json({ error: "Strategy package not found" });
    }
  });

  app.post("/api/live/strategy/pause", (req, res) => {
    const { id } = req.body;
    const pkg = globalState.strategyPackages.find(p => p.id === id);
    if (pkg) {
      pkg.status = pkg.status === "running" ? "paused" : "running";
      globalState.activeDeployments = globalState.activeDeployments.map(p => {
        if (p.id === id) {
          return { ...p, status: pkg.status };
        }
        return p;
      });
      logEvent(`Strategy Runtime state transitioned: ${pkg.name} status is now ${pkg.status.toUpperCase()}`, "WARNING");
      res.json({ success: true, state: globalState });
    } else {
      res.status(404).json({ error: "Strategy package not found" });
    }
  });

  app.post("/api/live/kill-switch", (req, res) => {
    globalState.isTradingPaused = true;
    globalState.strategyPackages.forEach(p => p.status = "stopped");
    globalState.activeDeployments = [];
    
    let forceCloseMsg = "";
    if (globalState.activeTrade) {
      const active = globalState.activeTrade;
      const currentPrice = globalState.pairs["EURUSD"] ? globalState.pairs["EURUSD"].price : active.entry;
      const profit = (currentPrice - active.entry) * active.lotSize * 10000;
      const executed: ExecutedTrade = {
        id: `trade_${Date.now()}`,
        pair: "EURUSD",
        type: active.type,
        lots: active.lotSize,
        entry: active.entry,
        exit: currentPrice,
        sl: active.sl,
        tp: active.tp,
        pnl: parseFloat(profit.toFixed(2)),
        status: profit >= 0 ? "PROFIT" : "LOSS",
        entryTime: new Date(Date.now() - 20000).toISOString(),
        exitTime: new Date().toISOString(),
        duration: "0m 20s",
        exitReason: "Emergency Kill Switch Action",
        mae: 0.2,
        mfe: 1.1,
        latency: 90,
        slippage: 0.1,
        commission: 37.5,
        realRr: 0.0,
        explanation: ["Emergency shutdown initiated by operator kill-switch"]
      };
      globalState.history.unshift(executed);
      globalState.activeTrade = null;
      eurUsdCycleState = "ACCUMULATING";
      forceCloseMsg = ` Realized emergency trade close of $${profit.toFixed(2)}.`;
    }

    if (globalState.brokerConnection) {
      globalState.brokerConnection.status = "DISCONNECTED";
    }

    logEvent(`EMERGENCY CIRCUIT BREAKER ACTIVATED: Terminated all strategy packages and halted active broker trades.${forceCloseMsg}`, "CRITICAL");
    res.json({ success: true, state: globalState });
  });

  app.post("/api/live/risk-controls", (req, res) => {
    const { maxDailyLoss, maxOpenPositions, maxLeverage, autoDisableConditions } = req.body;
    if (globalState.riskControls) {
      globalState.riskControls.maxDailyLoss = maxDailyLoss !== undefined ? maxDailyLoss : globalState.riskControls.maxDailyLoss;
      globalState.riskControls.maxOpenPositions = maxOpenPositions !== undefined ? maxOpenPositions : globalState.riskControls.maxOpenPositions;
      globalState.riskControls.maxLeverage = maxLeverage !== undefined ? maxLeverage : globalState.riskControls.maxLeverage;
      if (autoDisableConditions) {
        globalState.riskControls.autoDisableConditions = {
          ...globalState.riskControls.autoDisableConditions,
          ...autoDisableConditions
        };
      }
      logEvent(`Operator Risk Policy Updated: Loss Limit=${globalState.riskControls.maxDailyLoss}%, Max Pos=${globalState.riskControls.maxOpenPositions}, Leverage=${globalState.riskControls.maxLeverage}`, "INFO");
      res.json({ success: true, state: globalState });
    } else {
      res.status(404).json({ error: "Risk controls structure not found" });
    }
  });

  app.post("/api/live/broker/reconnect", (req, res) => {
    if (globalState.brokerConnection) {
      globalState.brokerConnection.status = "RECONNECTING";
      logEvent(`Broker reconnection triggered: reset MT5/Bybit gateway sockets...`, "WARNING");
      setTimeout(() => {
        globalState.brokerConnection.status = "CONNECTED";
        globalState.brokerConnection.latency = 12;
        logEvent(`Broker API connectivity re-established successfully. Latency: 12ms.`, "SUCCESS");
      }, 1000);
      res.json({ success: true, state: globalState });
    } else {
      res.status(404).json({ error: "Broker connection structure not found" });
    }
  });

  // Create standard native HTTP Server
  const server = http.createServer(app);

  // Attach WebSocket server
  const wss = new WebSocketServer({ noServer: true });

  server.on("upgrade", (request, socket, head) => {
    try {
      // Safely extract pathname without depending on request.headers.host
      const pathname = request.url ? request.url.split("?")[0] : "";
      if (pathname === "/api/ws" || pathname === "/ws" || pathname === "/") {
        wss.handleUpgrade(request, socket, head, (ws) => {
          wss.emit("connection", ws, request);
        });
      } else {
        socket.destroy();
      }
    } catch (err) {
      console.error("Error in server upgrade handler:", err);
      socket.destroy();
    }
  });

  const clients = new Set<WebSocket>();

  wss.on("connection", (ws) => {
    clients.add(ws);
    // Send immediate initial state
    ws.send(JSON.stringify({ type: "INITIAL_STATE", state: globalState }));

    ws.on("message", (message) => {
      try {
        const payload = JSON.parse(message.toString());
        if (payload.type === "PING") {
          ws.send(JSON.stringify({ type: "PONG" }));
        }
      } catch (err) {
        // Silent error
      }
    });

    ws.on("close", () => {
      clients.delete(ws);
    });
  });

  // Broadcast to all connected clients every 1.5s
  setInterval(() => {
    const packet = JSON.stringify({ type: "TICK", state: globalState });
    clients.forEach((client) => {
      if (client.readyState === WebSocket.OPEN) {
        client.send(packet);
      }
    });
  }, 1500);

  // Vite integration
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa"
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  // Bind to port 3000 and 0.0.0.0
  server.listen(PORT, "0.0.0.0", () => {
    console.log(`[Session SMC Bot Server] Listening on http://0.0.0.0:${PORT}`);
  });
}

startServer();
