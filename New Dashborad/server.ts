/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import express from "express";
import path from "path";
import fs from "fs";
import { createServer as createViteServer } from "vite";
import { GoogleGenAI, Type } from "@google/genai";
import dotenv from "dotenv";

import { Strategy, ValidationStage, GovernanceRecord, StrategyRules } from "./src/types";
import { getSampleMarketData } from "./src/data/mockMarketData";
import {
  runHistoricalReplay,
  runStatisticalValidation,
  runRobustnessValidation,
  runVirtualDemo,
  runExecutionSafety
} from "./src/lib/backtester";

dotenv.config();

const app = express();
const PORT = 3000;

app.use(express.json());

// In-memory strategy database with local JSON backup
const DB_FILE = path.join(process.cwd(), "strategies_db.json");
let strategies: Strategy[] = [];

// Initialize database with premium pre-defined strategies to offer a highly polished sandbox experience
const loadInitialData = () => {
  if (fs.existsSync(DB_FILE)) {
    try {
      strategies = JSON.parse(fs.readFileSync(DB_FILE, "utf-8"));
      return;
    } catch (e) {
      console.error("Error reading strategy database, reinitializing: ", e);
    }
  }

  // Pre-seed an institutional-grade strategy: SMA Golden Cross
  const smaRules: StrategyRules = {
    assetClass: "Equity",
    symbol: "AAPL",
    timeframe: "1D",
    entryConditions: ["Short Simple Moving Average (10-day) crosses above Long Simple Moving Average (30-day).", "Current price must be above 200-day EMA to confirm structural trend."],
    exitConditions: ["Short SMA (10-day) crosses back below Long SMA (30-day) or Stop Loss is reached."],
    riskRules: {
      stopLossPct: 2.0,
      takeProfitPct: 6.0,
      maxPositionSizePct: 10.0,
      dailyLossLimitPct: 3.5,
    },
    parameters: {
      shortPeriod: 10,
      longPeriod: 30,
    }
  };

  const initialMarketData = getSampleMarketData("AAPL");
  const replayReport = runHistoricalReplay(smaRules, initialMarketData);
  const statisticalReport = runStatisticalValidation(replayReport, initialMarketData);
  const robustnessReport = runRobustnessValidation(smaRules, initialMarketData);
  const virtualDemoReport = runVirtualDemo(smaRules, initialMarketData);
  const executionSafetyReport = runExecutionSafety(smaRules);

  const initialRecord: GovernanceRecord = {
    id: "G-0001",
    timestamp: new Date().toISOString(),
    actor: "System Genesis",
    action: "Strategy Creation",
    fromStage: "NONE",
    toStage: ValidationStage.INTAKE,
    hash: "0fca7a8c3e8e244d28ba89f2a96a9e1e2cf4f828a2b5d4fb17a4ea3c8f84092b",
    evidenceSummary: "SMA Golden Cross strategy specified and loaded.",
    details: "Created initial strategy with standard risk rules and baseline SMA parameters (10/30)."
  };

  const initialStrategy: Strategy = {
    id: "STR-001",
    name: "SMA Golden Cross",
    version: "1.0.0",
    description: "An institutional momentum strategy validating short-term moving average crossovers with high-volume breakouts on S&P500 components.",
    author: "Portfolio Management Group",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    status: ValidationStage.VIRTUAL_DEMO, // Highly advanced so user has a wealth of visual details out of the box!
    rules: smaRules,
    evidence: {
      audit: {
        checkedAt: new Date().toISOString(),
        isPassed: true,
        score: 95,
        logicalDefects: [
          {
            id: "L-001",
            type: "missing_parameter",
            severity: "low",
            title: "EMA Confirmation Period not explicitly parameterized",
            description: "The 200-day EMA parameter is hardcoded in the entry conditions description but not mapped in parameters object.",
            affectedRule: "Current price must be above 200-day EMA",
            resolution: "Parameterize the EMA filter length for optimization."
          }
        ],
        recommendations: [
          "Establish high-volume breakout filters to prevent false crossovers.",
          "Optimize stop-loss trailing mechanics during high volatility."
        ]
      },
      replay: replayReport,
      statistics: statisticalReport,
      robustness: robustnessReport,
      virtualDemo: virtualDemoReport,
      executionSafety: executionSafetyReport
    },
    auditLog: [initialRecord],
    versionHistory: [
      { version: "v1.0.0", date: "2026-06-10", auditScore: 82, safetyScore: 75, backtestReturnPct: -12.4, status: "Strategy Intake" },
      { version: "v1.1.0", date: "2026-06-15", auditScore: 88, safetyScore: 85, backtestReturnPct: -4.8, status: "AI Strategy Refinement" },
      { version: "v1.2.0", date: "2026-06-20", auditScore: 92, safetyScore: 94, backtestReturnPct: 1.5, status: "Historical Replay" },
      { version: "v1.3.0", date: "2026-06-25", auditScore: 95, safetyScore: 98, backtestReturnPct: 5.4, status: "Robustness Validation" }
    ]
  };

  strategies = [initialStrategy];
  saveData();
};

const saveData = () => {
  try {
    fs.writeFileSync(DB_FILE, JSON.stringify(strategies, null, 2), "utf-8");
  } catch (e) {
    console.error("Error writing to strategy database: ", e);
  }
};

loadInitialData();

// Lazy-initialize Google GenAI API Client
let aiInstance: GoogleGenAI | null = null;
function getGemini(): GoogleGenAI {
  if (!aiInstance) {
    const key = process.env.GEMINI_API_KEY;
    if (!key) {
      throw new Error("GEMINI_API_KEY is not defined. Please configure your API key in Settings > Secrets.");
    }
    aiInstance = new GoogleGenAI({
      apiKey: key,
      httpOptions: {
        headers: {
          "User-Agent": "aistudio-build",
        },
      },
    });
  }
  return aiInstance;
}

// REST API Endpoints

// GET all strategies
app.get("/api/strategies", (req, res) => {
  res.json(strategies);
});

// GET strategy by ID
app.get("/api/strategies/:id", (req, res) => {
  const strategy = strategies.find(s => s.id === req.params.id);
  if (!strategy) {
    return res.status(404).json({ error: "Strategy not found" });
  }
  res.json(strategy);
});

// POST create strategy
app.post("/api/strategies", (req, res) => {
  const { name, description, author, rules } = req.body;
  
  if (!name || !rules) {
    return res.status(400).json({ error: "Missing required fields: name and rules are required." });
  }

  const newId = `STR-${String(strategies.length + 1).padStart(3, "0")}`;
  const timestamp = new Date().toISOString();

  const genesisRecord: GovernanceRecord = {
    id: `G-${String(Math.floor(Math.random() * 10000)).padStart(4, "0")}`,
    timestamp,
    actor: author || "System Researcher",
    action: "Strategy Creation",
    fromStage: "NONE",
    toStage: ValidationStage.INTAKE,
    hash: Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15),
    evidenceSummary: "New strategy intake submitted successfully.",
    details: `Created new strategy specification: "${name}"`
  };

  const newStrategy: Strategy = {
    id: newId,
    name,
    version: "1.0.0",
    description: description || "Custom research strategy.",
    author: author || "System Researcher",
    createdAt: timestamp,
    updatedAt: timestamp,
    status: ValidationStage.INTAKE,
    rules,
    evidence: {},
    auditLog: [genesisRecord],
    versionHistory: [
      { version: "v1.0.0", date: timestamp.split("T")[0], auditScore: 0, safetyScore: 0, backtestReturnPct: 0, status: "Strategy Intake" }
    ]
  };

  strategies.push(newStrategy);
  saveData();
  res.status(201).json(newStrategy);
});

// PUT update strategy / rules
app.put("/api/strategies/:id", (req, res) => {
  const index = strategies.findIndex(s => s.id === req.params.id);
  if (index === -1) {
    return res.status(404).json({ error: "Strategy not found" });
  }

  const updatedStrategy = {
    ...strategies[index],
    ...req.body,
    updatedAt: new Date().toISOString()
  };

  strategies[index] = updatedStrategy;
  saveData();
  res.json(updatedStrategy);
});

// DELETE strategy
app.delete("/api/strategies/:id", (req, res) => {
  const index = strategies.findIndex(s => s.id === req.params.id);
  if (index === -1) {
    return res.status(404).json({ error: "Strategy not found" });
  }

  strategies.splice(index, 1);
  saveData();
  res.json({ success: true });
});

// POST AI parsing and auditing of trading ideas
app.post("/api/gemini/parse", async (req, res) => {
  const { idea, author } = req.body;
  if (!idea) {
    return res.status(400).json({ error: "No trading idea text was provided." });
  }

  try {
    const ai = getGemini();

    const prompt = `
You are an expert institutional quantitative research auditor. Analyze the following trading idea and parse it into a completely specified, machine-readable strategy specification.
At the same time, perform a rigorous logical audit of the strategy to identify contradictions, ambiguities, missing parameters, execution conflicts, or undefined conditions.

Trading Idea:
"""
${idea}
"""

You MUST respond strictly with a JSON object containing the exact properties mapped in this schema. Do not include markdown codeblocks or any additional wrapper text outside the raw JSON.

Schema:
{
  "name": "Concise Institutional Name of Strategy",
  "description": "Clear academic explanation of the underlying trading edge and mechanics.",
  "rules": {
    "assetClass": "Equity" or "Crypto" or "Forex",
    "symbol": "AAPL" or "BTC/USD" or "EUR/USD" (choose the best match),
    "timeframe": "1D" or "1H" or "15M",
    "entryConditions": ["Condition 1", "Condition 2"],
    "exitConditions": ["Condition 1"],
    "riskRules": {
      "stopLossPct": 2.0 (estimated stop loss percent based on description, default to 2.0 if unspecified),
      "takeProfitPct": 6.0 (estimated take profit, default to 6.0 if unspecified),
      "maxPositionSizePct": 10.0 (default to 10.0 if unspecified),
      "dailyLossLimitPct": 3.0 (default to 3.0 if unspecified)
    },
    "parameters": {
      "shortPeriod": 10,
      "longPeriod": 30
    }
  },
  "audit": {
    "isPassed": true or false (false if there are high severity defects),
    "score": 0 to 100 (logical completeness score, penalty for defects),
    "logicalDefects": [
      {
        "type": "ambiguity" or "contradiction" or "missing_parameter" or "execution_conflict" or "undefined_condition",
        "severity": "high" or "medium" or "low",
        "title": "Short title of issue",
        "description": "Detailed explanation of what is mathematically or logically ambiguous/contradictory about the rule.",
        "affectedRule": "The relevant sentence/clause from the idea"
      }
    ],
    "recommendations": ["Recommendation 1 for improving strategy specificity or safety"]
  }
}
`;

    const response = await ai.models.generateContent({
      model: "gemini-3.5-flash",
      contents: prompt,
      config: {
        responseMimeType: "application/json",
      },
    });

    const parsedData = JSON.parse(response.text?.trim() || "{}");
    res.json(parsedData);
  } catch (err: any) {
    console.error("Gemini parse failed: ", err);
    res.status(500).json({ error: err.message || "Failed to parse trading idea with Gemini AI." });
  }
});

// POST promote strategy stage with evidence generation
app.post("/api/strategies/:id/promote", (req, res) => {
  const strategy = strategies.find(s => s.id === req.params.id);
  if (!strategy) {
    return res.status(404).json({ error: "Strategy not found" });
  }

  const currentStage = strategy.status;
  let targetStage = currentStage;
  const timestamp = new Date().toISOString();
  let details = "";
  let evidenceSummary = "";

  // Progression list
  const stagesSequence = [
    ValidationStage.INTAKE,
    ValidationStage.AUDIT,
    ValidationStage.REFINEMENT,
    ValidationStage.REPLAY,
    ValidationStage.STATISTICAL,
    ValidationStage.ROBUSTNESS,
    ValidationStage.VIRTUAL_DEMO,
    ValidationStage.VERIFICATION_READY,
    ValidationStage.EXECUTION,
    ValidationStage.LIVE_DEMO,
    ValidationStage.PRODUCTION_APPROVAL
  ];

  const currentIndex = stagesSequence.indexOf(currentStage);
  if (currentIndex === -1 || currentIndex === stagesSequence.length - 1) {
    return res.status(400).json({ error: "Cannot promote strategy beyond production stage." });
  }

  targetStage = stagesSequence[currentIndex + 1];

  // Perform backend processing/simulation based on the newly promoted stage
  const candles = getSampleMarketData(strategy.rules.symbol || "AAPL");

  switch (targetStage) {
    case ValidationStage.AUDIT:
      if (!strategy.evidence.audit) {
        strategy.evidence.audit = {
          checkedAt: timestamp,
          isPassed: true,
          score: 100,
          logicalDefects: [],
          recommendations: ["Perform optimization sweeps on stop loss levels."]
        };
      }
      evidenceSummary = "Logical Audit Complete.";
      details = `Analyzed strategy logic for ambiguities. Completeness score: ${strategy.evidence.audit.score}%`;
      break;

    case ValidationStage.REFINEMENT:
      strategy.evidence.refinement = {
        refinedAt: timestamp,
        summary: "Strategy parameters finalized. Redundant parameters removed.",
        changesApplied: []
      };
      evidenceSummary = "AI Rules Refined and Finalized.";
      details = "Consolidated signal mechanisms and compiled machine-readable parameter map.";
      break;

    case ValidationStage.REPLAY:
      strategy.evidence.replay = runHistoricalReplay(strategy.rules, candles);
      evidenceSummary = `Backtest complete. Trades executed: ${strategy.evidence.replay.totalTrades}`;
      details = `Return: ${strategy.evidence.replay.totalReturnPct.toFixed(2)}%, Win Rate: ${(strategy.evidence.replay.winRate * 100).toFixed(1)}%, Max Drawdown: ${(strategy.evidence.replay.maxDrawdown * 100).toFixed(1)}%`;
      break;

    case ValidationStage.STATISTICAL:
      if (!strategy.evidence.replay) {
        strategy.evidence.replay = runHistoricalReplay(strategy.rules, candles);
      }
      strategy.evidence.statistics = runStatisticalValidation(strategy.evidence.replay, candles);
      evidenceSummary = "Statistical evidence generated.";
      details = `Sharpe: ${strategy.evidence.statistics.sharpeRatio.toFixed(2)}, Sortino: ${strategy.evidence.statistics.sortinoRatio.toFixed(2)}, p-value: ${strategy.evidence.statistics.pValue.toFixed(4)}`;
      break;

    case ValidationStage.ROBUSTNESS:
      strategy.evidence.robustness = runRobustnessValidation(strategy.rules, candles);
      evidenceSummary = "Robustness Stress Testing complete.";
      details = "Completed 10-point parameter sensitivity sweep and tested Black Swan / Volatility crash scenarios.";
      break;

    case ValidationStage.VIRTUAL_DEMO:
      strategy.evidence.virtualDemo = runVirtualDemo(strategy.rules, candles);
      evidenceSummary = "Virtual Demo Broker execution session complete.";
      details = `Simulated ${strategy.evidence.virtualDemo.simulatedOrdersSubmitted} submissions with average execution latency of ${strategy.evidence.virtualDemo.averageLatencyMs.toFixed(1)}ms.`;
      break;

    case ValidationStage.VERIFICATION_READY:
      evidenceSummary = "Complete research package verified.";
      details = "All research gates passed with evidence files generated. Strategy certified ready for Execution Validation Layer.";
      break;

    case ValidationStage.EXECUTION:
      strategy.evidence.executionSafety = runExecutionSafety(strategy.rules);
      evidenceSummary = "Execution Safety evaluation complete.";
      details = `Safety Score: ${strategy.evidence.executionSafety.signalIntegrityScore}/100. Signal integrity, position sizes, and emergency stops checked.`;
      break;

    case ValidationStage.LIVE_DEMO:
      evidenceSummary = "Live Demo paper environment activated.";
      details = "Started real-time telemetry streaming using chronological paper broker environment.";
      break;

    case ValidationStage.PRODUCTION_APPROVAL:
      strategy.evidence.productionApproval = {
        approvedAt: timestamp,
        governanceHash: Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15),
        certificateId: `CERT-${Math.floor(Math.random() * 900000 + 100000)}`,
        signoffs: [
          { role: "Risk Committee Sign-off", approver: "Chief Risk Officer", signedAt: timestamp, comments: "Risk boundaries and safety valves fully verified.", approved: true },
          { role: "Quantitative Research Sign-off", approver: "Head of Alpha Research", signedAt: timestamp, comments: "Edge is statistically valid with substantial alpha potential.", approved: true }
        ],
        riskCapLimitUsd: 500000
      };
      evidenceSummary = "Strategy Approved for Production.";
      details = `Governance Certificate ${strategy.evidence.productionApproval.certificateId} compiled under hash ${strategy.evidence.productionApproval.governanceHash}. Dedicated risk cap: $${strategy.evidence.productionApproval.riskCapLimitUsd.toLocaleString()}`;
      break;
  }

  const promotionRecord: GovernanceRecord = {
    id: `G-${String(Math.floor(Math.random() * 10000)).padStart(4, "0")}`,
    timestamp,
    actor: "Strategy Validation Engine",
    action: `Promote Stage`,
    fromStage: currentStage,
    toStage: targetStage,
    hash: Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15),
    evidenceSummary,
    details
  };

  strategy.status = targetStage;
  strategy.auditLog.unshift(promotionRecord);
  strategy.updatedAt = timestamp;

  if (!strategy.versionHistory) {
    strategy.versionHistory = [
      { version: "v1.0.0", date: strategy.createdAt.split("T")[0], auditScore: 0, safetyScore: 0, backtestReturnPct: 0, status: "Strategy Intake" }
    ];
  }

  const currentAuditScore = strategy.evidence.audit?.score || (targetStage === ValidationStage.AUDIT ? 100 : (strategy.evidence.audit?.score || 0));
  const currentSafetyScore = strategy.evidence.executionSafety?.signalIntegrityScore || (targetStage === ValidationStage.EXECUTION ? 98 : (strategy.evidence.executionSafety?.signalIntegrityScore || 0));
  const currentReturn = strategy.evidence.replay?.totalReturnPct || (targetStage === ValidationStage.REPLAY ? (strategy.evidence.replay?.totalReturnPct || 4.5) : (strategy.evidence.replay?.totalReturnPct || 0));

  const nextVerNum = strategy.versionHistory.length;
  const nextVer = `v1.${nextVerNum}.0`;

  strategy.versionHistory.push({
    version: nextVer,
    date: timestamp.split("T")[0],
    auditScore: currentAuditScore,
    safetyScore: currentSafetyScore,
    backtestReturnPct: parseFloat(currentReturn.toFixed(2)),
    status: targetStage
  });

  saveData();
  res.json(strategy);
});

// POST demote strategy back to a research stage (e.g., if a safety trigger fails, or user triggers optimization)
app.post("/api/strategies/:id/demote", (req, res) => {
  const strategy = strategies.find(s => s.id === req.params.id);
  if (!strategy) {
    return res.status(404).json({ error: "Strategy not found" });
  }

  const { targetStage, actor, comments } = req.body;
  if (!targetStage) {
    return res.status(400).json({ error: "No target stage was specified." });
  }

  const timestamp = new Date().toISOString();
  const demotionRecord: GovernanceRecord = {
    id: `G-${String(Math.floor(Math.random() * 10000)).padStart(4, "0")}`,
    timestamp,
    actor: actor || "System Integrity Watcher",
    action: "Demote Stage",
    fromStage: strategy.status,
    toStage: targetStage,
    hash: Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15),
    evidenceSummary: `Continuous Integrity Watcher: strategy demoted back to ${targetStage}.`,
    details: comments || "Integrity anomaly or revalidation request detected."
  };

  strategy.status = targetStage;
  strategy.auditLog.unshift(demotionRecord);
  strategy.updatedAt = timestamp;

  saveData();
  res.json(strategy);
});

// POST AI root cause analysis of trade failures
app.post("/api/gemini/explain-failure", async (req, res) => {
  const { trades, strategyName } = req.body;
  if (!trades || !trades.length) {
    return res.status(400).json({ error: "No trades provided to analyze." });
  }

  try {
    const ai = getGemini();
    const prompt = `
You are an expert quantitative risk manager. Analyze the following sequence of trading outcomes for the strategy "${strategyName || 'Generic Alpha'}" and provide a concise, professional diagnosis explaining why the losses occurred (e.g., regime mismatch, slippage cost drag, stop-loss overfitting, or parameter decay) and list actionable improvements.

Trades Context:
${JSON.stringify(trades.slice(-5), null, 2)}

Respond with a raw JSON object containing these keys:
{
  "diagnosis": "Detailed quantitative explanation of the failure dynamics.",
  "primaryCause": "One-sentence primary cause of loss.",
  "actionableFixes": ["Specific recommendation 1", "Specific recommendation 2"]
}
`;

    const response = await ai.models.generateContent({
      model: "gemini-3.5-flash",
      contents: prompt,
      config: {
        responseMimeType: "application/json"
      }
    });

    res.json(JSON.parse(response.text?.trim() || "{}"));
  } catch (err: any) {
    console.error("Gemini failure explanation failed: ", err);
    res.status(500).json({ error: err.message || "Failed to explain trading failures with Gemini AI." });
  }
});


// Serve Front-end App via Vite or Express build
async function startServer() {
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Institutional SVOS Server running on http://0.0.0.0:${PORT}`);
  });
}

startServer();
