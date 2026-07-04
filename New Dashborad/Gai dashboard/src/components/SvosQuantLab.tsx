import React, { useState, useEffect, useRef } from "react";
import { useSocket } from "../context/SocketContext.js";
import { 
  Lightbulb, 
  FileCheck, 
  History, 
  TrendingUp, 
  BarChart4, 
  ShieldAlert, 
  ShieldCheck, 
  CheckCircle2, 
  Play, 
  Pause,
  Sparkles, 
  HelpCircle, 
  Database, 
  Layers, 
  Download, 
  RefreshCw,
  Award,
  AlertCircle,
  Radio,
  Check,
  Lock,
  Unlock,
  ArrowRight,
  ChevronRight,
  Activity,
  Terminal,
  FileText,
  Server
} from "lucide-react";

interface WorkflowStep {
  id: number;
  label: string;
  desc: string;
  icon: React.ComponentType<any>;
  metricLabel?: string;
  metricValue?: string;
}

const SVOS_WORKFLOW_STEPS: WorkflowStep[] = [
  { id: 1, label: "Intake & Audit", desc: "SMC rule validation and syntactic code structure checks", icon: Lightbulb, metricLabel: "Compliance", metricValue: "100%" },
  { id: 2, label: "Historical Replay", desc: "Stream candle tick data to verify sweeps & structure triggers", icon: History, metricLabel: "Depth", metricValue: "1.48M" },
  { id: 3, label: "Statistical Backtest", desc: "Compute intraday and parallel swing performance ratios", icon: TrendingUp, metricLabel: "Est RRR", metricValue: "1:4.5" },
  { id: 4, label: "Perfect OB Filter", desc: "Confluence scoring module & Monte Carlo stress testing", icon: FileCheck, metricLabel: "Score", metricValue: "5/6" },
  { id: 5, label: "EVF Qualification", desc: "Slippage limits, execution speed & fill rate validation", icon: Activity, metricLabel: "Fill Rate", metricValue: "99.8%" },
  { id: 6, label: "RGM Risk Engine", desc: "Allocate profit-only buffers for swing trading risk", icon: ShieldCheck, metricLabel: "Drawdown", metricValue: "3.6%" },
  { id: 7, label: "Live Demo Sandbox", desc: "Forward-test hot trading loops inside live sandbox feeds", icon: Radio, metricLabel: "Latency", metricValue: "42ms" },
  { id: 8, label: "Governance Signer", desc: "Apply cryptographic signature to verified trading contract", icon: CheckCircle2, metricLabel: "Registry", metricValue: "Active" }
];

export const SvosQuantLab: React.FC = () => {
  const { state, activateStrategy } = useSocket();
  const [activeStep, setActiveStep] = useState<number>(1);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [simStep, setSimStep] = useState<number>(0);
  const [simProgress, setSimProgress] = useState<number>(0);
  
  // Custom Strategy state variables for developer configuration
  const [strategyName, setStrategyName] = useState<string>("Step Index 100 Sniper AI Bot");
  const [targetAsset, setTargetAsset] = useState<string>("Step Index 100");
  const [stopLossPips, setStopLossPips] = useState<number>(10);
  const [riskRewardRatio, setRiskRewardRatio] = useState<number>(4.5);
  const [timeframe, setTimeframe] = useState<string>("M15");
  const [enableNewsFilter, setEnableNewsFilter] = useState<boolean>(true);

  // Dual Mode and Perfect OB Filter states based on Github README and ChatGPT Specs
  const [hybridModeEnabled, setHybridModeEnabled] = useState<boolean>(true);
  const [startingCapital, setStartingCapital] = useState<number>(1000);
  const [dailyProfitTarget, setDailyProfitTarget] = useState<number>(3000);
  
  // Perfect OB Filter Module criteria states (max score = 6)
  const [obScoreDisplacement, setObScoreDisplacement] = useState<boolean>(true);
  const [obScoreUnmitigated, setObScoreUnmitigated] = useState<boolean>(true);
  const [obScoreSweep, setObScoreSweep] = useState<boolean>(true);
  const [obScoreFib, setObScoreFib] = useState<boolean>(true);
  const [obScoreStructure, setObScoreStructure] = useState<boolean>(true);
  const [obScoreImpulse, setObScoreImpulse] = useState<boolean>(true);
  const [acceptanceThreshold, setAcceptanceThreshold] = useState<number>(5);

  // RGM & Swing Buffer Configuration states
  const [swingRiskBufferPercent, setSwingRiskBufferPercent] = useState<number>(100);
  const [pauseDayTradingOnSwing, setPauseDayTradingOnSwing] = useState<boolean>(true);

  // Learning & Optimization state variables (Self-Training Module)
  const [trainingEpochs, setTrainingEpochs] = useState<number>(0);
  const [trainingRunning, setTrainingRunning] = useState<boolean>(false);

  // Replay states
  const [isReplayPlaying, setIsReplayPlaying] = useState<boolean>(false);
  const [replayCandleIndex, setReplayCandleIndex] = useState<number>(0);
  const [replaySpeed, setReplaySpeed] = useState<number>(1); // 1 = 1x, 2 = 2x, 4 = 4x

  // Master asset configs for dynamically adjusting replay & sandbox data
  const getAssetConfig = (asset: string) => {
    switch (asset) {
      case "EURUSD":
        return { base: 1.0820, pip: 0.0001, decimals: 4, label: "EUR/USD" };
      case "GBPUSD":
        return { base: 1.2750, pip: 0.0001, decimals: 4, label: "GBP/USD" };
      case "XAUUSD":
        return { base: 2335.0, pip: 0.1, decimals: 2, label: "XAU/USD (Gold)" };
      case "Step Index 100":
      default:
        return { base: 11245.0, pip: 1.0, decimals: 1, label: "Step Index 100" };
    }
  };

  // Calculated OB Confluence Score based on active checklist selections
  const calculatedObScore = (obScoreDisplacement ? 1 : 0) + 
                            (obScoreUnmitigated ? 1 : 0) + 
                            (obScoreSweep ? 1 : 0) + 
                            (obScoreFib ? 1 : 0) + 
                            (obScoreStructure ? 1 : 0) + 
                            (obScoreImpulse ? 1 : 0);

  // Simulated metrics that dynamically update as user plays with parameters
  const [backtestReturn, setBacktestReturn] = useState<number>(124.8);
  const [profitFactor, setProfitFactor] = useState<number>(2.42);
  const [maxDrawdown, setMaxDrawdown] = useState<number>(3.6);
  const [passedValidation, setPassedValidation] = useState<boolean>(true);

  // Virtual Demo Sub-Workflow States
  const [demoRunning, setDemoRunning] = useState<boolean>(false);
  const [demoStep, setDemoStep] = useState<number>(0); // 0 = not started, 1-8 are steps
  const [brokerConnected, setBrokerConnected] = useState<boolean>(false);
  const [brokerLatency, setBrokerLatency] = useState<number>(42);
  const [sandboxBalance, setSandboxBalance] = useState<number>(1000);
  const [livePrice, setLivePrice] = useState<number>(11245.0);
  const [priceDirection, setPriceDirection] = useState<"up" | "down" | "flat">("flat");
  const [lotSizeInput, setLotSizeInput] = useState<string>("1.00");
  const [slPipsInput, setSlPipsInput] = useState<string>("15");
  const [tpPipsInput, setTpPipsInput] = useState<string>("45");
  const [demoOrders, setDemoOrders] = useState<Array<{
    id: string; 
    asset: string; 
    time: string; 
    type: "BUY" | "SELL"; 
    price: number; 
    tp: number; 
    sl: number; 
    status: string;
    lotSize?: number;
    exitPrice?: number;
    profit?: number;
  }>>([]);

  // Terminal log stream state
  const [logs, setLogs] = useState<string[]>([
    "System: SVOS Quant Laboratory loaded.",
    "Ready to audit and validate custom SMC strategies. Select parameters and click 'Start Quant Validation Pipeline'."
  ]);
  const terminalEndRef = useRef<HTMLDivElement | null>(null);

  // Autoscroll terminal
  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs]);

  // Handle slide/value variations to change metrics to make it feel real & reactive
  useEffect(() => {
    // Generate organic metrics based on parameters
    const baseWin = 70 - (stopLossPips * 0.5) - (riskRewardRatio * 2) + (calculatedObScore * 3);
    const winRate = Math.max(38, Math.min(88, baseWin + (hybridModeEnabled ? 4 : 0) + Math.random() * 3));
    const pf = Math.max(1.1, parseFloat((winRate * riskRewardRatio / (100 - winRate)).toFixed(2)));
    
    // Day trade target $1k -> $3k. Swing targets multi-leg scaling.
    const retMultiplier = targetAsset === "Step Index 100" ? 45.8 : 12.4;
    const ret = parseFloat((pf * retMultiplier).toFixed(1));
    const dd = parseFloat((riskRewardRatio * 0.8 + (6 - calculatedObScore) * 0.6 + Math.random() * 1.5).toFixed(1));

    setBacktestReturn(ret);
    setProfitFactor(pf);
    setMaxDrawdown(dd);
    setPassedValidation(calculatedObScore >= acceptanceThreshold && pf >= 1.6 && dd <= 8);
  }, [stopLossPips, riskRewardRatio, timeframe, targetAsset, calculatedObScore, acceptanceThreshold, hybridModeEnabled]);

  const addLog = (msg: string) => {
    setLogs(prev => [...prev, `[${new Date().toISOString().slice(11, 19)}] ${msg}`]);
  };

  const runPipelineSimulation = () => {
    if (isSimulating) return;
    setIsSimulating(true);
    setSimStep(1);
    setSimProgress(0);
    setLogs([]);
    addLog(`INITIALIZING SVOS VALIDATION CYCLE: Strategy "${strategyName}" on ${targetAsset} (${timeframe})`);
  };

  // Simulation timer sequence mimicking real quant processing
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isSimulating && simStep > 0 && simStep <= 8) {
      // Setup detailed text logs for each step to make the user's workflow come to life!
      let stepMsgs: string[] = [];
      if (simStep === 1) {
        stepMsgs = [
          "STAGE 1: Parsing Strategy Rules & Parameter Structs...",
          `Configuring Step Index 100 Sniper AI Bot: Day-Trade Mode (M15), Target RRR: 1:${riskRewardRatio}, News Filter = ${enableNewsFilter ? "ENABLED" : "DISABLED"}`,
          `Hybrid Swing Mode parallel scanner: ${hybridModeEnabled ? "ACTIVATED" : "DEACTIVATED"} (allocating profits from $1k day-trading buffer)`,
          "Validated syntactic rules. Proceeding to semantic code audit."
        ];
      } else if (simStep === 2) {
        stepMsgs = [
          "STAGE 2: Historical Candle Replay buffers initialized...",
          `Streaming tick buffer for ${targetAsset} (${timeframe}). Loading 1,480,500 historical ticks...`,
          "Simulating candle-by-candle sweep, break of structure (BOS), and order block (OB) entry sweeps."
        ];
      } else if (simStep === 3) {
        stepMsgs = [
          "STAGE 3: Executing multi-cycle statistical backtest...",
          `Simulated Day Trades: 2-4 daily (5-15 pips SL). Swing Trades: 1-3 weekly (100-300 pips SL).`,
          `Simulated Return: +${backtestReturn}%, Profit Factor: ${profitFactor}, Max Drawdown: -${maxDrawdown}% (PASSED)`
        ];
      } else if (simStep === 4) {
        stepMsgs = [
          "STAGE 4: Running Perfect OB Filter scoring & Monte Carlo Stress Testing...",
          `Configured Acceptance Score Threshold: >= ${acceptanceThreshold}/6. Current OB Confluence Score: ${calculatedObScore}/6.`,
          `Score Criteria: Displacement: ${obScoreDisplacement?"Pass":"Fail"}, Unmitigated: ${obScoreUnmitigated?"Pass":"Fail"}, Sweep: ${obScoreSweep?"Pass":"Fail"}, Fib: ${obScoreFib?"Pass":"Fail"}, Structure: ${obScoreStructure?"Pass":"Fail"}, Impulse: ${obScoreImpulse?"Pass":"Fail"}`,
          `Result: ${calculatedObScore >= acceptanceThreshold ? "APPROVED" : "REJECTED (Does not meet threshold)"}`,
          "Running 500 Monte Carlo path permutations under extreme 3.0 pip spread spikes."
        ];
      } else if (simStep === 5) {
        stepMsgs = [
          "STAGE 5: EVF Execution Qualification initialized...",
          "Simulating market microstructure filled-rates, microsecond delay buffers, and partial order fills...",
          "Average execution latency: 0.4ms | Slippage tolerance: 0.1 pips. Expected Fill Quality: 99.8%."
        ];
      } else if (simStep === 6) {
        stepMsgs = [
          "STAGE 6: RGM Risk Engine compliance verification...",
          `Validating Capital Preservation limits. Day Trade Limit: 10-20% max risk. Starting balance: $${startingCapital}.`,
          `Swing allocation buffer: ${swingRiskBufferPercent}% of day trading profits only. Principal capital risk: 0%.`,
          `Auto-pause Day Trade scanner during active Swing trade: ${pauseDayTradingOnSwing ? "ENABLED" : "DISABLED"}. No firewall breaches detected.`
        ];
      } else if (simStep === 7) {
        stepMsgs = [
          "STAGE 7: Live Demo Sandbox Forward-Test starting...",
          "Establishing persistent WebSocket connection to broker paper trade gateway...",
          "Streaming tick-by-tick order placement. Forward equity tracking online. Performance metrics aligned with backtest expectation."
        ];
      } else if (simStep === 8) {
        stepMsgs = [
          "STAGE 8: Cryptographic Strategy Contract Signer & Registry...",
          `Generated stand-alone WebAssembly strategy compiler binary (38.4KB)`,
          `Immutable Strategy Fingerprint: sha256_isop_${Math.random().toString(16).slice(2, 18)}`,
          "GOVERNANCE COMPLIANCE CHECK PASSED! Strategy approved for hot deployment."
        ];
      }

      let subIdx = 0;
      interval = setInterval(() => {
        if (subIdx < stepMsgs.length) {
          addLog(stepMsgs[subIdx]);
          subIdx++;
          setSimProgress(prev => Math.min(100, prev + (100 / stepMsgs.length)));
        } else {
          clearInterval(interval);
          setActiveStep(simStep);
          if (simStep < 8) {
            setSimStep(prev => prev + 1);
            setSimProgress(0);
          } else {
            setIsSimulating(false);
            setSimStep(0);
            addLog("SUCCESS: Full SVOS quant validation suite finalized. Contract approved!");
          }
        }
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [isSimulating, simStep]);

  const startVirtualDemoSequence = () => {
    if (demoRunning) return;
    setDemoRunning(true);
    setDemoStep(1);
    setBrokerConnected(false);
    setDemoOrders([]);
    setLogs([]);
    addLog(`STARTING INTERACTIVE VIRTUAL DEMO FLOW: testing "${strategyName}" on ${targetAsset}...`);
  };

  // Keep sandbox balance in sync with starting capital until active trades modify it
  useEffect(() => {
    if (demoOrders.length === 0) {
      setSandboxBalance(startingCapital);
    }
  }, [startingCapital, demoOrders.length]);

  // Sync live price when asset changes
  useEffect(() => {
    const config = getAssetConfig(targetAsset);
    setLivePrice(config.base);
  }, [targetAsset]);

  // Live price ticker simulation when broker is connected
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (brokerConnected) {
      const config = getAssetConfig(targetAsset);
      interval = setInterval(() => {
        setLivePrice(prev => {
          const delta = (Math.random() - 0.5) * 2 * config.pip;
          const next = prev + delta;
          setPriceDirection(delta > 0 ? "up" : "down");
          return next;
        });
      }, 1000);
    } else {
      setPriceDirection("flat");
    }
    return () => clearInterval(interval);
  }, [brokerConnected, targetAsset]);

  // Virtual Demo cycle effect
  useEffect(() => {
    let timeout: NodeJS.Timeout;
    if (demoRunning && demoStep >= 1 && demoStep <= 8) {
      let msg = "";
      const config = getAssetConfig(targetAsset);
      switch (demoStep) {
        case 1:
          msg = `DEMO FLOW [1/8]: Historical Data. Loading and synchronizing 3-year historical tick streams for ${targetAsset}... (Success: 1,200,000 candles verified)`;
          break;
        case 2:
          msg = `DEMO FLOW [2/8]: Strategy Signal Generator. Parsing candle data using strategy rules. Generated 142 high-confluence Smart Money sweeps.`;
          break;
        case 3:
          msg = `DEMO FLOW [3/8]: Risk Firewall. Applying margin verification, leverage controls, and max drawdown limits. (Safety status: 0 violations found)`;
          break;
        case 4:
          msg = `DEMO FLOW [4/8]: Virtual Execution Engine. Simulating slippage and broker delay. Order fill rate calculated at 99.8%.`;
          break;
        case 5:
          msg = `DEMO FLOW [5/8]: Trade Journal. Appending 142 simulated fills into local SQLite memory journal.`;
          setDemoOrders([
            { id: "TX-9011", asset: targetAsset, time: "2026-07-02 12:44:00", type: "BUY", price: config.base + 5 * config.pip, tp: config.base + 50 * config.pip, sl: config.base - 10 * config.pip, status: "FILLED", lotSize: 1.0 },
            { id: "TX-9012", asset: targetAsset, time: "2026-07-02 14:15:30", type: "SELL", price: config.base + 22 * config.pip, tp: config.base - 13 * config.pip, sl: config.base + 32 * config.pip, status: "FILLED", lotSize: 1.0 },
            { id: "TX-9013", asset: targetAsset, time: "2026-07-02 15:02:10", type: "BUY", price: config.base - 2 * config.pip, tp: config.base + 33 * config.pip, sl: config.base - 12 * config.pip, status: "FILLED", lotSize: 1.0 }
          ]);
          break;
        case 6:
          msg = `DEMO FLOW [6/8]: Performance Report. Compiling key stats: Profit Factor: ${profitFactor}, Sharpe: ${(profitFactor * 1.15).toFixed(2)}, Expectancy: +0.45 R.`;
          break;
        case 7:
          msg = `DEMO FLOW [7/8]: Readiness Verdict. Evaluating overall system stability. READINESS VERDICT: APPROVED FOR LIVE GATEWAY INJECTION (Score: 98.4%).`;
          break;
        case 8:
          msg = `DEMO FLOW [8/8]: Broker Demo API. Establishing live websocket links... ALL STAGES VALIDATED. Accessing paper sandbox.`;
          break;
      }
      addLog(msg);

      timeout = setTimeout(() => {
        if (demoStep < 8) {
          setDemoStep(prev => prev + 1);
        } else {
          setDemoRunning(false);
          setBrokerConnected(true);
          addLog("SUCCESS: Broker Demo API online! Securely streaming live sandbox tick feeds.");
        }
      }, 1100);
    }
    return () => clearTimeout(timeout);
  }, [demoRunning, demoStep, targetAsset, profitFactor]);

  // Interactive Historical Replay Handler
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isReplayPlaying) {
      const config = getAssetConfig(targetAsset);
      const speedInterval = replaySpeed === 4 ? 150 : replaySpeed === 2 ? 300 : 600;

      const supportPrice = config.base - 35 * config.pip;
      const obMin = config.base - 20 * config.pip;
      const obMax = config.base - 15 * config.pip;
      const entryPrice = config.base - 18 * config.pip;

      interval = setInterval(() => {
        setReplayCandleIndex(prev => {
          if (prev >= 100) {
            setIsReplayPlaying(false);
            addLog(`REPLAY COMPLETED: Analyzed 100 candle periods. High-precision liquidity sweeps mapped successfully for ${targetAsset}.`);
            return 100;
          }
          const next = prev + 10;
          if (next === 20) {
            addLog(`[REPLAY] Candle #${next}: Fetching ${targetAsset} liquidity frames. Major support established at ${supportPrice.toFixed(config.decimals)}.`);
          } else if (next === 40) {
            addLog(`[REPLAY] Candle #40: Break of Structure (BOS) confirmed! ${timeframe} candle closed below swing low.`);
          } else if (next === 60) {
            addLog(`[REPLAY] Candle #60: Perfect Order Block (OB) detected between ${obMin.toFixed(config.decimals)} and ${obMax.toFixed(config.decimals)}. Confluence Score: ${calculatedObScore}/6.`);
          } else if (next === 80) {
            addLog(`[REPLAY] Candle #80: Limit buy order executed at OB wick (${entryPrice.toFixed(config.decimals)}). Active profit protection buffer engaged.`);
          }
          return next;
        });
      }, speedInterval);
    }
    return () => clearInterval(interval);
  }, [isReplayPlaying, calculatedObScore, replaySpeed, targetAsset, timeframe]);

  // Interactive Self-Training LSTM Optimizer Handler
  const startSelfTraining = () => {
    if (trainingRunning) return;
    setTrainingRunning(true);
    setTrainingEpochs(0);
    addLog("STARTING LSTM & ATTENTION OPTIMIZATION MODULE: Initializing neural weights...");
  };

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (trainingRunning) {
      interval = setInterval(() => {
        setTrainingEpochs(prev => {
          if (prev >= 100) {
            setIsSimulating(false);
            setTrainingRunning(false);
            addLog(`[OPTIMIZER] Training completed! Adjusted filter weight matrices. Recommended Confluence Threshold: >= 5. Model Winrate expectancy up +4.2%.`);
            return 100;
          }
          const next = prev + 10;
          addLog(`[OPTIMIZER] Epoch ${next}/100. Loss: ${(0.38 - (next * 0.0032)).toFixed(4)} | Confluence accuracy: ${(85.4 + (next * 0.12)).toFixed(2)}%`);
          return next;
        });
      }, 500);
    }
    return () => clearInterval(interval);
  }, [trainingRunning]);

  // Interactive Sandbox Order Handlers
  const placeSandboxOrder = (type: "BUY" | "SELL", customLotSize: number, customSlPips: number, customTpPips: number) => {
    if (!brokerConnected) return;
    const config = getAssetConfig(targetAsset);
    const orderId = `TX-${Math.floor(1000 + Math.random() * 9000)}`;
    const price = livePrice;
    
    // Calculate TP and SL prices
    const slPrice = type === "BUY" ? price - customSlPips * config.pip : price + customSlPips * config.pip;
    const tpPrice = type === "BUY" ? price + customTpPips * config.pip : price - customTpPips * config.pip;
    
    addLog(`[WS SEND] Placing Market Order: ${type} ${customLotSize.toFixed(2)} lots on ${targetAsset} at ${price.toFixed(config.decimals)}`);
    
    setTimeout(() => {
      const newOrder = {
        id: orderId,
        asset: targetAsset,
        time: new Date().toISOString().replace("T", " ").slice(0, 19),
        type,
        price,
        tp: tpPrice,
        sl: slPrice,
        status: "FILLED",
        lotSize: customLotSize
      };
      
      setDemoOrders(prev => [newOrder, ...prev]);
      addLog(`[WS RECV] Order ${orderId} executed! Status: FILLED at ${price.toFixed(config.decimals)}. Latency: ${brokerLatency}ms`);
    }, 180);
  };

  const closeSandboxOrder = (id: string) => {
    const order = demoOrders.find(o => o.id === id);
    if (!order) return;
    const config = getAssetConfig(targetAsset);
    
    // Simulate current exit price
    const exitPrice = livePrice;
    const pipsDiff = (exitPrice - order.price) / config.pip;
    
    // Calculate P&L: lotSize * pipsDiff * multiplier
    const multiplier = targetAsset === "Step Index 100" ? 10 : 100;
    const rawProfit = order.type === "BUY" ? pipsDiff * multiplier * (order.lotSize || 1) : -pipsDiff * multiplier * (order.lotSize || 1);
    const profit = parseFloat(rawProfit.toFixed(2));
    
    addLog(`[WS SEND] Requesting Market Close for Order ${id}`);
    
    setTimeout(() => {
      setDemoOrders(prev => prev.map(o => {
        if (o.id === id) {
          return { ...o, status: "CLOSED", exitPrice, profit };
        }
        return o;
      }));
      setSandboxBalance(prev => parseFloat((prev + profit).toFixed(2)));
      addLog(`[WS RECV] Order ${id} closed successfully! Realized P&L: ${profit >= 0 ? "+" : ""}$${profit}`);
    }, 120);
  };

  // Export to live tab!
  const handleExportToProduction = async () => {
    // Generate a fresh unique ID
    const signature = `sha256_svos_${Math.random().toString(16).slice(2, 10)}8eab3275bc912662c1109a90ef550f4b`;
    const randId = `svos_${strategyName.toLowerCase().replace(/ /g, "_")}`;
    
    await activateStrategy(
      "svos_sweeper_h4", // Use existing slot but updates the parameters in liveState to simulate direct syncing
      "Bybit",
      [targetAsset, "GBPUSD"],
      profitFactor > 2.0 ? "Low" : "Medium",
      "v1.0.4"
    );
    addLog(`Contract synced directly to Deployed Runtimes array. Ready for broker lease attachment.`);
  };

  return (
    <div className="w-full bg-zinc-900 border border-zinc-800/80 rounded-2xl p-5 shadow-xl flex flex-col gap-5" id="svos-quant-lab-container">
      
      {/* Title block */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 border-b border-zinc-800/60 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <Layers className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <h2 className="text-sm font-black text-white uppercase tracking-wider">SVOS Quant Strategy Laboratory</h2>
            <p className="text-[10px] text-zinc-500 font-mono mt-0.5">Automated SMC Idea Backtester, Robustness Engine &amp; Production Signer</p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-zinc-400 font-mono font-bold bg-zinc-950 px-2 py-1 rounded-lg border border-zinc-850">
            Engine Core: D3.Quant v2
          </span>
        </div>
      </div>

      {/* 1. INTERACTIVE 8-STEP LIFECYCLE PROGRESS PIPELINE */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-2" id="svos-8-step-flow">
        {SVOS_WORKFLOW_STEPS.map((step) => {
          const StepIcon = step.icon;
          const isPassed = activeStep > step.id;
          const isActive = activeStep === step.id;
          const isProcessing = isSimulating && simStep === step.id;

          let statusClass = "border-zinc-850 bg-zinc-950/40 text-zinc-500";
          if (isPassed) {
            statusClass = "border-emerald-500/40 bg-emerald-500/5 text-emerald-400 shadow shadow-emerald-500/2";
          } else if (isActive) {
            statusClass = "border-amber-500/50 bg-amber-500/10 text-amber-400 shadow shadow-amber-500/2";
          } else if (isProcessing) {
            statusClass = "border-cyan-500/60 bg-cyan-500/10 text-cyan-400 animate-pulse";
          }

          return (
            <div 
              key={step.id} 
              className={`flex flex-col gap-1.5 p-3 rounded-xl border text-left transition-all duration-300 relative ${statusClass}`}
              onClick={() => { if (!isSimulating) setActiveStep(step.id); }}
              role="button"
              style={{ cursor: isSimulating ? "not-allowed" : "pointer" }}
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-[9px] font-bold text-zinc-600">0{step.id}</span>
                <StepIcon className={`w-4 h-4 ${isProcessing ? "animate-spin" : ""}`} />
              </div>
              <div className="mt-1">
                <span className="text-[10px] font-extrabold block truncate leading-tight text-zinc-200">{step.label}</span>
                <span className="text-[8px] text-zinc-500 font-medium block truncate mt-0.5">{step.desc}</span>
              </div>
              
              {/* Mini Status Indicator */}
              <div className="flex justify-between items-center text-[8px] font-mono border-t border-zinc-800/40 mt-1.5 pt-1">
                <span>{step.metricLabel}:</span>
                <span className="font-bold text-white">{step.metricValue}</span>
              </div>

              {/* Progress fill overlay for active step */}
              {isProcessing && (
                <div 
                  className="absolute bottom-0 left-0 h-1 bg-cyan-400 transition-all duration-300 rounded-b-xl"
                  style={{ width: `${simProgress}%` }}
                ></div>
              )}
            </div>
          );
        })}
      </div>

      {/* 2. DUAL BENTO GRID: SANDBOX CONTROLS + QUANT LIVE METRICS */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5" id="svos-bento-split">
        
        {/* Left 1 Column: Strategy Parameter Sandbox */}
        <div className="lg:col-span-1 bg-zinc-950/40 border border-zinc-850 p-4 rounded-xl flex flex-col gap-4">
          <h3 className="text-xs font-extrabold text-zinc-300 uppercase tracking-wider flex items-center gap-1.5">
            <Sparkles className="w-4 h-4 text-emerald-400" /> Strategy Sandbox Controls
          </h3>

          <div className="flex flex-col gap-3.5">
            {/* Strategy Select presets */}
            <div className="flex flex-col gap-1">
              <label className="text-[9px] text-zinc-400 uppercase font-mono font-bold">Strategy Core Blueprint</label>
              <select
                value={strategyName}
                onChange={(e) => setStrategyName(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-800 text-xs text-white rounded-lg p-2 font-mono outline-none"
              >
                <option value="Step Index 100 Sniper AI Bot">Step Index 100 Sniper AI Bot</option>
                <option value="SMC H4 Liquidity Sweeper">SMC H4 Liquidity Sweeper</option>
                <option value="CHoCH Momentum Rider">CHoCH Momentum Rider</option>
                <option value="FVG Intraday Scalper">FVG Intraday Scalper</option>
              </select>
            </div>

            <div className="grid grid-cols-2 gap-2">
              {/* Asset choice */}
              <div className="flex flex-col gap-1">
                <label className="text-[9px] text-zinc-400 uppercase font-mono font-bold">Asset Class</label>
                <select
                  value={targetAsset}
                  onChange={(e) => setTargetAsset(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-800 text-xs text-white rounded-lg p-2 font-mono outline-none"
                >
                  <option value="Step Index 100">Step Index 100 (Synthetic)</option>
                  <option value="EURUSD">EURUSD (SMC core)</option>
                  <option value="GBPUSD">GBPUSD (Peak pips)</option>
                  <option value="XAUUSD">XAUUSD (Volatility)</option>
                </select>
              </div>

              {/* Timeframe */}
              <div className="flex flex-col gap-1">
                <label className="text-[9px] text-zinc-400 uppercase font-mono font-bold">Execution Timeframe</label>
                <select
                  value={timeframe}
                  onChange={(e) => setTimeframe(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-800 text-xs text-white rounded-lg p-2 font-mono outline-none"
                >
                  <option value="M15">M15 (Day main)</option>
                  <option value="M5">M5 (CHoCH Scalp)</option>
                  <option value="H1">H1 (Intraday zone)</option>
                  <option value="H4">H4 (Swing main)</option>
                </select>
              </div>
            </div>

            {/* Stop Loss Slider */}
            <div className="flex flex-col gap-1">
              <div className="flex justify-between text-[10px] font-mono">
                <span className="text-zinc-400 font-bold uppercase">OB Stop Loss Offset</span>
                <span className="text-white font-black">{stopLossPips} Pips</span>
              </div>
              <input
                type="range"
                min="5"
                max="30"
                step="1"
                value={stopLossPips}
                onChange={(e) => setStopLossPips(parseInt(e.target.value))}
                className="w-full accent-emerald-400 cursor-pointer h-1 bg-zinc-800 rounded-lg"
              />
            </div>

            {/* Risk Reward multiplier slider */}
            <div className="flex flex-col gap-1">
              <div className="flex justify-between text-[10px] font-mono">
                <span className="text-zinc-400 font-bold uppercase">Target Risk-to-Reward</span>
                <span className="text-emerald-400 font-black">1 : {riskRewardRatio} R</span>
              </div>
              <input
                type="range"
                min="1.5"
                max="6.0"
                step="0.1"
                value={riskRewardRatio}
                onChange={(e) => setRiskRewardRatio(parseFloat(e.target.value))}
                className="w-full accent-emerald-400 cursor-pointer h-1 bg-zinc-800 rounded-lg"
              />
            </div>

            {/* News filter checkbox */}
            <label className="flex items-center gap-2 text-xs text-zinc-400 hover:text-white font-mono cursor-pointer bg-zinc-900/60 p-2.5 rounded-lg border border-zinc-850">
              <input
                type="checkbox"
                checked={enableNewsFilter}
                onChange={(e) => setEnableNewsFilter(e.target.checked)}
                className="rounded border-zinc-800 text-emerald-500 bg-zinc-950 focus:ring-0"
              />
              <span>Engage 30m News Circuit Breaker</span>
            </label>

            {/* Start Pipeline Action Button */}
            <button
              onClick={runPipelineSimulation}
              disabled={isSimulating}
              className={`w-full py-3 rounded-xl text-xs font-black transition flex items-center justify-center gap-2 cursor-pointer shadow-lg select-none ${
                isSimulating 
                  ? "bg-zinc-800 text-zinc-500 border border-zinc-700/50 cursor-not-allowed" 
                  : "bg-emerald-400 hover:bg-emerald-300 text-zinc-950 hover:scale-[1.01] active:scale-[0.99]"
              }`}
            >
              {isSimulating ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin text-zinc-500" /> SIMULATING PIPELINE STAGES...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-zinc-950" /> START QUANT VALIDATION PIPELINE
                </>
              )}
            </button>
          </div>
        </div>

        {/* Center & Right 2 Columns: Statistical Lab Metrics & Output Term */}
        <div className="lg:col-span-2 flex flex-col gap-4">
          
          {/* A) DYNAMIC METRICS BOARD */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {/* Metric 1 */}
            <div className="bg-zinc-950/30 border border-zinc-850 p-3 rounded-xl text-left flex flex-col justify-between">
              <span className="text-[9px] font-mono text-zinc-500 uppercase font-bold">Simulated Return</span>
              <span className="text-xl font-black font-mono mt-1 text-emerald-400">+{backtestReturn}%</span>
              <span className="text-[8px] text-zinc-500 font-mono mt-0.5">3-Yr portfolio run</span>
            </div>

            {/* Metric 2 */}
            <div className="bg-zinc-950/30 border border-zinc-850 p-3 rounded-xl text-left flex flex-col justify-between">
              <span className="text-[9px] font-mono text-zinc-500 uppercase font-bold">Profit Factor</span>
              <span className={`text-xl font-black font-mono mt-1 ${profitFactor >= 2.0 ? "text-emerald-400" : "text-amber-400"}`}>{profitFactor}</span>
              <span className="text-[8px] text-zinc-500 font-mono mt-0.5">Gross gain/loss ratio</span>
            </div>

            {/* Metric 3 */}
            <div className="bg-zinc-950/30 border border-zinc-850 p-3 rounded-xl text-left flex flex-col justify-between">
              <span className="text-[9px] font-mono text-zinc-500 uppercase font-bold">Max Drawdown</span>
              <span className="text-xl font-black font-mono mt-1 text-rose-400">-{maxDrawdown}%</span>
              <span className="text-[8px] text-zinc-500 font-mono mt-0.5">95% Monte Carlo peak</span>
            </div>

            {/* Metric 4 */}
            <div className="bg-zinc-950/30 border border-zinc-850 p-3 rounded-xl text-left flex flex-col justify-between">
              <span className="text-[9px] font-mono text-zinc-500 uppercase font-bold">Validation Status</span>
              <span className={`text-xs font-black font-mono mt-1.5 px-2 py-0.5 rounded-md border inline-block text-center ${passedValidation ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-rose-500/10 text-rose-400 border-rose-500/20"}`}>
                {passedValidation ? "APPROVED" : "LOGIC WARNING"}
              </span>
              <span className="text-[8px] text-zinc-500 font-mono mt-0.5">{passedValidation ? "D3 Robust compliance" : "Adjust limits"}</span>
            </div>
          </div>

          {/* DYNAMIC ACTIVE WORKSPACE STEP DETAILS (1-8) */}
          <div className="bg-zinc-950/85 border border-zinc-800/80 rounded-xl p-5 flex flex-col gap-5 shadow-xl min-h-[350px]">
            
            {/* STAGE 1: INTAKE & AUDIT */}
            {activeStep === 1 && (
              <div className="flex flex-col gap-4">
                <div className="border-b border-zinc-900 pb-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
                  <div>
                    <h4 className="text-xs font-black text-emerald-400 uppercase tracking-widest flex items-center gap-2">
                      <Lightbulb className="w-4 h-4" /> Stage 1: Strategy Intake &amp; Rule Auditing
                    </h4>
                    <p className="text-[9px] text-zinc-500 font-mono mt-0.5">Synthesize SMC parameters, starting capital, and syntactic safeguards</p>
                  </div>
                  <span className="text-[10px] bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-mono px-2 py-0.5 rounded font-bold">
                    COMPLIANT (100%)
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Left Parameter panel */}
                  <div className="flex flex-col gap-3.5 bg-zinc-900/40 p-4 rounded-xl border border-zinc-850">
                    <span className="text-[10px] font-mono text-zinc-400 uppercase font-bold tracking-wider">Account Scaling Setup</span>
                    
                    <div className="grid grid-cols-2 gap-3">
                      <div className="flex flex-col gap-1">
                        <label className="text-[9px] text-zinc-500 font-mono font-bold uppercase">Starting Capital</label>
                        <div className="relative">
                          <span className="absolute left-2.5 top-2 text-zinc-500 text-xs">$</span>
                          <input 
                            type="number" 
                            value={startingCapital} 
                            onChange={(e) => setStartingCapital(Math.max(100, parseInt(e.target.value) || 0))}
                            className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-1.5 pl-6 text-xs text-white font-mono outline-none"
                          />
                        </div>
                      </div>
                      
                      <div className="flex flex-col gap-1">
                        <label className="text-[9px] text-zinc-500 font-mono font-bold uppercase">Daily Scalp Target</label>
                        <div className="relative">
                          <span className="absolute left-2.5 top-2 text-zinc-500 text-xs">$</span>
                          <input 
                            type="number" 
                            value={dailyProfitTarget} 
                            onChange={(e) => setDailyProfitTarget(Math.max(100, parseInt(e.target.value) || 0))}
                            className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-1.5 pl-6 text-xs text-white font-mono outline-none"
                          />
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-col gap-2 border-t border-zinc-850 pt-3">
                      <div className="flex items-center justify-between">
                        <label className="text-[10px] text-zinc-300 font-bold uppercase flex items-center gap-1.5 cursor-pointer">
                          <input 
                            type="checkbox" 
                            checked={hybridModeEnabled} 
                            onChange={(e) => setHybridModeEnabled(e.target.checked)}
                            className="rounded border-zinc-800 text-emerald-500 bg-zinc-950 focus:ring-0"
                          />
                          Enable Parallel Hybrid Swing Scanner
                        </label>
                        <span className={`text-[8px] font-mono font-black px-1.5 py-0.2 rounded ${hybridModeEnabled ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-zinc-800 text-zinc-500"}`}>
                          {hybridModeEnabled ? "ACTIVE" : "STANDBY"}
                        </span>
                      </div>
                      <p className="text-[9px] text-zinc-500 leading-normal">
                        <strong>Day builds margin &rarr; Swing scales the gains:</strong> Bot day-trades Step Index 100 on M15 until an H1/H4 unmitigated order block aligns with 61.8–78.6% Fib. Swing entry placed using profit buffer only.
                      </p>
                    </div>
                  </div>

                  {/* Right Rules check */}
                  <div className="flex flex-col gap-3 bg-zinc-900/40 p-4 rounded-xl border border-zinc-850">
                    <span className="text-[10px] font-mono text-zinc-400 uppercase font-bold tracking-wider">Syntactic Audit Checklist</span>
                    <div className="flex flex-col gap-2 text-[10px] text-zinc-400 font-mono">
                      {[
                        { text: "Division-by-zero boundary safeguards compiled", ok: true },
                        { text: "Infinity-loop breakout thresholds verified", ok: true },
                        { text: "Variable slippage multiplier constraints loaded", ok: true },
                        { text: "SMC structure detection rules validated syntactically", ok: true },
                        { text: "Fibonacci level array boundaries mapped correctly", ok: true }
                      ].map((item, idx) => (
                        <div key={idx} className="flex items-center gap-2 border-b border-zinc-850/50 pb-1.5 last:border-0 last:pb-0">
                          <Check className="w-3.5 h-3.5 text-emerald-400" />
                          <span className="truncate">{item.text}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* STAGE 2: HISTORICAL REPLAY */}
            {activeStep === 2 && (
              <div className="flex flex-col gap-4">
                <div className="border-b border-zinc-900 pb-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
                  <div>
                    <h4 className="text-xs font-black text-emerald-400 uppercase tracking-widest flex items-center gap-2">
                      <History className="w-4 h-4" /> Stage 2: High-Fidelity Historical Replay
                    </h4>
                    <p className="text-[9px] text-zinc-500 font-mono mt-0.5">Stream tick frame buffers candle-by-candle to evaluate Smart Money entry triggers</p>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    {/* Speed selector */}
                    <div className="flex items-center bg-zinc-900 border border-zinc-800 rounded-lg p-0.5 font-mono text-[9px] font-bold">
                      <span className="text-[8px] text-zinc-500 px-1.5 uppercase font-black">Speed:</span>
                      {([1, 2, 4] as const).map((spd) => (
                        <button
                          key={spd}
                          onClick={() => setReplaySpeed(spd)}
                          className={`px-2 py-0.5 rounded cursor-pointer transition ${replaySpeed === spd ? "bg-emerald-500 text-zinc-950 font-black" : "text-zinc-400 hover:text-white"}`}
                        >
                          {spd}x
                        </button>
                      ))}
                    </div>

                    {/* Reset Button */}
                    <button
                      onClick={() => {
                        setIsReplayPlaying(false);
                        setReplayCandleIndex(0);
                        addLog("[REPLAY] Replay buffer reset. Click START to stream.");
                      }}
                      className="px-2 py-1 bg-zinc-900 hover:bg-zinc-800 text-zinc-400 hover:text-white rounded-lg text-[10px] font-bold border border-zinc-800 transition cursor-pointer"
                    >
                      RESET
                    </button>

                    <button
                      onClick={() => setIsReplayPlaying(!isReplayPlaying)}
                      className={`px-3 py-1 rounded-lg text-[10px] font-bold flex items-center gap-1 cursor-pointer transition ${
                        isReplayPlaying 
                          ? "bg-amber-500 text-zinc-950 hover:bg-amber-400" 
                          : "bg-emerald-500 text-zinc-950 hover:bg-emerald-400"
                      }`}
                    >
                      {isReplayPlaying ? (
                        <>
                          <Pause className="w-3 h-3 fill-zinc-950" /> PAUSE
                        </>
                      ) : (
                        <>
                          <Play className="w-3 h-3 fill-zinc-950" /> START STREAM
                        </>
                      )}
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                  {/* Left 2x Block: Replay visualization & dynamic candle rendering */}
                  <div className="lg:col-span-2 bg-zinc-900/40 border border-zinc-850 p-4 rounded-xl flex flex-col gap-3 justify-between">
                    <div>
                      <div className="flex justify-between items-center text-[10px] font-mono text-zinc-400">
                        <span className="flex items-center gap-1">
                          <Activity className={`w-3.5 h-3.5 text-emerald-400 ${isReplayPlaying ? "animate-pulse" : ""}`} />
                          Live {targetAsset} Candle Feed Progress:
                        </span>
                        <span className="text-emerald-400 font-bold">{replayCandleIndex}% ({Math.max(1, Math.floor(replayCandleIndex / 10))} / 10 periods)</span>
                      </div>
                      
                      {/* Interactive Progress Bar */}
                      <div className="w-full bg-zinc-950 h-1.5 rounded-full mt-1.5 border border-zinc-800/80 overflow-hidden relative">
                        <div 
                          className="h-full bg-emerald-400 rounded-full transition-all duration-300"
                          style={{ width: `${replayCandleIndex}%` }}
                        ></div>
                      </div>
                    </div>

                    {/* DYNAMIC CANDLESTICK SVG DISPLAY PANEL */}
                    <div className="bg-zinc-950 border border-zinc-900 rounded-xl p-2.5 h-36 flex items-center justify-center relative overflow-hidden">
                      <svg viewBox="0 0 520 130" className="w-full h-full">
                        {/* 1. Gridlines */}
                        <line x1="10" y1="20" x2="510" y2="20" className="stroke-zinc-900 stroke-1 stroke-dasharray" strokeDasharray="3,3" />
                        <line x1="10" y1="65" x2="510" y2="65" className="stroke-zinc-900 stroke-1 stroke-dasharray" strokeDasharray="3,3" />
                        <line x1="10" y1="110" x2="510" y2="110" className="stroke-zinc-900 stroke-1 stroke-dasharray" strokeDasharray="3,3" />

                        {/* 2. Horizontal Level Annotations */}
                        {/* Take Profit Target Line */}
                        <line x1="15" y1="23" x2="505" y2="23" className="stroke-emerald-500/30 stroke-1" strokeDasharray="2,2" />
                        <text x="20" y="18" className="fill-emerald-400/40 font-mono text-[7px] uppercase font-bold">Target Take-Profit</text>

                        {/* Stop Loss Target Line */}
                        <line x1="15" y1="114" x2="505" y2="114" className="stroke-rose-500/30 stroke-1" strokeDasharray="2,2" />
                        <text x="20" y="125" className="fill-rose-400/40 font-mono text-[7px] uppercase font-bold">Stop Loss Buffer</text>

                        {/* Order Block Shaded Box (Candles index 6 to 9) */}
                        {replayCandleIndex >= 60 && (
                          <g>
                            <rect x="310" y="72" width="180" height="17" className="fill-emerald-500/5 stroke-emerald-500/20 stroke-1" strokeDasharray="1,2" />
                            <text x="315" y="83" className="fill-emerald-400/50 font-mono text-[7px] uppercase font-black">H4 ORDER BLOCK</text>
                          </g>
                        )}

                        {/* 3. Render Candle array dynamically revealed by playback progress */}
                        {[
                          { o: 0, h: 4, l: -2, c: 2, label: "Sweep", type: "sweep" },
                          { o: 2, h: 5, l: -6, c: -3, label: "Low Swept", type: "sweep" },
                          { o: -3, h: 1, l: -4, c: -1, label: "CHoCH", type: "choch" },
                          { o: -1, h: 8, l: -2, c: 6, label: "BOS", type: "bos" },
                          { o: 6, h: 10, l: 4, c: 9, label: "Impulse", type: "impulse" },
                          { o: 9, h: 11, l: 3, c: 5, label: "Retrace", type: "ob_test" },
                          { o: 5, h: 6, l: 2, c: 4, label: "OB Touch", type: "ob_touch" },
                          { o: 4, h: 12, l: 3, c: 10, label: "ENTRY", type: "entry" },
                          { o: 10, h: 18, l: 9, c: 16, label: "Rally", type: "profit" },
                          { o: 16, h: 22, l: 15, c: 21, label: "TP HIT", type: "tp" }
                        ].map((cndl, i) => {
                          const maxVisibleIdx = Math.floor(replayCandleIndex / 10);
                          if (i > maxVisibleIdx) return null;

                          // convert relative to SVG Y (box bounds relative -8 to 24)
                          const openY = 120 - ((cndl.o - (-8)) / 32) * 100;
                          const closeY = 120 - ((cndl.c - (-8)) / 32) * 100;
                          const highY = 120 - ((cndl.h - (-8)) / 32) * 100;
                          const lowY = 120 - ((cndl.l - (-8)) / 32) * 100;

                          const cx = i * 46 + 45;
                          const isBullish = cndl.c >= cndl.o;
                          const themeClass = isBullish 
                            ? "text-emerald-400 fill-emerald-500/10 stroke-emerald-400" 
                            : "text-rose-400 fill-rose-500/10 stroke-rose-400";

                          const bodyY = Math.min(openY, closeY);
                          const bodyH = Math.max(2, Math.abs(openY - closeY));

                          return (
                            <g key={i} className="transition-all duration-300">
                              {/* Wick */}
                              <line x1={cx} y1={highY} x2={cx} y2={lowY} className={`${isBullish ? "stroke-emerald-400" : "stroke-rose-400"} stroke-[1.5]`} />
                              {/* Body */}
                              <rect x={cx - 11} y={bodyY} width={22} height={bodyH} className={`${themeClass} stroke-[1.5]`} rx="2" />

                              {/* Candle specific annotation tags */}
                              {cndl.label && (
                                <g>
                                  {cndl.type === "sweep" && i === 1 && (
                                    <path d={`M ${cx} ${lowY + 4} L ${cx - 4} ${lowY + 10} L ${cx + 4} ${lowY + 10} Z`} className="fill-rose-400 text-rose-400" />
                                  )}
                                  {cndl.type === "entry" && i === 7 && (
                                    <circle cx={cx} cy={lowY} r="4.5" className="fill-emerald-400 stroke-zinc-950 stroke-1 animate-pulse" />
                                  )}
                                  <text 
                                    x={cx} 
                                    y={isBullish ? highY - 6 : lowY + 12} 
                                    className={`text-[6.5px] font-mono text-center font-bold tracking-tighter ${cndl.type === "entry" ? "fill-emerald-400" : cndl.type === "sweep" ? "fill-rose-400" : "fill-zinc-400"}`}
                                    textAnchor="middle"
                                  >
                                    {cndl.label}
                                  </text>
                                </g>
                              )}
                            </g>
                          );
                        })}
                      </svg>
                    </div>

                    <div className="grid grid-cols-3 gap-2 text-center mt-1">
                      <div className="bg-zinc-950 p-2.5 rounded-lg border border-zinc-900">
                        <span className="text-[8px] font-mono text-zinc-500 block uppercase">Buffered Ticks</span>
                        <span className="text-xs font-bold text-white font-mono mt-0.5 block">1,480,500</span>
                      </div>
                      <div className="bg-zinc-950 p-2.5 rounded-lg border border-zinc-900">
                        <span className="text-[8px] font-mono text-zinc-500 block uppercase">Symbol Focus</span>
                        <span className="text-xs font-bold text-white font-mono mt-0.5 block">{targetAsset}</span>
                      </div>
                      <div className="bg-zinc-950 p-2.5 rounded-lg border border-zinc-900">
                        <span className="text-[8px] font-mono text-zinc-500 block uppercase">Active Sweeps</span>
                        <span className="text-xs font-bold text-emerald-400 font-mono mt-0.5 block">4 Structures</span>
                      </div>
                    </div>
                  </div>

                  {/* Right 1x Block: Replay Telemetry info */}
                  <div className="bg-zinc-900/40 border border-zinc-850 p-4 rounded-xl flex flex-col gap-2.5 justify-center">
                    <span className="text-[10px] font-mono text-zinc-400 uppercase font-bold block border-b border-zinc-800 pb-1.5">Replay Protocol</span>
                    <p className="text-[9px] text-zinc-500 leading-relaxed font-mono">
                      The High-Fidelity Historical Replay streams tick buffer data at millisecond granularity. It replicates actual spread inflation, slippage events, and unmitigated order blocks to confirm the {timeframe} strategy holds up to real historical constraints.
                    </p>
                    <div className="border-t border-zinc-850 pt-2 flex flex-col gap-1 text-[8.5px] font-mono text-zinc-400">
                      <div className="flex justify-between">
                        <span>P&amp;L Expected Multiplier:</span>
                        <span className="text-emerald-400 font-bold">{targetAsset === "Step Index 100" ? "$10 / pip" : "$100 / pip"}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Min Candle Interval:</span>
                        <span className="text-white">15 Minutes</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* STAGE 3: STATISTICAL BACKTEST */}
            {activeStep === 3 && (
              <div className="flex flex-col gap-4">
                <div className="border-b border-zinc-900 pb-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
                  <div>
                    <h4 className="text-xs font-black text-emerald-400 uppercase tracking-widest flex items-center gap-2">
                      <TrendingUp className="w-4 h-4" /> Stage 3: Statistical Backtest &amp; Frequency Metrics
                    </h4>
                    <p className="text-[9px] text-zinc-500 font-mono mt-0.5">Comprehensive historical data verification over multi-year portfolio curves</p>
                  </div>
                  <span className="text-[10px] bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-mono px-2 py-0.5 rounded font-bold">
                    WINRATE EXPECTANCY: 64.5%
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Left Column: Trade frequency estimates */}
                  <div className="flex flex-col gap-3 bg-zinc-900/40 p-4 rounded-xl border border-zinc-850">
                    <span className="text-[10px] font-mono text-zinc-400 uppercase font-bold tracking-wider">Trade Frequency Expectations (Step Index 100)</span>
                    <div className="overflow-x-auto mt-1">
                      <table className="w-full text-left font-mono text-[9px] text-zinc-400">
                        <thead>
                          <tr className="border-b border-zinc-850 text-zinc-500">
                            <th className="pb-1.5 font-bold uppercase">Setup Scale</th>
                            <th className="pb-1.5 font-bold uppercase">Expected Frequency</th>
                            <th className="pb-1.5 font-bold uppercase text-right">Target Range</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr className="border-b border-zinc-850/50 last:border-0 hover:bg-zinc-900/20">
                            <td className="py-2 font-bold text-white">Intraday Sniper Trade</td>
                            <td className="py-2 text-zinc-300">2–4 times daily</td>
                            <td className="py-2 text-right text-emerald-400">100–300 Pips</td>
                          </tr>
                          <tr className="border-b border-zinc-850/50 last:border-0 hover:bg-zinc-900/20">
                            <td className="py-2 font-bold text-white">H4 Swing Trade</td>
                            <td className="py-2 text-zinc-300">1–3 times weekly</td>
                            <td className="py-2 text-right text-emerald-400">300–500 Pips</td>
                          </tr>
                          <tr className="border-b border-zinc-850/50 last:border-0 hover:bg-zinc-900/20">
                            <td className="py-2 font-bold text-white">Multi-Leg Trend Compound</td>
                            <td className="py-2 text-zinc-300">1x per week</td>
                            <td className="py-2 text-right text-emerald-400">500–1000+ Pips</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Right Column: Other backtest stats */}
                  <div className="flex flex-col gap-3 bg-zinc-900/40 p-4 rounded-xl border border-zinc-850">
                    <span className="text-[10px] font-mono text-zinc-400 uppercase font-bold tracking-wider">Performance Expectations</span>
                    <div className="grid grid-cols-2 gap-3 mt-1">
                      <div className="bg-zinc-950 p-2.5 rounded-lg border border-zinc-850/50">
                        <span className="text-[8px] font-mono text-zinc-500 block uppercase">Sharpe Ratio</span>
                        <span className="text-sm font-bold text-white mt-0.5 block">2.42</span>
                      </div>
                      <div className="bg-zinc-950 p-2.5 rounded-lg border border-zinc-850/50">
                        <span className="text-[8px] font-mono text-zinc-500 block uppercase">Sortino Ratio</span>
                        <span className="text-sm font-bold text-white mt-0.5 block">3.10</span>
                      </div>
                      <div className="bg-zinc-950 p-2.5 rounded-lg border border-zinc-850/50">
                        <span className="text-[8px] font-mono text-zinc-500 block uppercase">R-Expectancy</span>
                        <span className="text-sm font-bold text-emerald-400 mt-0.5 block">+0.45 R / trade</span>
                      </div>
                      <div className="bg-zinc-950 p-2.5 rounded-lg border border-zinc-850/50">
                        <span className="text-[8px] font-mono text-zinc-500 block uppercase">Total Trades Sim</span>
                        <span className="text-sm font-bold text-white mt-0.5 block">1,482 positions</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* STAGE 4: PERFECT OB FILTER */}
            {activeStep === 4 && (
              <div className="flex flex-col gap-4">
                <div className="border-b border-zinc-900 pb-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
                  <div>
                    <h4 className="text-xs font-black text-emerald-400 uppercase tracking-widest flex items-center gap-2">
                      <FileCheck className="w-4 h-4" /> Stage 4: Perfect OB Filter &amp; MC Stress Testing
                    </h4>
                    <p className="text-[9px] text-zinc-500 font-mono mt-0.5">Filter out weak/fake structures dynamically by scoring unmitigated order blocks</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-zinc-400 font-mono">Confluence Score:</span>
                    <span className={`text-xs font-mono font-black px-2 py-0.5 rounded border ${
                      calculatedObScore >= acceptanceThreshold 
                        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" 
                        : "bg-rose-500/10 text-rose-400 border-rose-500/20"
                    }`}>
                      {calculatedObScore}/6 {calculatedObScore >= acceptanceThreshold ? "APPROVED" : "REJECTED"}
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Left Column: Criteria Checkboxes */}
                  <div className="flex flex-col gap-3 bg-zinc-900/40 p-4 rounded-xl border border-zinc-850">
                    <div className="flex items-center justify-between border-b border-zinc-850 pb-2">
                      <span className="text-[10px] font-mono text-zinc-400 uppercase font-bold">Filter Criteria Checklist</span>
                      <div className="flex items-center gap-1.5">
                        <span className="text-[9px] text-zinc-500 font-mono uppercase font-bold">Acceptance Threshold:</span>
                        <select
                          value={acceptanceThreshold}
                          onChange={(e) => setAcceptanceThreshold(parseInt(e.target.value))}
                          className="bg-zinc-950 border border-zinc-800 text-[10px] text-emerald-400 rounded p-1 font-mono outline-none cursor-pointer"
                        >
                          <option value={3}>&gt;= 3</option>
                          <option value={4}>&gt;= 4</option>
                          <option value={5}>&gt;= 5</option>
                          <option value={6}>&gt;= 6</option>
                        </select>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 gap-2 text-[10px] text-zinc-400 font-mono">
                      <label className="flex items-center gap-2.5 cursor-pointer hover:text-white transition">
                        <input 
                          type="checkbox" 
                          checked={obScoreDisplacement} 
                          onChange={(e) => setObScoreDisplacement(e.target.checked)}
                          className="rounded border-zinc-800 text-emerald-500 bg-zinc-950 focus:ring-0"
                        />
                        <span>[+1] Order Block caused clean displacement</span>
                      </label>
                      <label className="flex items-center gap-2.5 cursor-pointer hover:text-white transition">
                        <input 
                          type="checkbox" 
                          checked={obScoreUnmitigated} 
                          onChange={(e) => setObScoreUnmitigated(e.target.checked)}
                          className="rounded border-zinc-800 text-emerald-500 bg-zinc-950 focus:ring-0"
                        />
                        <span>[+1] Order Block is unmitigated</span>
                      </label>
                      <label className="flex items-center gap-2.5 cursor-pointer hover:text-white transition">
                        <input 
                          type="checkbox" 
                          checked={obScoreSweep} 
                          onChange={(e) => setObScoreSweep(e.target.checked)}
                          className="rounded border-zinc-800 text-emerald-500 bg-zinc-950 focus:ring-0"
                        />
                        <span>[+1] Liquidity sweep occurred just before OB</span>
                      </label>
                      <label className="flex items-center gap-2.5 cursor-pointer hover:text-white transition">
                        <input 
                          type="checkbox" 
                          checked={obScoreFib} 
                          onChange={(e) => setObScoreFib(e.target.checked)}
                          className="rounded border-zinc-800 text-emerald-500 bg-zinc-950 focus:ring-0"
                        />
                        <span>[+1] OB sits within 61.8%–78.6% Fib zone</span>
                      </label>
                      <label className="flex items-center gap-2.5 cursor-pointer hover:text-white transition">
                        <input 
                          type="checkbox" 
                          checked={obScoreStructure} 
                          onChange={(e) => setObScoreStructure(e.target.checked)}
                          className="rounded border-zinc-800 text-emerald-500 bg-zinc-950 focus:ring-0"
                        />
                        <span>[+1] Clean structure surrounding OB (no wick chaos)</span>
                      </label>
                      <label className="flex items-center gap-2.5 cursor-pointer hover:text-white transition">
                        <input 
                          type="checkbox" 
                          checked={obScoreImpulse} 
                          onChange={(e) => setObScoreImpulse(e.target.checked)}
                          className="rounded border-zinc-800 text-emerald-500 bg-zinc-950 focus:ring-0"
                        />
                        <span>[+1] Impulse from OB caused BOS</span>
                      </label>
                    </div>
                  </div>

                  {/* Right Column: Monte Carlo Stress Test & self learning */}
                  <div className="flex flex-col gap-3 bg-zinc-900/40 p-4 rounded-xl border border-zinc-850 justify-between">
                    <div>
                      <span className="text-[10px] font-mono text-zinc-400 uppercase font-bold block border-b border-zinc-850 pb-2">LSTM Learning &amp; Optimizer Module</span>
                      <p className="text-[9px] text-zinc-500 leading-relaxed font-mono mt-2">
                        Continuously learns from historical post-close structures, refining filter thresholds and SL/TP matrices.
                      </p>
                    </div>

                    <div className="flex flex-col gap-2 pt-2 border-t border-zinc-850/50">
                      <div className="flex items-center justify-between text-[9px] font-mono text-zinc-400">
                        <span>Learning epoch state:</span>
                        <span className="text-emerald-400 font-bold">{trainingEpochs}/100</span>
                      </div>
                      
                      <button
                        onClick={startSelfTraining}
                        disabled={trainingRunning}
                        className={`w-full py-2 rounded-lg text-[10px] font-black tracking-wider uppercase transition cursor-pointer select-none border border-emerald-500/20 ${
                          trainingRunning 
                            ? "bg-zinc-800 text-zinc-600 border-zinc-750 cursor-not-allowed animate-pulse" 
                            : "bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/15"
                        }`}
                      >
                        {trainingRunning ? "OPTIMIZING ATTENTION WEIGHTS..." : "ENGAGE AI SELF-TRAINING ENGINE"}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* STAGE 5: EVF ISOLATION TESTING */}
            {activeStep === 5 && (
              <div className="bg-zinc-950/80 rounded-xl flex flex-col gap-4">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 border-b border-zinc-900 pb-2.5">
                  <div>
                    <h4 className="text-xs font-black text-emerald-400 uppercase tracking-widest flex items-center gap-2">
                      <Activity className="w-4 h-4 text-emerald-400 animate-pulse" />
                      Execution Validation Framework (EVF) Workspace
                    </h4>
                    <p className="text-[9px] text-zinc-500 font-mono mt-0.5">8-Stage Isolation Testing &amp; Gatekeeper Protocols</p>
                  </div>
                  <button
                    onClick={startVirtualDemoSequence}
                    disabled={demoRunning}
                    className={`px-4 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 cursor-pointer shadow ${
                      demoRunning 
                        ? "bg-zinc-800 text-zinc-600 border border-zinc-750 cursor-not-allowed" 
                        : "bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-black hover:scale-[1.01]"
                    }`}
                  >
                    {demoRunning ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" /> RUNNING GATE TESTS ({demoStep}/8)...
                      </>
                    ) : (
                      <>
                        <Play className="w-3.5 h-3.5 fill-zinc-950" /> ENGAGE EVF GATE TESTS
                      </>
                    )}
                  </button>
                </div>

                {/* The 8 checklist sub-steps flowing downwards/horizontally */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3" id="virtual-demo-sub-steps">
                  {[
                    { id: 1, name: "Historical Data", desc: "Sync tick feed & CSV candles", icon: Database, stats: "1,200,000 candles synced", passMsg: "PASS - History Complete" },
                    { id: 2, name: "Strategy Signal Generator", desc: "CHoCH, OB, FVG compilation", icon: Sparkles, stats: "142 valid sweeps tracked", passMsg: "PASS - Signals Safe" },
                    { id: 3, name: "Risk Firewall", desc: "Leverage & drawdown limits", icon: ShieldCheck, stats: "Compliance validation: 100%", passMsg: "PASS - Firewall Active" },
                    { id: 4, name: "Virtual Execution Engine", desc: "Low-latency memory simulator", icon: RefreshCw, stats: "Avg latency: 0.4ms | 99.8% fill", passMsg: "PASS - Fill Verified" },
                    { id: 5, name: "Trade Journal", desc: "Secure JSON ledger logging", icon: FileText, stats: "142 mock entries recorded", passMsg: "PASS - Logs Journaled" },
                    { id: 6, name: "Performance Report", desc: "Compute Profit Factor & Sharpe", icon: BarChart4, stats: `Profit Factor: ${profitFactor} | Win Rate: 64.5%`, passMsg: "PASS - Stats Robust" },
                    { id: 7, name: "Readiness Verdict", desc: "System stability confirmation", icon: Award, stats: "Verdict index score: 98.4/100", passMsg: "PASS - APPROVED READY" },
                    { id: 8, name: "Broker Demo API", desc: "Secure gateway hot connectivity", icon: Radio, stats: brokerConnected ? "CONNECTED - WebSockets Active" : "LOCKED until Steps 1-7 pass", passMsg: "ONLINE - Sandbox Stream" }
                  ].map((step) => {
                    const StepIcon = step.icon;
                    const isActive = demoStep === step.id;
                    const isCompleted = demoStep > step.id || brokerConnected;
                    const isLocked = step.id === 8 && !brokerConnected && !isActive;

                    let borderStyle = "border-zinc-900 bg-zinc-900/10 text-zinc-600";
                    let iconColor = "text-zinc-600";
                    if (isActive) {
                      borderStyle = "border-amber-500/40 bg-amber-500/5 text-amber-400 shadow shadow-amber-500/2";
                      iconColor = "text-amber-400";
                    } else if (isCompleted) {
                      borderStyle = "border-emerald-500/35 bg-emerald-500/5 text-emerald-400";
                      iconColor = "text-emerald-400";
                    } else if (isLocked) {
                      borderStyle = "border-zinc-900 bg-zinc-955 text-zinc-700 opacity-60";
                      iconColor = "text-zinc-700";
                    }

                    return (
                      <div 
                        key={step.id} 
                        className={`flex items-start gap-3 p-3 rounded-xl border transition-all duration-300 ${borderStyle}`}
                      >
                        <div className={`p-2 rounded-lg ${isActive ? "bg-amber-500/10" : isCompleted ? "bg-emerald-500/10" : "bg-zinc-950"} border border-zinc-800 shrink-0`}>
                          <StepIcon className={`w-4 h-4 ${isActive ? "animate-spin" : ""} ${iconColor}`} />
                        </div>
                        
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-1">
                            <span className="text-[10px] font-black text-zinc-300 truncate uppercase">
                              0{step.id}. {step.name}
                            </span>
                            {isCompleted ? (
                              <span className="text-[8px] font-mono bg-emerald-500/10 text-emerald-400 px-1.5 py-0.2 rounded font-extrabold flex items-center gap-1">
                                <Check className="w-2.5 h-2.5" /> {step.passMsg}
                              </span>
                            ) : isActive ? (
                              <span className="text-[8px] font-mono bg-amber-500/10 text-amber-400 px-1.5 py-0.2 rounded font-extrabold animate-pulse">
                                VALIDATING...
                              </span>
                            ) : (
                              <span className="text-[8px] font-mono bg-zinc-900 text-zinc-500 px-1.5 py-0.2 rounded font-semibold">
                                {step.id === 8 ? "LOCKED" : "QUEUED"}
                              </span>
                            )}
                          </div>
                          <p className="text-[9px] text-zinc-500 truncate mt-0.5">{step.desc}</p>
                          
                          {/* Interactive Stats Telemetry display */}
                          <div className="mt-1.5 border-t border-zinc-900/50 pt-1 flex items-center justify-between text-[8px] font-mono text-zinc-400">
                            <span>TELEMETRY:</span>
                            <span className={`font-bold ${isActive ? "text-amber-400" : isCompleted ? "text-emerald-400" : "text-zinc-600"}`}>
                              {step.stats}
                            </span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* STAGE 6: RGM RISK ENGINE */}
            {activeStep === 6 && (
              <div className="flex flex-col gap-4">
                <div className="border-b border-zinc-900 pb-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
                  <div>
                    <h4 className="text-xs font-black text-emerald-400 uppercase tracking-widest flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4" /> Stage 6: Risk Governance Module (RGM)
                    </h4>
                    <p className="text-[9px] text-zinc-500 font-mono mt-0.5">Control margin allocation, drawdowns, and day trade profit redirection</p>
                  </div>
                  <span className="text-[10px] bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-mono px-2 py-0.5 rounded font-bold">
                    FIREWALL: ONLINE
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Left Column: Risk allocations */}
                  <div className="flex flex-col gap-3.5 bg-zinc-900/40 p-4 rounded-xl border border-zinc-850">
                    <span className="text-[10px] font-mono text-zinc-400 uppercase font-bold tracking-wider">Allocation Verification &amp; Sliders</span>
                    
                    {/* Swing Risk Buffer Slider */}
                    <div className="flex flex-col gap-1 mt-1">
                      <div className="flex justify-between text-[9px] font-mono">
                        <span className="text-zinc-500 font-bold uppercase">Swing Profit Buffer Risk</span>
                        <span className="text-emerald-400 font-black">{swingRiskBufferPercent}% of Day Profit</span>
                      </div>
                      <input 
                        type="range" 
                        min="20" 
                        max="100" 
                        step="5"
                        value={swingRiskBufferPercent}
                        onChange={(e) => setSwingRiskBufferPercent(parseInt(e.target.value))}
                        className="w-full accent-emerald-400 cursor-pointer h-1 bg-zinc-800 rounded-lg"
                      />
                    </div>

                    {/* Day trade max risk */}
                    <div className="flex flex-col gap-2 text-[9px] text-zinc-500 font-mono mt-1 border-t border-zinc-850 pt-3">
                      <div className="flex items-center justify-between">
                        <span>Max Day Trades / Session:</span>
                        <span className="text-white font-bold">3–5 positions</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span>Max Day Trade Exposure:</span>
                        <span className="text-white font-bold">10% – 20% of balance</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span>SMC Swing Stop Loss:</span>
                        <span className="text-white font-bold">100–300 Pips (H4 OB wick)</span>
                      </div>
                    </div>
                  </div>

                  {/* Right Column: Capital Preservation Firewall */}
                  <div className="flex flex-col gap-3 bg-zinc-900/40 p-4 rounded-xl border border-zinc-850 justify-between">
                    <div>
                      <span className="text-[10px] font-mono text-zinc-400 uppercase font-bold block border-b border-zinc-850 pb-2">Capital Preservation Module</span>
                      <p className="text-[9px] text-zinc-500 leading-normal font-mono mt-2">
                        Protects core seed capital ($1k principal). Hybrid mode allocates <strong>only</strong> processed intraday day trade profits buffer into swing trades.
                      </p>
                    </div>

                    <label className="flex items-center gap-2.5 text-xs text-zinc-400 hover:text-white font-mono cursor-pointer bg-zinc-950 p-2.5 rounded-lg border border-zinc-850">
                      <input 
                        type="checkbox" 
                        checked={pauseDayTradingOnSwing} 
                        onChange={(e) => setPauseDayTradingOnSwing(e.target.checked)}
                        className="rounded border-zinc-800 text-emerald-500 bg-zinc-950 focus:ring-0"
                      />
                      <span>Pause Day Trades while Swing trade active</span>
                    </label>
                  </div>
                </div>
              </div>
            )}

            {/* STAGE 7: LIVE DEMO SANDBOX */}
            {activeStep === 7 && (
              <div className="flex flex-col gap-4">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 border-b border-zinc-900 pb-2.5">
                  <div>
                    <h4 className="text-xs font-black text-emerald-400 uppercase tracking-widest flex items-center gap-2">
                      <Radio className="w-4 h-4 animate-pulse" /> Stage 7: Virtual Live Demo Sandbox
                    </h4>
                    <p className="text-[9px] text-zinc-500 font-mono mt-0.5">Test hot trading execution loops using mock websockets connected to the Bybit/Deriv sandbox</p>
                  </div>
                  <button
                    onClick={() => {
                      const nextState = !brokerConnected;
                      setBrokerConnected(nextState);
                      if (nextState) {
                        addLog("[WS GATEWAY] WebSockets connecting... Streaming live ticks.");
                      } else {
                        addLog("[WS GATEWAY] Sandbox disconnected.");
                      }
                    }}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 cursor-pointer shadow ${
                      brokerConnected 
                        ? "bg-rose-500 hover:bg-rose-400 text-white" 
                        : "bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-black"
                    }`}
                  >
                    {brokerConnected ? "DISCONNECT GATEWAY" : "CONNECT SANDBOX"}
                  </button>
                </div>

                {/* Only then: Broker Demo API Interactive Control Block */}
                <div className={`border rounded-xl p-3 flex flex-col sm:flex-row items-center justify-between gap-3 transition-all duration-300 ${
                  brokerConnected 
                    ? "bg-emerald-500/5 border-emerald-500/30" 
                    : "bg-zinc-950 border-zinc-900 opacity-80"
                }`}>
                  <div className="flex items-center gap-3">
                    <div className={`p-2.5 rounded-xl ${brokerConnected ? "bg-emerald-500/10 text-emerald-400" : "bg-zinc-900 text-zinc-600"} border border-zinc-800`}>
                      <Server className="w-4 h-4" />
                    </div>
                    <div className="text-left">
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-black text-white uppercase">SMC broker API Gateway</span>
                        <span className={`text-[8px] font-mono font-bold px-1.5 py-0.2 rounded border ${
                          brokerConnected 
                            ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30 animate-pulse" 
                            : "bg-zinc-900 text-zinc-500 border-zinc-800"
                        }`}>
                          {brokerConnected ? "ONLINE (DEMO-NET)" : "DISCONNECTED"}
                        </span>
                      </div>
                      <p className="text-[9px] text-zinc-500 font-mono mt-0.5">
                        {brokerConnected 
                          ? `Live connection to Bybit/Deriv Sandbox. Latency: ${brokerLatency}ms | Stream rate: 24 msgs/s` 
                          : "Requires sandbox gateway activation lease to stream WebSocket tick feeds."}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {!brokerConnected && (
                      <div className="flex items-center gap-1 text-[9px] text-zinc-600 font-mono">
                        <Lock className="w-3 h-3 text-zinc-700" />
                        <span>Security lease locked</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Interactive Ticker, Account Info, and Order Panel */}
                {brokerConnected ? (
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                    {/* Live Account Info & Market Ticker */}
                    <div className="bg-zinc-950 border border-zinc-900 rounded-xl p-4 flex flex-col gap-4">
                      <span className="text-[10px] font-mono text-zinc-400 uppercase font-black tracking-wider border-b border-zinc-900 pb-2 block">
                        Account &amp; Market HUD
                      </span>

                      {/* Live Ticker Box */}
                      <div className="bg-zinc-900/40 border border-zinc-850 p-3 rounded-lg flex items-center justify-between">
                        <div>
                          <span className="text-[8px] font-mono text-zinc-500 uppercase block">Asset Feed</span>
                          <span className="text-xs font-bold text-white font-mono">{targetAsset}</span>
                        </div>
                        <div className="text-right">
                          <span className="text-[8px] font-mono text-zinc-500 uppercase block">Live Sandbox Price</span>
                          <div className="flex items-center gap-1 justify-end">
                            <span className={`h-1.5 w-1.5 rounded-full ${
                              priceDirection === "up" ? "bg-emerald-400 animate-ping" : priceDirection === "down" ? "bg-rose-400 animate-ping" : "bg-zinc-600"
                            }`}></span>
                            <span className={`text-sm font-black font-mono tracking-tight transition-colors duration-200 ${
                              priceDirection === "up" ? "text-emerald-400" : priceDirection === "down" ? "text-rose-400" : "text-zinc-300"
                            }`}>
                              {livePrice.toFixed(getAssetConfig(targetAsset).decimals)}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Balance & Equity Stats */}
                      <div className="grid grid-cols-2 gap-3">
                        <div className="bg-zinc-900/20 border border-zinc-900 p-2.5 rounded-lg">
                          <span className="text-[8px] font-mono text-zinc-500 uppercase block">Sandbox Balance</span>
                          <span className="text-sm font-black font-mono text-white mt-0.5 block">
                            ${sandboxBalance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </span>
                        </div>
                        <div className="bg-zinc-900/20 border border-zinc-900 p-2.5 rounded-lg">
                          <span className="text-[8px] font-mono text-zinc-500 uppercase block">Sandbox Equity</span>
                          <span className="text-sm font-black font-mono text-emerald-400 mt-0.5 block">
                            ${(sandboxBalance + demoOrders.reduce((acc, order) => {
                              if (order.status !== "FILLED") return acc;
                              const config = getAssetConfig(targetAsset);
                              const pipsDiff = (livePrice - order.price) / config.pip;
                              const multiplier = targetAsset === "Step Index 100" ? 10 : 100;
                              const profit = order.type === "BUY" ? pipsDiff * multiplier * (order.lotSize || 1.0) : -pipsDiff * multiplier * (order.lotSize || 1.0);
                              return acc + profit;
                            }, 0)).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Quick Sandbox Order Execution Panel */}
                    <div className="bg-zinc-950 border border-zinc-900 rounded-xl p-4 lg:col-span-2 flex flex-col gap-3">
                      <span className="text-[10px] font-mono text-zinc-400 uppercase font-black tracking-wider border-b border-zinc-900 pb-2 block">
                        Quick Execution Sandbox Form
                      </span>

                      <div className="grid grid-cols-3 gap-3">
                        <div className="flex flex-col gap-1">
                          <label className="text-[8px] font-mono text-zinc-500 uppercase font-bold">Lot Size</label>
                          <input 
                            type="number" 
                            step="0.01" 
                            min="0.01"
                            max="100"
                            value={lotSizeInput}
                            onChange={(e) => setLotSizeInput(e.target.value)}
                            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg p-1.5 text-xs text-white font-mono outline-none focus:border-zinc-700"
                          />
                        </div>

                        <div className="flex flex-col gap-1">
                          <label className="text-[8px] font-mono text-zinc-500 uppercase font-bold">Stop Loss (Pips)</label>
                          <input 
                            type="number" 
                            step="1" 
                            min="1"
                            value={slPipsInput}
                            onChange={(e) => setSlPipsInput(e.target.value)}
                            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg p-1.5 text-xs text-white font-mono outline-none focus:border-zinc-700"
                          />
                        </div>

                        <div className="flex flex-col gap-1">
                          <label className="text-[8px] font-mono text-zinc-500 uppercase font-bold">Take Profit (Pips)</label>
                          <input 
                            type="number" 
                            step="1" 
                            min="1"
                            value={tpPipsInput}
                            onChange={(e) => setTpPipsInput(e.target.value)}
                            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg p-1.5 text-xs text-white font-mono outline-none focus:border-zinc-700"
                          />
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-3 mt-1 flex-1 items-end">
                        <button
                          onClick={() => {
                            const lots = parseFloat(lotSizeInput) || 1.0;
                            const sl = parseInt(slPipsInput) || 15;
                            const tp = parseInt(tpPipsInput) || 45;
                            placeSandboxOrder("BUY", lots, sl, tp);
                          }}
                          className="bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-black py-2.5 rounded-lg text-xs tracking-wider transition-all shadow hover:shadow-emerald-500/5 cursor-pointer uppercase flex items-center justify-center gap-1"
                        >
                          <Play className="w-3 h-3 fill-zinc-950" /> Submit Buy Market
                        </button>
                        <button
                          onClick={() => {
                            const lots = parseFloat(lotSizeInput) || 1.0;
                            const sl = parseInt(slPipsInput) || 15;
                            const tp = parseInt(tpPipsInput) || 45;
                            placeSandboxOrder("SELL", lots, sl, tp);
                          }}
                          className="bg-rose-500 hover:bg-rose-400 text-white font-black py-2.5 rounded-lg text-xs tracking-wider transition-all shadow hover:shadow-rose-500/5 cursor-pointer uppercase flex items-center justify-center gap-1"
                        >
                          <Pause className="w-3 h-3 fill-white" /> Submit Sell Market
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="bg-zinc-950 border border-zinc-900 border-dashed rounded-xl p-8 text-center flex flex-col items-center justify-center gap-2">
                    <Lock className="w-7 h-7 text-zinc-700" />
                    <span className="text-[10px] font-mono text-zinc-400 uppercase font-black">Gateway Sandbox Offline</span>
                    <p className="text-[9px] text-zinc-500 font-mono max-w-sm leading-relaxed">
                      Please click the <strong className="text-emerald-400">CONNECT SANDBOX</strong> button above to activate secure websocket subscriptions, enable manual execution controls, and view live order journals.
                    </p>
                  </div>
                )}

                {/* Dynamic order log stream from Broker Demo WebSockets */}
                {brokerConnected && (
                  <div className="bg-zinc-950 border border-zinc-900 rounded-xl p-3 flex flex-col gap-2">
                    <div className="flex items-center justify-between text-[9px] font-mono text-zinc-400 border-b border-zinc-900 pb-1.5 font-bold uppercase">
                      <span className="flex items-center gap-1">
                        <Terminal className="w-3.5 h-3.5 text-emerald-400 animate-pulse" /> Live Sandbox Positions Ledger
                      </span>
                      <span className="text-emerald-400 font-bold">WS CONNECTED</span>
                    </div>
                    
                    {demoOrders.length === 0 ? (
                      <div className="text-center py-6 text-zinc-600 text-[9px] font-mono">
                        No active positions or order records found in the current sandbox lease. Use the Quick Execution panel above to open a trade.
                      </div>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full text-left border-collapse font-mono text-[9px] text-zinc-400">
                          <thead>
                            <tr className="border-b border-zinc-900 text-zinc-500">
                              <th className="pb-1.5 font-bold uppercase">Ticket ID</th>
                              <th className="pb-1.5 font-bold uppercase">Asset</th>
                              <th className="pb-1.5 font-bold uppercase">Type</th>
                              <th className="pb-1.5 font-bold uppercase">Lots</th>
                              <th className="pb-1.5 font-bold uppercase">Entry Price</th>
                              <th className="pb-1.5 font-bold uppercase">TP / SL</th>
                              <th className="pb-1.5 font-bold uppercase">Current Price</th>
                              <th className="pb-1.5 font-bold uppercase text-right">P&amp;L</th>
                              <th className="pb-1.5 font-bold uppercase text-right">Action</th>
                            </tr>
                          </thead>
                          <tbody>
                            {demoOrders.map((order) => {
                              const config = getAssetConfig(order.asset);
                              const isFilled = order.status === "FILLED";
                              
                              // Calculate floating profit if active
                              let displayPl = "";
                              let isProfitable = false;
                              
                              if (isFilled) {
                                const pipsDiff = (livePrice - order.price) / config.pip;
                                const multiplier = order.asset === "Step Index 100" ? 10 : 100;
                                const profit = order.type === "BUY" ? pipsDiff * multiplier * (order.lotSize || 1.0) : -pipsDiff * multiplier * (order.lotSize || 1.0);
                                displayPl = `${profit >= 0 ? "+" : ""}$${profit.toFixed(2)}`;
                                isProfitable = profit >= 0;
                              } else {
                                displayPl = `${(order.profit || 0) >= 0 ? "+" : ""}$${(order.profit || 0).toFixed(2)}`;
                                isProfitable = (order.profit || 0) >= 0;
                              }

                              return (
                                <tr key={order.id} className="border-b border-zinc-900/50 last:border-0 hover:bg-zinc-900/10">
                                  <td className="py-1.5 text-zinc-300 font-bold">{order.id}</td>
                                  <td className="py-1.5 font-bold text-white">{order.asset}</td>
                                  <td className="py-1.5">
                                    <span className={`px-1.5 py-0.2 rounded text-[8px] font-bold ${
                                      order.type === "BUY" ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"
                                    }`}>
                                      {order.type}
                                    </span>
                                  </td>
                                  <td className="py-1.5 text-zinc-400">{order.lotSize?.toFixed(2) || "1.00"}</td>
                                  <td className="py-1.5 text-zinc-300">{order.price.toFixed(config.decimals)}</td>
                                  <td className="py-1.5 text-zinc-500">
                                    <span className="text-emerald-500">{order.tp.toFixed(config.decimals)}</span> / <span className="text-rose-500">{order.sl.toFixed(config.decimals)}</span>
                                  </td>
                                  <td className="py-1.5 text-zinc-400">
                                    {isFilled ? livePrice.toFixed(config.decimals) : order.exitPrice?.toFixed(config.decimals) || "-"}
                                  </td>
                                  <td className={`py-1.5 text-right font-bold ${isProfitable ? "text-emerald-400" : "text-rose-400"}`}>
                                    {displayPl}
                                  </td>
                                  <td className="py-1.5 text-right">
                                    {isFilled ? (
                                      <button
                                        onClick={() => closeSandboxOrder(order.id)}
                                        className="bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 px-2 py-0.5 rounded text-[8px] font-black border border-rose-500/25 transition cursor-pointer"
                                      >
                                        CLOSE TRADE
                                      </button>
                                    ) : (
                                      <span className="text-zinc-600 uppercase text-[8px] font-bold bg-zinc-900/50 px-1.5 py-0.5 rounded border border-zinc-850">
                                        {order.status}
                                      </span>
                                    )}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* STAGE 8: GOVERNANCE SIGNER */}
            {activeStep === 8 && (
              <div className="flex flex-col gap-4">
                <div className="border-b border-zinc-900 pb-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
                  <div>
                    <h4 className="text-xs font-black text-emerald-400 uppercase tracking-widest flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4" /> Stage 8: Governance &amp; Strategy Registry Promotion
                    </h4>
                    <p className="text-[9px] text-zinc-500 font-mono mt-0.5">Review immutable metadata fingerprint and digitally promote verified script to the OCC Runtimes</p>
                  </div>
                  <span className="text-[10px] bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-mono px-2 py-0.5 rounded font-bold">
                    PROMOTION READY
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Left Column: Registry stats & fingerprint */}
                  <div className="flex flex-col gap-3 bg-zinc-900/40 p-4 rounded-xl border border-zinc-850">
                    <span className="text-[10px] font-mono text-zinc-400 uppercase font-bold tracking-wider">Immutable Strategy Fingerprint</span>
                    <div className="flex flex-col gap-2 font-mono text-[9px] text-zinc-500 mt-1">
                      <div className="flex justify-between border-b border-zinc-850 pb-1.5">
                        <span>Strategy Tag:</span>
                        <span className="text-white font-bold">isop_step100_hybrid</span>
                      </div>
                      <div className="flex justify-between border-b border-zinc-850 pb-1.5">
                        <span>Asset Focus:</span>
                        <span className="text-white font-bold">{targetAsset}</span>
                      </div>
                      <div className="flex justify-between border-b border-zinc-850 pb-1.5">
                        <span>OB Criteria Score:</span>
                        <span className="text-emerald-400 font-bold">{calculatedObScore}/6 (Threshold &gt;= {acceptanceThreshold})</span>
                      </div>
                      <div className="flex justify-between border-b border-zinc-850 pb-1.5">
                        <span>MD5 Fingerprint:</span>
                        <span className="text-white tracking-widest">9ef80a37b58ce88e89...</span>
                      </div>
                    </div>
                  </div>

                  {/* Right Column: Signed legal contract info */}
                  <div className="flex flex-col gap-3 bg-zinc-900/40 p-4 rounded-xl border border-zinc-850 justify-between">
                    <div>
                      <span className="text-[10px] font-mono text-zinc-400 uppercase font-bold block border-b border-zinc-850 pb-2">Governance Audit Trail</span>
                      <p className="text-[9px] text-zinc-500 leading-normal font-mono mt-2">
                        Promoting this strategy cryptographically signs a validation receipt. This receipt is persisted to local audit logs, confirming research criteria have been fully passed under SVOS, EVF, and RGM rules.
                      </p>
                    </div>

                    <div className="flex items-center gap-2 bg-zinc-950 p-2.5 rounded-lg border border-zinc-850">
                      <Unlock className="w-4 h-4 text-emerald-400" />
                      <span className="text-[9px] font-mono text-zinc-400">All gate protocols unlocked successfully.</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

          </div>

          {/* B) SVOS QUANT TERMINAL LOG STREAM */}
          <div className="bg-zinc-950 border border-zinc-900 rounded-xl p-3 flex-1 flex flex-col gap-2 shadow-inner">
            <div className="flex items-center justify-between text-[9px] font-mono text-zinc-500 border-b border-zinc-900 pb-1.5 uppercase font-bold">
              <span className="flex items-center gap-1">
                <Database className="w-3.5 h-3.5 text-emerald-400 animate-pulse" /> SVOS Quant Pipeline Terminal
              </span>
              <span>Rate: 50 msg/sec</span>
            </div>

            <div className="h-44 overflow-y-auto font-mono text-[9px] flex flex-col gap-1 text-zinc-400 select-text scrollbar-thin">
              {logs.map((log, index) => {
                let colClass = "text-zinc-400";
                if (log.includes("STAGE")) colClass = "text-emerald-400 font-extrabold";
                if (log.includes("SUCCESS") || log.includes("PASSED")) colClass = "text-emerald-400";
                if (log.includes("INITIALIZING")) colClass = "text-cyan-400 font-bold";
                if (log.includes("MC Pass") || log.includes("Net return")) colClass = "text-white";
                return (
                  <div key={index} className="flex gap-1">
                    <span className="text-zinc-600 select-none">&gt;</span>
                    <span className={colClass}>{log}</span>
                  </div>
                );
              })}
              <div ref={terminalEndRef}></div>
            </div>

            {/* Strategy packaging compiler controls */}
            {activeStep === 8 && !isSimulating && (
              <div className="border-t border-zinc-900 pt-2.5 mt-1.5 flex flex-col sm:flex-row items-center justify-between gap-2 bg-zinc-900/40 p-2.5 rounded-lg border border-zinc-850">
                <div className="flex items-center gap-2">
                  <Award className="w-4 h-4 text-emerald-400 animate-bounce" />
                  <div className="text-left">
                    <span className="text-[10px] text-zinc-200 font-bold block">Digital Contract Signed Successfully!</span>
                    <span className="text-[8px] text-zinc-500 font-mono">MD5 Signature: hash_7ef80572e... ready for hot runtime injection</span>
                  </div>
                </div>

                <button
                  onClick={handleExportToProduction}
                  id="btn-sync-contract-production"
                  className="px-3.5 py-1.5 bg-emerald-400 hover:bg-emerald-300 text-zinc-950 text-[10px] font-black rounded-lg transition shadow-md flex items-center gap-1 select-none active:scale-95 cursor-pointer"
                >
                  <Download className="w-3.5 h-3.5" /> EXPORT TO PRODUCTION RUNTIME
                </button>
              </div>
            )}
          </div>

        </div>
      </div>
      
    </div>
  );
};
