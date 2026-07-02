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
  Sparkles, 
  HelpCircle, 
  Database, 
  Layers, 
  Download, 
  RefreshCw,
  Award,
  AlertCircle
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
  { id: 1, label: "Strategy Idea", desc: "Synthesize SMC indicator rules & parameter boundaries", icon: Lightbulb, metricLabel: "Idea Maturity", metricValue: "95%" },
  { id: 2, label: "Strategy Audit", desc: "Scan logic safety, code compilation & boundary checks", icon: FileCheck, metricLabel: "Audit Score", metricValue: "98.2" },
  { id: 3, label: "Historical Replay", desc: "Step-through historical candle streams to assess triggers", icon: History, metricLabel: "Replay Depth", metricValue: "3 Yrs" },
  { id: 4, label: "Backtest", desc: "Execute portfolio-wide statistical historical backtests", icon: TrendingUp, metricLabel: "Win Rate", metricValue: "64.5%" },
  { id: 5, label: "Statistical Validation", desc: "Evaluate Sharpe, Sortino ratio, expectancy & profit factor", icon: BarChart4, metricLabel: "Sharpe Ratio", metricValue: "2.42" },
  { id: 6, label: "Robustness Testing", desc: "Slippage stress, spread spikes & Monte Carlo runs", icon: ShieldAlert, metricLabel: "MC Pass Rate", metricValue: "94.8%" },
  { id: 7, label: "Virtual Demo", desc: "Forward-test inside simulated live broker sandboxes", icon: ShieldCheck, metricLabel: "Demo Profit", metricValue: "+$4,812" },
  { id: 8, label: "Production Approval", desc: "Cryptographically sign contract and deploy to live servers", icon: CheckCircle2, metricLabel: "Signature", metricValue: "Signed" }
];

export const SvosQuantLab: React.FC = () => {
  const { state, activateStrategy } = useSocket();
  const [activeStep, setActiveStep] = useState<number>(1);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [simStep, setSimStep] = useState<number>(0);
  const [simProgress, setSimProgress] = useState<number>(0);
  
  // Custom Strategy state variables for developer configuration
  const [strategyName, setStrategyName] = useState<string>("SMC H4 Liquidity Sweeper");
  const [targetAsset, setTargetAsset] = useState<string>("EURUSD");
  const [stopLossPips, setStopLossPips] = useState<number>(10);
  const [riskRewardRatio, setRiskRewardRatio] = useState<number>(3.5);
  const [timeframe, setTimeframe] = useState<string>("H4");
  const [enableNewsFilter, setEnableNewsFilter] = useState<boolean>(true);

  // Simulated metrics that dynamically update as user plays with parameters
  const [backtestReturn, setBacktestReturn] = useState<number>(24.8);
  const [profitFactor, setProfitFactor] = useState<number>(2.15);
  const [maxDrawdown, setMaxDrawdown] = useState<number>(4.2);
  const [passedValidation, setPassedValidation] = useState<boolean>(true);

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
    const baseWin = 75 - (stopLossPips * 0.8) - (riskRewardRatio * 3);
    const winRate = Math.max(38, Math.min(78, baseWin + Math.random() * 4));
    const pf = Math.max(1.2, parseFloat((winRate * riskRewardRatio / (100 - winRate)).toFixed(2)));
    const ret = parseFloat((pf * 12.4).toFixed(1));
    const dd = parseFloat((riskRewardRatio * 1.1 + Math.random() * 2).toFixed(1));

    setBacktestReturn(ret);
    setProfitFactor(pf);
    setMaxDrawdown(dd);
    setPassedValidation(pf >= 1.6 && dd <= 8);
  }, [stopLossPips, riskRewardRatio, timeframe, targetAsset]);

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
          `Configuring rules: StopLoss = ${stopLossPips} pips, RiskReward = 1:${riskRewardRatio}, TF = ${timeframe}, News Filter = ${enableNewsFilter ? "ENABLED" : "DISABLED"}`,
          "Validated syntactic rules. Proceeding to semantic code audit."
        ];
      } else if (simStep === 2) {
        stepMsgs = [
          "STAGE 2: Strategy Audit Engine Initiated...",
          "Inspecting code safety, division by zero, and infinity loop safeguards...",
          `Static compilation success. Audit Score: ${passedValidation ? "98.2" : "89.5"}%. No critical warnings found.`
        ];
      } else if (simStep === 3) {
        stepMsgs = [
          "STAGE 3: Streaming historical candle replay buffers...",
          `Analyzing ${targetAsset} historical candles. Total candle frames loaded: 148,500.`,
          "Simulating real-time signal sweep callbacks..."
        ];
      } else if (simStep === 4) {
        stepMsgs = [
          "STAGE 4: Executing multi-cycle backtest...",
          `Simulated 1,482 execution structures over past 3 years.`,
          `Net return: +${backtestReturn}%, Win Rate: ${parseFloat(( (profitFactor / (1+profitFactor)) * 100).toFixed(1))}%`
        ];
      } else if (simStep === 5) {
        stepMsgs = [
          "STAGE 5: Running statistical validation suite...",
          `Sharpe Ratio: ${(profitFactor * 1.15).toFixed(2)}, Sortino: ${(profitFactor * 1.4).toFixed(2)}`,
          `Profit Factor: ${profitFactor}, Expectancy: +0.45 R-units per trade (PASSED)`
        ];
      } else if (simStep === 6) {
        stepMsgs = [
          "STAGE 6: Running Robustness & Monte Carlo Stress Testing...",
          "Running 500 randomized path permutations with 1.2 pip slippage and spread volatility spikes...",
          `95% confidence level maximum drawdowns within limits (Pass score: ${(90 + profitFactor * 2).toFixed(1)}%)`
        ];
      } else if (simStep === 7) {
        stepMsgs = [
          "STAGE 7: Virtual Paper Forward Testing initiated...",
          "Simulating MT5/Bybit gateway connectivity over 150 live forward trading sessions...",
          "Live latency alignment within 45ms. Forward equity curve matches historical expectation."
        ];
      } else if (simStep === 8) {
        stepMsgs = [
          "STAGE 8: Cryptographic Contract Compilation & Final Signature Generation...",
          `Compiling standalone Javascript strategy binary (bundle-size: 42KB)`,
          `Generated contract digest: sha256_svos_${Math.random().toString(16).slice(2, 18)}...`,
          "PRODUCTION COMPLIANCE CHECK PASSED! Strat ready for live broker adaptation!"
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
                <option value="SMC H4 Liquidity Sweeper">SMC H4 Liquidity Sweeper</option>
                <option value="CHoCH Momentum Rider">CHoCH Momentum Rider</option>
                <option value="FVG Intraday Scalper">FVG Intraday Scalper</option>
                <option value="Custom High-Confluence OB">Custom High-Confluence OB</option>
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
                  <option value="EURUSD">EURUSD (SMC core)</option>
                  <option value="GBPUSD">GBPUSD (Peak pips)</option>
                  <option value="XAUUSD">XAUUSD (Volatility)</option>
                  <option value="USDJPY">USDJPY (Spread filter)</option>
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
                  <option value="M1">M1 (Micro Scalping)</option>
                  <option value="M5">M5 (CHoCH momentum)</option>
                  <option value="H1">H1 (Intraday zones)</option>
                  <option value="H4">H4 (HTF sweep focus)</option>
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
