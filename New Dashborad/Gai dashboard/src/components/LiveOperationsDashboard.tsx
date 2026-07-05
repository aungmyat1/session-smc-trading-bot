import React, { useState, useEffect, useRef } from "react";
import { useSocket } from "../context/SocketContext.js";
import { LiveChart } from "./LiveChart.js";
import { StrategyRuntimeStatus } from "./StrategyRuntimeStatus.js";
import { TradeExecutionHistory } from "./TradeExecutionHistory.js";
import { 
  ShieldCheck, 
  ShieldAlert, 
  Play, 
  Pause, 
  Settings, 
  Activity, 
  Zap, 
  TrendingUp, 
  Database, 
  Cpu, 
  AlertOctagon, 
  Globe, 
  RefreshCw, 
  CheckCircle, 
  XCircle, 
  ArrowRight,
  TrendingDown,
  Lock,
  FileCode,
  Sliders,
  ChevronDown,
  Search,
  Filter,
  Radio,
  Terminal,
  ChevronRight
} from "lucide-react";

export const LiveOperationsDashboard: React.FC = () => {
  const { 
    state, 
    isConnected, 
    forceCloseTrade,
    activateStrategy,
    pauseStrategy,
    triggerKillSwitch,
    updateRiskControls,
    reconnectBroker,
    selectPair
  } = useSocket();

  // Selected package for deployment
  const [selectedPkgId, setSelectedPkgId] = useState<string>("svos_sweeper_h4");
  const [deployBroker, setDeployBroker] = useState<"Bybit" | "MT5" | "Binance">("Bybit");
  const [deploySymbols, setDeploySymbols] = useState<string[]>(["EURUSD", "GBPUSD"]);
  const [deployRisk, setDeployRisk] = useState<"Low" | "Medium" | "Aggressive">("Low");

  // Risk control state inputs
  const [riskMaxLoss, setRiskMaxLoss] = useState<number>(2.5);
  const [riskMaxPos, setRiskMaxPos] = useState<number>(3);
  const [riskLeverage, setRiskLeverage] = useState<string>("1:100");
  const [riskNews, setRiskNews] = useState<boolean>(true);
  const [riskLatency, setRiskLatency] = useState<boolean>(true);
  const [riskLossLimit, setRiskLossLimit] = useState<boolean>(true);

  // Filter for real-time console
  const [logFilter, setLogFilter] = useState<string>("ALL");
  const [logSearch, setLogSearch] = useState<string>("");

  const consoleEndRef = useRef<HTMLDivElement | null>(null);

  // Execution Mode Switch (Automated Bot vs. Manual Sandbox)
  const [executionMode, setExecutionMode] = useState<"AUTOMATED" | "MANUAL">("AUTOMATED");

  // Manual Sandbox Trader states
  const [brokerConnected, setBrokerConnected] = useState<boolean>(false);
  const [brokerLatency, setBrokerLatency] = useState<number>(42);
  const [sandboxBalance, setSandboxBalance] = useState<number>(10000);
  const [lotSizeInput, setLotSizeInput] = useState<string>("1.00");
  const [slPipsInput, setSlPipsInput] = useState<string>("15");
  const [tpPipsInput, setTpPipsInput] = useState<string>("45");
  const [sandboxLogs, setSandboxLogs] = useState<string[]>([
    "System: Sandbox Manual execution gateway ready.",
    "Ready to trade manually on virtual websockets connected to live prices. Change instrument above and select Buy/Sell."
  ]);
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

  const addSandboxLog = (msg: string) => {
    setSandboxLogs(prev => [...prev, `[${new Date().toISOString().slice(11, 19)}] ${msg}`]);
  };

  // Sync risk state when state loads. The real backend's riskControls (from
  // strategy_portfolio.yaml's risk limits) has no maxLeverage or
  // autoDisableConditions concept — that's an operator-controls editing
  // feature not yet backed by any API (SYSTEM2_MASTER_PLAN.md "Operator
  // Controls" milestone). Defaulting rather than crashing on the missing
  // fields; values stay display-only until that milestone lands.
  useEffect(() => {
    if (state?.riskControls) {
      const autoDisable = state.riskControls.autoDisableConditions;
      setRiskMaxLoss(state.riskControls.maxDailyLoss ?? 0);
      setRiskMaxPos(state.riskControls.maxOpenPositions ?? 0);
      setRiskLeverage(state.riskControls.maxLeverage ?? "N/A");
      setRiskNews(autoDisable?.newsEvent ?? false);
      setRiskLatency(autoDisable?.latencySpike ?? false);
      setRiskLossLimit(autoDisable?.lossExceeded ?? false);
    }
  }, [state?.riskControls]);

  // Auto-scroll console logs to bottom when new logs arrive
  useEffect(() => {
    if (consoleEndRef.current) {
      consoleEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [state?.events]);

  if (!state) return null;

  const selectedPairState = state.pairs[state.selectedPair] || Object.values(state.pairs)[0];

  // Calculate live unrealized PnL
  const activeTrade = state.activeTrade;
  let runningPnL = 0;
  let marginLocked = 0;
  if (activeTrade && selectedPairState) {
    const currentPrice = selectedPairState.price;
    const isBuy = activeTrade.type === "BUY";
    const diff = isBuy ? (currentPrice - activeTrade.entry) : (activeTrade.entry - currentPrice);
    runningPnL = parseFloat((diff * activeTrade.lotSize * 100000).toFixed(2));
    marginLocked = 1240.00;
  }

  // Asset config for manual sandbox
  const getAssetConfig = (symbol: string) => {
    switch (symbol) {
      case "EURUSD":
        return { base: 1.0820, pip: 0.0001, decimals: 4, label: "EUR/USD" };
      case "GBPUSD":
        return { base: 1.2750, pip: 0.0001, decimals: 4, label: "GBP/USD" };
      case "XAUUSD":
        return { base: 2335.0, pip: 0.1, decimals: 2, label: "XAU/USD" };
      case "USDJPY":
        return { base: 156.20, pip: 0.01, decimals: 2, label: "USD/JPY" };
      case "Step Index 100":
      default:
        return { base: 11245.0, pip: 1.0, decimals: 1, label: "Step Index 100" };
    }
  };

  // Live price ticker simulation when broker is connected
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (brokerConnected) {
      interval = setInterval(() => {
        setBrokerLatency(prev => Math.max(15, Math.min(180, prev + Math.floor((Math.random() - 0.5) * 15))));
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [brokerConnected]);

  // Calculate Sandbox Floating PnL
  const sandboxPnL = demoOrders.reduce((acc, order) => {
    if (order.status !== "FILLED") return acc;
    const config = getAssetConfig(order.asset);
    const pairData = state.pairs[order.asset];
    const currentPrice = pairData ? pairData.price : order.price;
    const pipsDiff = (currentPrice - order.price) / config.pip;
    const multiplier = order.asset === "Step Index 100" ? 10 : 100;
    const profit = order.type === "BUY" ? pipsDiff * multiplier * (order.lotSize || 1.0) : -pipsDiff * multiplier * (order.lotSize || 1.0);
    return acc + profit;
  }, 0);

  const totalSandboxEquity = sandboxBalance + sandboxPnL;
  const activeSandboxOrdersCount = demoOrders.filter(o => o.status === "FILLED").length;

  const placeSandboxOrder = (type: "BUY" | "SELL", customLotSize: number, customSlPips: number, customTpPips: number) => {
    if (!brokerConnected) return;
    const symbol = state.selectedPair;
    const config = getAssetConfig(symbol);
    const orderId = `TX-${Math.floor(1000 + Math.random() * 9000)}`;
    const price = selectedPairState?.price || config.base;
    
    // Calculate TP and SL prices
    const slPrice = type === "BUY" ? price - customSlPips * config.pip : price + customSlPips * config.pip;
    const tpPrice = type === "BUY" ? price + customTpPips * config.pip : price - customTpPips * config.pip;
    
    addSandboxLog(`[WS SEND] Placing Market Order: ${type} ${customLotSize.toFixed(2)} lots on ${symbol} at ${price.toFixed(config.decimals)}`);
    
    setTimeout(() => {
      const newOrder = {
        id: orderId,
        asset: symbol,
        time: new Date().toISOString().replace("T", " ").slice(0, 19),
        type,
        price,
        tp: tpPrice,
        sl: slPrice,
        status: "FILLED",
        lotSize: customLotSize
      };
      
      setDemoOrders(prev => [newOrder, ...prev]);
      addSandboxLog(`[WS RECV] Order ${orderId} executed! Status: FILLED at ${price.toFixed(config.decimals)}. Latency: ${brokerLatency}ms`);
    }, 180);
  };

  const closeSandboxOrder = (id: string) => {
    const order = demoOrders.find(o => o.id === id);
    if (!order) return;
    const config = getAssetConfig(order.asset);
    
    // Simulate current exit price
    const pairData = state.pairs[order.asset];
    const exitPrice = pairData ? pairData.price : order.price;
    const pipsDiff = (exitPrice - order.price) / config.pip;
    
    // Calculate P&L: lotSize * pipsDiff * multiplier
    const multiplier = order.asset === "Step Index 100" ? 10 : 100;
    const rawProfit = order.type === "BUY" ? pipsDiff * multiplier * (order.lotSize || 1) : -pipsDiff * multiplier * (order.lotSize || 1);
    const profit = parseFloat(rawProfit.toFixed(2));
    
    addSandboxLog(`[WS SEND] Requesting Market Close for Order ${id}`);
    
    setTimeout(() => {
      setDemoOrders(prev => prev.map(o => {
        if (o.id === id) {
          return { ...o, status: "CLOSED", exitPrice, profit };
        }
        return o;
      }));
      setSandboxBalance(prev => parseFloat((prev + profit).toFixed(2)));
      addSandboxLog(`[WS RECV] Order ${id} closed successfully! Realized P&L: ${profit >= 0 ? "+" : ""}$${profit}`);
    }, 120);
  };

  // Handle deploying a strategy
  const handleDeploy = async () => {
    const pkg = state.strategyPackages.find(p => p.id === selectedPkgId);
    if (pkg) {
      await activateStrategy(
        selectedPkgId,
        deployBroker,
        deploySymbols,
        deployRisk,
        pkg.version
      );
    }
  };

  // Handle saving risk controls
  const handleSaveRisk = async () => {
    await updateRiskControls(
      riskMaxLoss,
      riskMaxPos,
      riskLeverage,
      {
        newsEvent: riskNews,
        latencySpike: riskLatency,
        lossExceeded: riskLossLimit
      }
    );
  };

  // Toggle symbols for deployment selector
  const toggleSymbol = (sym: string) => {
    if (deploySymbols.includes(sym)) {
      if (deploySymbols.length > 1) {
        setDeploySymbols(deploySymbols.filter(s => s !== sym));
      }
    } else {
      setDeploySymbols([...deploySymbols, sym]);
    }
  };

  // Get filtered event logs
  const filteredEvents = state.events.filter(evt => {
    const matchesSearch = evt.message.toLowerCase().includes(logSearch.toLowerCase()) || 
                          evt.level.toLowerCase().includes(logSearch.toLowerCase());
    if (logFilter === "ALL") return matchesSearch;
    return evt.level === logFilter && matchesSearch;
  });

  return (
    <div className="w-full flex flex-col gap-6" id="live-operations-dashboard">
      
      {/* Dynamic Execution Mode Controller */}
      <div className="flex flex-col sm:flex-row items-center justify-between p-2 bg-zinc-900 border border-zinc-800/80 rounded-2xl gap-3 shadow-xl">
        <div className="pl-2">
          <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest font-extrabold block">Execution Gateway Switch</span>
          <p className="text-[11px] text-zinc-300 font-sans mt-0.5">
            Select <strong className="text-emerald-400">Automated Bot Core</strong> to deploy/manage bots or <strong className="text-teal-400">Manual Sandbox Trader</strong> for instant paper trading.
          </p>
        </div>
        <div className="flex items-center gap-1.5 bg-zinc-950 p-1 rounded-xl border border-zinc-850 font-mono text-[11px] font-bold shrink-0 w-full sm:w-auto">
          <button
            onClick={() => setExecutionMode("AUTOMATED")}
            className={`flex-1 sm:flex-initial px-4 py-2 rounded-lg cursor-pointer transition flex items-center justify-center gap-2 ${
              executionMode === "AUTOMATED" 
                ? "bg-emerald-500 text-zinc-950 font-black shadow-lg shadow-emerald-500/10" 
                : "text-zinc-400 hover:text-zinc-100"
            }`}
          >
            <Cpu className="w-3.5 h-3.5" /> AUTOMATED BOTS
          </button>
          <button
            onClick={() => setExecutionMode("MANUAL")}
            className={`flex-1 sm:flex-initial px-4 py-2 rounded-lg cursor-pointer transition flex items-center justify-center gap-2 ${
              executionMode === "MANUAL" 
                ? "bg-teal-500 text-zinc-950 font-black shadow-lg shadow-teal-500/10" 
                : "text-zinc-400 hover:text-zinc-100"
            }`}
          >
            <Radio className="w-3.5 h-3.5" /> MANUAL SANDBOX
          </button>
        </div>
      </div>

      {/* 1. TOP ROW METRICS */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" id="top-metrics-row">
        {executionMode === "AUTOMATED" ? (
          <>
            {/* Active PnL Card */}
            <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-xl relative overflow-hidden flex flex-col justify-between min-h-[110px]">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">Unrealized Active PnL</span>
                <Activity className={`w-4 h-4 ${runningPnL >= 0 ? "text-emerald-400" : "text-rose-400 animate-pulse"}`} />
              </div>
              <div className="mt-2 flex items-baseline gap-1.5">
                <span className={`text-2xl font-black font-mono tracking-tight ${runningPnL > 0 ? "text-emerald-400" : runningPnL < 0 ? "text-rose-400" : "text-zinc-500"}`}>
                  {runningPnL > 0 ? `+$${runningPnL.toLocaleString()}` : runningPnL < 0 ? `-$${Math.abs(runningPnL).toLocaleString()}` : "$0.00"}
                </span>
                {activeTrade && (
                  <span className="text-[10px] font-mono text-zinc-500">
                    ({activeTrade.lotSize} Lots {activeTrade.type})
                  </span>
                )}
              </div>
              <div className="text-[10px] text-zinc-500 font-mono flex items-center gap-1">
                <span className={`w-1.5 h-1.5 rounded-full ${activeTrade ? "bg-emerald-500 animate-ping" : "bg-zinc-600"}`}></span>
                {activeTrade ? "Live position risk-exposure active" : "No open risk — Systems idle"}
              </div>
            </div>

            {/* Margin Card */}
            <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-xl relative overflow-hidden flex flex-col justify-between min-h-[110px]">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">Running Margin</span>
                <Lock className="w-4 h-4 text-zinc-500" />
              </div>
              <div className="mt-2">
                <span className="text-2xl font-black font-mono text-white tracking-tight">
                  ${marginLocked.toFixed(2)}
                </span>
              </div>
              <div className="text-[10px] text-zinc-500 font-mono">
                {activeTrade ? "Lease Leverage Locked: 1:100" : "Leverage headroom: 100.0% available"}
              </div>
            </div>

            {/* Risk Used Card */}
            <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-xl relative overflow-hidden flex flex-col justify-between min-h-[110px]">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">Daily Risk Used</span>
                <Sliders className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="mt-2">
                <div className="flex items-baseline justify-between mb-1.5">
                  <span className="text-2xl font-black font-mono text-emerald-400 tracking-tight">
                    {state.analytics.dailyRiskUsed.toFixed(1)}%
                  </span>
                  <span className="text-[10px] font-mono text-zinc-500">Max limit: {riskMaxLoss}%</span>
                </div>
                {/* Simple Progress Bar */}
                <div className="w-full h-1.5 bg-zinc-950 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-emerald-500 transition-all duration-500"
                    style={{ width: `${Math.min((state.analytics.dailyRiskUsed / riskMaxLoss) * 100, 100)}%` }}
                  ></div>
                </div>
              </div>
              <div className="text-[10px] text-zinc-500 font-mono flex items-center justify-between">
                <span>Risk allowance secure</span>
                <span>{Math.max(0, riskMaxLoss - state.analytics.dailyRiskUsed).toFixed(1)}% left</span>
              </div>
            </div>

            {/* Broker Latency Card */}
            <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-xl relative overflow-hidden flex flex-col justify-between min-h-[110px]">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">Broker Gateway Link</span>
                <Globe className={`w-4 h-4 ${state.brokerConnection.status === "CONNECTED" ? "text-emerald-400" : "text-rose-500 animate-pulse"}`} />
              </div>
              <div className="mt-2 flex items-baseline justify-between">
                <span className="text-2xl font-black font-mono text-white tracking-tight">
                  {state.brokerConnection.latency}ms
                </span>
                <span className="text-[10px] font-mono text-zinc-400 bg-zinc-950/80 px-1.5 py-0.5 rounded border border-zinc-800">
                  {state.brokerConnection.apiCalls} API Calls
                </span>
              </div>
              <div className="text-[10px] text-zinc-500 font-mono flex items-center justify-between">
                <span className="flex items-center gap-1">
                  <span className={`w-1.5 h-1.5 rounded-full ${state.brokerConnection.status === "CONNECTED" ? "bg-emerald-500" : "bg-rose-500"}`}></span>
                  Gateway: {state.brokerConnection.status}
                </span>
                <span>Rate: 99.4%</span>
              </div>
            </div>
          </>
        ) : (
          <>
            {/* Sandbox Floating PnL Card */}
            <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-xl relative overflow-hidden flex flex-col justify-between min-h-[110px]">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">Sandbox Floating PnL</span>
                <Activity className={`w-4 h-4 ${sandboxPnL >= 0 ? "text-teal-400" : "text-rose-400 animate-pulse"}`} />
              </div>
              <div className="mt-2 flex items-baseline gap-1.5">
                <span className={`text-2xl font-black font-mono tracking-tight ${sandboxPnL > 0 ? "text-teal-400" : sandboxPnL < 0 ? "text-rose-400" : "text-zinc-500"}`}>
                  {sandboxPnL > 0 ? `+$${sandboxPnL.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}` : sandboxPnL < 0 ? `-$${Math.abs(sandboxPnL).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}` : "$0.00"}
                </span>
              </div>
              <div className="text-[10px] text-zinc-500 font-mono flex items-center gap-1">
                <span className={`w-1.5 h-1.5 rounded-full ${activeSandboxOrdersCount > 0 ? "bg-teal-400 animate-ping" : "bg-zinc-600"}`}></span>
                {activeSandboxOrdersCount > 0 ? `${activeSandboxOrdersCount} manual risk-exposure open` : "No manual risk — Sandbox idle"}
              </div>
            </div>

            {/* Sandbox Balance Card */}
            <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-xl relative overflow-hidden flex flex-col justify-between min-h-[110px]">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">Sandbox Balance</span>
                <Lock className="w-4 h-4 text-teal-400" />
              </div>
              <div className="mt-2">
                <span className="text-2xl font-black font-mono text-white tracking-tight">
                  ${sandboxBalance.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                </span>
              </div>
              <div className="text-[10px] text-zinc-500 font-mono">
                Equity: ${totalSandboxEquity.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
              </div>
            </div>

            {/* Sandbox Orders Limit Card */}
            <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-xl relative overflow-hidden flex flex-col justify-between min-h-[110px]">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">Open Positions Limit</span>
                <Sliders className="w-4 h-4 text-teal-400" />
              </div>
              <div className="mt-2">
                <div className="flex items-baseline justify-between mb-1.5">
                  <span className="text-2xl font-black font-mono text-teal-400 tracking-tight">
                    {activeSandboxOrdersCount} / {riskMaxPos}
                  </span>
                  <span className="text-[10px] font-mono text-zinc-500">Max Open: {riskMaxPos}</span>
                </div>
                {/* Simple Progress Bar */}
                <div className="w-full h-1.5 bg-zinc-950 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-teal-500 transition-all duration-500"
                    style={{ width: `${Math.min((activeSandboxOrdersCount / riskMaxPos) * 100, 100)}%` }}
                  ></div>
                </div>
              </div>
              <div className="text-[10px] text-zinc-500 font-mono flex items-center justify-between">
                <span>Risk buffer secure</span>
                <span>{Math.max(0, riskMaxPos - activeSandboxOrdersCount)} slots open</span>
              </div>
            </div>

            {/* Sandbox Socket Link Card */}
            <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-xl relative overflow-hidden flex flex-col justify-between min-h-[110px]">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">Sandbox API Gateway</span>
                <Globe className={`w-4 h-4 ${brokerConnected ? "text-teal-400" : "text-zinc-600"}`} />
              </div>
              <div className="mt-2 flex items-baseline justify-between">
                <span className="text-2xl font-black font-mono text-white tracking-tight">
                  {brokerConnected ? `${brokerLatency}ms` : "OFFLINE"}
                </span>
                <span className="text-[10px] font-mono text-zinc-400 bg-zinc-950/80 px-1.5 py-0.5 rounded border border-zinc-800">
                  {brokerConnected ? "WebSockets streaming" : "Inactive gateway"}
                </span>
              </div>
              <div className="text-[10px] text-zinc-500 font-mono flex items-center justify-between">
                <span className="flex items-center gap-1">
                  <span className={`w-1.5 h-1.5 rounded-full ${brokerConnected ? "bg-teal-400 animate-pulse" : "bg-zinc-600"}`}></span>
                  {brokerConnected ? "Connected (Paper)" : "Disconnected"}
                </span>
                <span>Live Feed</span>
              </div>
            </div>
          </>
        )}
      </div>

      {/* 2. BENTO STAGE WITH LEFT SIDEBAR */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6" id="bento-operations-stage">
        
        {/* LEFT COLUMN: OPERATOR SIDEBAR (Col span 1) */}
        <div className="xl:col-span-1 flex flex-col gap-6" id="operator-sidebar">
          
          {executionMode === "AUTOMATED" ? (
            <>
              {/* A) LIVE POSITIONS PANEL */}
              <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-xl flex flex-col gap-4 relative" id="live-positions-panel">
                <div className="flex items-center justify-between border-b border-zinc-800/60 pb-3">
                  <h3 className="text-xs font-extrabold text-white tracking-wider uppercase flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${activeTrade ? "bg-emerald-500 animate-ping" : "bg-zinc-600"}`}></span>
                    Live Positions
                  </h3>
                  <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded ${activeTrade ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-zinc-950 text-zinc-500 border border-zinc-850"}`}>
                    {activeTrade ? "RISK ON" : "IDLE"}
                  </span>
                </div>

                {activeTrade && selectedPairState ? (
                  <div className="flex flex-col gap-3.5">
                    {/* Meta details */}
                    <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                      <div className="bg-zinc-950/40 border border-zinc-850 p-2 rounded-xl">
                        <div className="text-zinc-500 text-[9px] uppercase font-bold">Instrument</div>
                        <div className="text-white font-extrabold mt-0.5">{state.selectedPair}</div>
                      </div>
                      <div className="bg-zinc-950/40 border border-zinc-850 p-2 rounded-xl">
                        <div className="text-zinc-500 text-[9px] uppercase font-bold">Position Size</div>
                        <div className="text-white font-extrabold mt-0.5">{activeTrade.lotSize} Lots</div>
                      </div>
                    </div>

                    <div className="bg-zinc-950/40 border border-zinc-850 p-3 rounded-xl flex flex-col gap-2 font-mono text-xs">
                      <div className="flex justify-between">
                        <span className="text-zinc-500">Entry Price:</span>
                        <span className="text-zinc-300 font-bold">{activeTrade.entry.toFixed(5)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-zinc-500">Current Price:</span>
                        <span className="text-white font-bold animate-pulse">{selectedPairState.price.toFixed(5)}</span>
                      </div>
                      <div className="flex justify-between border-t border-zinc-800/50 pt-1.5 mt-0.5">
                        <span className="text-rose-400 font-semibold">Stop Loss:</span>
                        <span className="text-rose-400/90 font-bold">{activeTrade.sl.toFixed(5)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-emerald-400 font-semibold">Take Profit:</span>
                        <span className="text-emerald-400/90 font-bold">{activeTrade.tp.toFixed(5)}</span>
                      </div>
                    </div>

                    {/* Unrealized PnL Meter */}
                    <div className="bg-zinc-950/80 border border-zinc-850 p-3 rounded-xl flex flex-col gap-1.5 font-mono text-center">
                      <span className="text-[9px] text-zinc-500 uppercase tracking-widest font-bold">Unrealized Net PnL</span>
                      <span className={`text-xl font-black ${runningPnL >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {runningPnL >= 0 ? `+$${runningPnL.toFixed(2)}` : `-$${Math.abs(runningPnL).toFixed(2)}`}
                      </span>
                      <div className="w-full h-1 bg-zinc-900 rounded-full overflow-hidden mt-1">
                        <div 
                          className={`h-full transition-all duration-300 ${runningPnL >= 0 ? "bg-emerald-500" : "bg-rose-500"}`}
                          style={{ width: `${Math.max(10, Math.min(100, 50 + (runningPnL / activeTrade.expectedProfit) * 50))}%` }}
                        ></div>
                      </div>
                    </div>

                    {/* Force close action */}
                    <button
                      onClick={forceCloseTrade}
                      id="btn-force-close"
                      className="w-full bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 hover:border-rose-500/40 text-xs font-black py-2.5 rounded-xl transition flex items-center justify-center gap-1.5 cursor-pointer shadow-lg active:scale-[0.99]"
                    >
                      <AlertOctagon className="w-4 h-4" /> FORCE CLOSE POSITION
                    </button>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-8 text-center px-4 bg-zinc-950/30 rounded-xl border border-dashed border-zinc-850">
                    <ShieldCheck className="w-8 h-8 text-zinc-600 mb-2.5" />
                    <span className="text-xs font-bold text-zinc-400">Execution Engine Idle</span>
                    <p className="text-[10px] text-zinc-500 mt-1 max-w-[200px]">
                      No active capital risk detected. Runtimes are monitoring order flow structures.
                    </p>
                  </div>
                )}
              </div>

              {/* B) STRATEGY DEPLOYMENT PIPELINE SELECTOR */}
              <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-xl flex flex-col gap-4" id="strategy-deployment-panel">
                <div className="flex items-center justify-between border-b border-zinc-800/60 pb-3">
                  <h3 className="text-xs font-extrabold text-white tracking-wider uppercase flex items-center gap-2">
                    <FileCode className="w-4 h-4 text-emerald-400" />
                    Deploy Strategy Contract
                  </h3>
                </div>

                <div className="flex flex-col gap-3.5">
                  {/* Select Approved Package */}
                  <div className="flex flex-col gap-1.5">
                    <label className="text-[9px] text-zinc-400 uppercase tracking-wider font-bold">Approved SVOS Package</label>
                    <div className="relative">
                      <select
                        value={selectedPkgId}
                        onChange={(e) => setSelectedPkgId(e.target.value)}
                        id="select-strategy-package"
                        className="w-full bg-zinc-950 border border-zinc-850 hover:border-zinc-750 text-xs text-white font-mono rounded-xl p-2.5 outline-none appearance-none cursor-pointer pr-10 focus:ring-1 focus:ring-emerald-500/50"
                      >
                        {state.strategyPackages.map((pkg) => (
                          <option key={pkg.id} value={pkg.id}>
                            {pkg.name} ({pkg.version})
                          </option>
                        ))}
                      </select>
                      <ChevronDown className="w-4 h-4 text-zinc-500 absolute right-3 top-3 pointer-events-none" />
                    </div>
                  </div>

                  {/* Configure Adapter */}
                  <div className="flex flex-col gap-1.5">
                    <label className="text-[9px] text-zinc-400 uppercase tracking-wider font-bold">Broker Adapter Target</label>
                    <div className="grid grid-cols-3 gap-1.5">
                      {(["Bybit", "MT5", "Binance"] as const).map((b) => (
                        <button
                          key={b}
                          onClick={() => setDeployBroker(b)}
                          className={`text-xs font-mono py-2 rounded-lg border transition cursor-pointer text-center ${deployBroker === b ? "bg-emerald-500/10 border-emerald-500/40 text-emerald-400 font-bold" : "bg-zinc-950 border-zinc-850 text-zinc-400 hover:border-zinc-800"}`}
                        >
                          {b}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Configure Symbols */}
                  <div className="flex flex-col gap-1.5">
                    <label className="text-[9px] text-zinc-400 uppercase tracking-wider font-bold">Market Symbols</label>
                    <div className="grid grid-cols-2 gap-1.5">
                      {["EURUSD", "GBPUSD", "XAUUSD", "USDJPY"].map((sym) => {
                        const isSelected = deploySymbols.includes(sym);
                        return (
                          <button
                            key={sym}
                            onClick={() => toggleSymbol(sym)}
                            className={`text-[10px] font-mono py-1.5 rounded-lg border transition cursor-pointer text-center ${isSelected ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400 font-bold" : "bg-zinc-950 border-zinc-850 text-zinc-500 hover:border-zinc-800"}`}
                          >
                            {sym}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Configure Risk */}
                  <div className="flex flex-col gap-1.5">
                    <label className="text-[9px] text-zinc-400 uppercase tracking-wider font-bold">Risk Allocation Profile</label>
                    <div className="grid grid-cols-3 gap-1.5">
                      {(["Low", "Medium", "Aggressive"] as const).map((r) => (
                        <button
                          key={r}
                          onClick={() => setDeployRisk(r)}
                          className={`text-[10px] font-mono py-1.5 rounded-lg border transition cursor-pointer text-center ${deployRisk === r ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400 font-bold" : "bg-zinc-950 border-zinc-850 text-zinc-500 hover:border-zinc-800"}`}
                        >
                          {r}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Deployed Preview Checklist */}
                  {selectedPkgId && (
                    <div className="bg-zinc-950/60 border border-zinc-850 rounded-xl p-2.5 text-[10px] font-mono text-zinc-400 flex flex-col gap-1">
                      <div className="text-zinc-500 font-bold uppercase text-[8px] mb-1">Contract Signature Hash</div>
                      <div className="text-zinc-300 break-all select-all leading-relaxed bg-zinc-950 p-1.5 rounded border border-zinc-900/60 font-mono text-[9px] text-emerald-500">
                        {state.strategyPackages.find(p => p.id === selectedPkgId)?.signature || "none"}
                      </div>
                      <div className="mt-1.5 flex justify-between">
                        <span>Validation Score:</span>
                        <span className="text-emerald-400 font-bold">
                          {state.strategyPackages.find(p => p.id === selectedPkgId)?.validation_score || 0}%
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Deploy Action */}
                  <button
                    onClick={handleDeploy}
                    id="btn-deploy-strategy"
                    className="w-full bg-emerald-400 hover:bg-emerald-300 text-zinc-950 text-xs font-black py-2.5 rounded-xl transition flex items-center justify-center gap-1.5 cursor-pointer shadow-lg active:scale-[0.99]"
                  >
                    <Zap className="w-4 h-4 fill-zinc-950 text-zinc-950" /> ACTIVATE STRATEGY CONTRACT
                  </button>
                </div>
              </div>
            </>
          ) : (
            <>
              {/* MANUAL SANDBOX CONTROLS PANEL */}
              <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-xl flex flex-col gap-4 relative" id="sandbox-controls-panel">
                <div className="flex items-center justify-between border-b border-zinc-800/60 pb-3">
                  <h3 className="text-xs font-extrabold text-white tracking-wider uppercase flex items-center gap-2">
                    <Radio className={`w-4 h-4 ${brokerConnected ? "text-teal-400 animate-pulse" : "text-zinc-600"}`} />
                    Sandbox Live Desk
                  </h3>
                  <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded ${brokerConnected ? "bg-teal-500/10 text-teal-400 border border-teal-500/20" : "bg-zinc-950 text-zinc-500 border border-zinc-850"}`}>
                    {brokerConnected ? "ACTIVE" : "STANDBY"}
                  </span>
                </div>

                <div className="flex flex-col gap-3.5">
                  {/* Connect / Disconnect Action */}
                  <button
                    onClick={() => {
                      const nextState = !brokerConnected;
                      setBrokerConnected(nextState);
                      if (nextState) {
                        addSandboxLog("WebSocket pipeline connecting... Securely streaming paper trades.");
                      } else {
                        addSandboxLog("WebSocket gateway disconnected. Paper trading halted.");
                      }
                    }}
                    className={`w-full text-xs font-black py-2.5 rounded-xl transition flex items-center justify-center gap-1.5 cursor-pointer shadow-lg ${
                      brokerConnected 
                        ? "bg-rose-500/15 hover:bg-rose-500/25 text-rose-400 border border-rose-500/20" 
                        : "bg-teal-400 hover:bg-teal-300 text-zinc-950 font-black"
                    }`}
                  >
                    {brokerConnected ? (
                      <>
                        <XCircle className="w-4 h-4" /> DISCONNECT SANDBOX GATEWAY
                      </>
                    ) : (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin-slow" /> CONNECT SANDBOX GATEWAY
                      </>
                    )}
                  </button>

                  {/* Account stats HUD */}
                  <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                    <div className="bg-zinc-950/40 border border-zinc-850 p-2 rounded-xl">
                      <div className="text-zinc-500 text-[9px] uppercase font-bold">Balance</div>
                      <div className="text-white font-extrabold mt-0.5">${sandboxBalance.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
                    </div>
                    <div className="bg-zinc-950/40 border border-zinc-850 p-2 rounded-xl">
                      <div className="text-zinc-500 text-[9px] uppercase font-bold">Equity</div>
                      <div className="text-white font-extrabold mt-0.5">${totalSandboxEquity.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
                    </div>
                  </div>

                  {/* Manual Order Entry Form */}
                  <div className="border border-zinc-850/60 bg-zinc-950/20 rounded-xl p-3 flex flex-col gap-3">
                    <div className="text-zinc-400 text-[9px] uppercase tracking-wider font-extrabold border-b border-zinc-850/40 pb-1.5">
                      Order Placement Form ({state.selectedPair})
                    </div>

                    <div className="flex flex-col gap-2 font-mono text-xs">
                      {/* Lot Size */}
                      <div className="flex items-center justify-between gap-2 bg-zinc-950/60 px-2.5 py-1.5 rounded-lg border border-zinc-850/40">
                        <span className="text-zinc-500 text-[10px]">LOT SIZE:</span>
                        <input
                          type="text"
                          value={lotSizeInput}
                          disabled={!brokerConnected}
                          onChange={(e) => setLotSizeInput(e.target.value)}
                          className="bg-transparent border-none text-right font-bold text-white focus:outline-none w-20 text-xs pr-1 outline-none"
                        />
                      </div>

                      {/* SL Pips */}
                      <div className="flex items-center justify-between gap-2 bg-zinc-950/60 px-2.5 py-1.5 rounded-lg border border-zinc-850/40">
                        <span className="text-zinc-500 text-[10px]">STOP LOSS (PIPS):</span>
                        <input
                          type="number"
                          value={slPipsInput}
                          disabled={!brokerConnected}
                          onChange={(e) => setSlPipsInput(e.target.value)}
                          className="bg-transparent border-none text-right font-bold text-rose-400 focus:outline-none w-20 text-xs pr-1 outline-none"
                        />
                      </div>

                      {/* TP Pips */}
                      <div className="flex items-center justify-between gap-2 bg-zinc-950/60 px-2.5 py-1.5 rounded-lg border border-zinc-850/40">
                        <span className="text-zinc-500 text-[10px]">TAKE PROFIT (PIPS):</span>
                        <input
                          type="number"
                          value={tpPipsInput}
                          disabled={!brokerConnected}
                          onChange={(e) => setTpPipsInput(e.target.value)}
                          className="bg-transparent border-none text-right font-bold text-emerald-400 focus:outline-none w-20 text-xs pr-1 outline-none"
                        />
                      </div>
                    </div>

                    {/* BUY / SELL Action Buttons */}
                    <div className="grid grid-cols-2 gap-2.5 mt-1">
                      <button
                        onClick={() => placeSandboxOrder("BUY", parseFloat(lotSizeInput) || 1.0, parseInt(slPipsInput) || 15, parseInt(tpPipsInput) || 45)}
                        disabled={!brokerConnected}
                        className={`py-2.5 rounded-xl text-xs font-black transition cursor-pointer flex items-center justify-center gap-1.5 shadow ${
                          brokerConnected 
                            ? "bg-teal-500 hover:bg-teal-400 text-zinc-950 hover:scale-[1.01]" 
                            : "bg-zinc-800 text-zinc-500 cursor-not-allowed"
                        }`}
                      >
                        <TrendingUp className="w-3.5 h-3.5" /> BUY MARKET
                      </button>
                      <button
                        onClick={() => placeSandboxOrder("SELL", parseFloat(lotSizeInput) || 1.0, parseInt(slPipsInput) || 15, parseInt(tpPipsInput) || 45)}
                        disabled={!brokerConnected}
                        className={`py-2.5 rounded-xl text-xs font-black transition cursor-pointer flex items-center justify-center gap-1.5 shadow ${
                          brokerConnected 
                            ? "bg-rose-500 hover:bg-rose-400 text-white hover:scale-[1.01]" 
                            : "bg-zinc-800 text-zinc-500 cursor-not-allowed"
                        }`}
                      >
                        <TrendingDown className="w-3.5 h-3.5" /> SELL MARKET
                      </button>
                    </div>
                  </div>

                  {/* Sandbox activity logger */}
                  <div className="bg-zinc-950/80 border border-zinc-850 rounded-xl p-3 flex flex-col gap-2">
                    <div className="flex items-center justify-between border-b border-zinc-900 pb-1.5">
                      <span className="text-[9px] text-zinc-500 font-extrabold uppercase tracking-wider flex items-center gap-1">
                        <Terminal className="w-3 h-3 text-teal-400" />
                        Sandbox Log Stream
                      </span>
                      <button
                        onClick={() => setSandboxLogs([])}
                        className="text-[8px] font-mono text-zinc-600 hover:text-zinc-400 cursor-pointer"
                      >
                        CLEAR
                      </button>
                    </div>
                    <div className="flex flex-col gap-1.5 font-mono text-[9px] text-zinc-400 max-h-[110px] min-h-[110px] overflow-y-auto leading-relaxed scrollbar-thin">
                      {sandboxLogs.slice().reverse().map((log, i) => (
                        <div key={i} className="flex gap-1 items-start">
                          <span className="text-teal-500 shrink-0">&gt;</span>
                          <span>{log}</span>
                        </div>
                      ))}
                      {sandboxLogs.length === 0 && (
                        <div className="text-zinc-600 italic">No activity logged. Connect gateway to start.</div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* C) OPERATOR RISK POLICY CONTROL PANEL */}
          <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-xl flex flex-col gap-4" id="operator-risk-panel">
            <div className="flex items-center justify-between border-b border-zinc-800/60 pb-3">
              <h3 className="text-xs font-extrabold text-white tracking-wider uppercase flex items-center gap-2">
                <Sliders className="w-4 h-4 text-emerald-400" />
                Capital Risk Policies
              </h3>
            </div>

            <div className="flex flex-col gap-4">
              {/* Max Daily Loss Slider */}
              <div className="flex flex-col gap-1.5">
                <div className="flex justify-between text-[10px] font-mono">
                  <span className="text-zinc-400 uppercase tracking-wider font-bold">Max Daily Loss</span>
                  <span className="text-rose-400 font-black">{riskMaxLoss}%</span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="5.0"
                  step="0.5"
                  value={riskMaxLoss}
                  onChange={(e) => setRiskMaxLoss(parseFloat(e.target.value))}
                  id="slider-risk-max-loss"
                  className="w-full accent-emerald-400 cursor-pointer h-1.5 bg-zinc-950 rounded-lg appearance-none"
                />
              </div>

              {/* Max Open Positions */}
              <div className="flex flex-col gap-1.5">
                <div className="flex justify-between text-[10px] font-mono">
                  <span className="text-zinc-400 uppercase tracking-wider font-bold">Max Open Positions</span>
                  <span className="text-white font-black">{riskMaxPos}</span>
                </div>
                <div className="grid grid-cols-4 gap-1">
                  {[1, 2, 3, 5].map((num) => (
                    <button
                      key={num}
                      onClick={() => setRiskMaxPos(num)}
                      className={`text-xs font-mono py-1.5 rounded-lg border transition cursor-pointer text-center ${riskMaxPos === num ? "bg-emerald-500/10 border-emerald-500/40 text-emerald-400 font-bold" : "bg-zinc-950 border-zinc-850 text-zinc-500 hover:border-zinc-800"}`}
                    >
                      {num}
                    </button>
                  ))}
                </div>
              </div>

              {/* Max Leverage */}
              <div className="flex flex-col gap-1.5">
                <label className="text-[9px] text-zinc-400 uppercase tracking-wider font-bold">Max Allowed Leverage</label>
                <div className="relative">
                  <select
                    value={riskLeverage}
                    onChange={(e) => setRiskLeverage(e.target.value)}
                    id="select-risk-leverage"
                    className="w-full bg-zinc-950 border border-zinc-850 hover:border-zinc-750 text-xs text-white font-mono rounded-xl p-2 outline-none appearance-none cursor-pointer pr-10 focus:ring-1 focus:ring-emerald-500/50"
                  >
                    <option value="1:20">1:20 (Conservative)</option>
                    <option value="1:50">1:50 (Standard)</option>
                    <option value="1:100">1:100 (SMC Default)</option>
                    <option value="1:500">1:500 (Aggressive)</option>
                  </select>
                  <ChevronDown className="w-4 h-4 text-zinc-500 absolute right-3 top-2 pointer-events-none" />
                </div>
              </div>

              {/* Auto Disable checkboxes */}
              <div className="flex flex-col gap-2 bg-zinc-950/40 border border-zinc-850 p-3 rounded-xl">
                <div className="text-[8px] text-zinc-500 font-mono uppercase tracking-widest font-extrabold mb-1">
                  Auto Circuit Breaker Triggers
                </div>
                
                <label className="flex items-center gap-2.5 text-[10px] font-mono text-zinc-400 hover:text-white cursor-pointer">
                  <input
                    type="checkbox"
                    checked={riskNews}
                    onChange={(e) => setRiskNews(e.target.checked)}
                    className="rounded border-zinc-800 text-emerald-500 focus:ring-0 bg-zinc-900"
                  />
                  <span>Halt on high-impact news events</span>
                </label>

                <label className="flex items-center gap-2.5 text-[10px] font-mono text-zinc-400 hover:text-white cursor-pointer">
                  <input
                    type="checkbox"
                    checked={riskLatency}
                    onChange={(e) => setRiskLatency(e.target.checked)}
                    className="rounded border-zinc-800 text-emerald-500 focus:ring-0 bg-zinc-900"
                  />
                  <span>Halt if Broker latency spikes &gt; 250ms</span>
                </label>

                <label className="flex items-center gap-2.5 text-[10px] font-mono text-zinc-400 hover:text-white cursor-pointer">
                  <input
                    type="checkbox"
                    checked={riskLossLimit}
                    onChange={(e) => setRiskLossLimit(e.target.checked)}
                    className="rounded border-zinc-800 text-emerald-500 focus:ring-0 bg-zinc-900"
                  />
                  <span>Force close if drawdown limit tapped</span>
                </label>
              </div>

              {/* Commit and Emergency Action Row */}
              <div className="flex flex-col gap-2">
                <button
                  onClick={handleSaveRisk}
                  id="btn-save-risk"
                  className="w-full bg-zinc-800 hover:bg-zinc-700 text-white hover:text-emerald-400 border border-zinc-700/60 text-xs font-bold py-2 rounded-xl transition cursor-pointer text-center"
                >
                  COMMIT RISK POLICY
                </button>

                {/* EMERGENCY TRIGGER */}
                <button
                  onClick={triggerKillSwitch}
                  id="btn-emergency-kill-switch"
                  className="w-full bg-rose-600 hover:bg-rose-500 text-white text-xs font-black py-3 rounded-xl transition flex items-center justify-center gap-1.5 cursor-pointer shadow-lg active:scale-[0.98] border border-rose-500/50 select-none bg-[linear-gradient(45deg,#e11d48_25%,#be123c_25%,#be123c_50%,#e11d48_50%,#e11d48_75%,#be123c_75%,#be123c)] bg-[length:24px_24px] hover:animate-[stripe_2s_linear_infinite]"
                >
                  <AlertOctagon className="w-4 h-4" /> EMERGENCY KILL SWITCH
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: MAIN DISPLAY SCREEN (Col span 3) */}
        <div className="xl:col-span-3 flex flex-col gap-6" id="main-ops-center">
          
          {/* A) THE CENTRAL INTERACTIVE WORKSPACE (CHART) */}
          <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-xl flex flex-col gap-3" id="central-chart-workspace">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 border-b border-zinc-800/60 pb-3">
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></div>
                <span className="text-xs font-extrabold text-white uppercase tracking-wider">
                  Live Market Structure Canvas: {state.selectedPair}
                </span>
              </div>
              
              {/* Instrument Toggle Quick Switch */}
              <div className="flex items-center gap-1.5 bg-zinc-950/80 p-1 border border-zinc-850 rounded-xl">
                {Object.keys(state.pairs).map((sym) => (
                  <button
                    key={sym}
                    onClick={() => selectPair(sym)}
                    className={`px-3 py-1 text-xs font-mono font-bold rounded-lg transition cursor-pointer ${state.selectedPair === sym ? "bg-emerald-500 text-zinc-950 shadow" : "text-zinc-400 hover:text-white"}`}
                  >
                    {sym}
                  </button>
                ))}
              </div>
            </div>

            {/* Render High-fidelity SVOS Canvas */}
            <div className="w-full relative min-h-[300px]">
              {selectedPairState && (
                <LiveChart pair={selectedPairState} activeTrade={state.activeTrade} />
              )}
            </div>
          </div>

          {/* B) ACTIVE DEPLOYED STRATEGY RUNTIMES & ACTIVE POSITIONS */}
          {executionMode === "AUTOMATED" ? (
            <>
              {/* B1) REAL-TIME ACTIVE AUTOMATED POSITIONS */}
              <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-xl flex flex-col gap-4" id="active-automated-positions-panel">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 border-b border-zinc-800/60 pb-3">
                  <div className="flex flex-col">
                    <h3 className="text-xs font-extrabold text-white tracking-wider uppercase flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${state.activeTrade ? "bg-emerald-500 animate-pulse" : "bg-zinc-600"}`}></span>
                      Active Automated Positions &amp; Risk Structures
                    </h3>
                    <span className="text-[10px] text-zinc-500 font-sans mt-0.5">
                      Real-time institutional liquidity order block risk exposure
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 text-[10px] font-mono text-zinc-400 bg-zinc-950/80 px-2.5 py-1.5 rounded-xl border border-zinc-850">
                    <span>Active: {state.activeTrade ? 1 : 0} Open</span>
                  </div>
                </div>

                {state.activeTrade ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left font-mono text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-zinc-800 text-zinc-500 text-[10px] font-bold uppercase tracking-wider">
                          <th className="pb-3 pl-2">Ticket ID</th>
                          <th className="pb-3">Symbol</th>
                          <th className="pb-3">Type</th>
                          <th className="pb-3">Lots</th>
                          <th className="pb-3">Entry Price</th>
                          <th className="pb-3">Current Price</th>
                          <th className="pb-3">SL / TP Levels</th>
                          <th className="pb-3 text-center">Risk/Reward</th>
                          <th className="pb-3 text-right">Floating P&amp;L</th>
                          <th className="pb-3 pr-2 text-right">Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(() => {
                          const pairSymbol = "EURUSD";
                          const pairData = state.pairs[pairSymbol];
                          const currentPrice = pairData ? pairData.price : state.activeTrade.entry;
                          const isBuy = state.activeTrade.type === "BUY";
                          const pipsDiff = isBuy ? (currentPrice - state.activeTrade.entry) : (state.activeTrade.entry - currentPrice);
                          const runningPnL = parseFloat((pipsDiff * state.activeTrade.lotSize * 100000).toFixed(2));
                          const ticketId = `TX-AUTO-${state.activeTrade.entry.toString().replace(".", "").slice(-4)}`;
                          
                          return (
                            <tr className="border-b border-zinc-850 hover:bg-zinc-950/20 transition">
                              <td className="py-3.5 pl-2">
                                <span className="font-bold text-zinc-300">{ticketId}</span>
                                <div className="text-[9px] text-zinc-600 mt-0.5">SMC Core Live</div>
                              </td>
                              <td className="py-3.5">
                                <span className="text-white font-extrabold font-sans text-sm">{pairSymbol}</span>
                              </td>
                              <td className="py-3.5">
                                <span className={`px-2 py-0.5 rounded-md text-[9px] font-black border ${isBuy ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-rose-500/10 text-rose-400 border-rose-500/20"}`}>
                                  {state.activeTrade.type}
                                </span>
                              </td>
                              <td className="py-3.5 text-zinc-300 font-semibold">
                                {state.activeTrade.lotSize.toFixed(2)}
                              </td>
                              <td className="py-3.5 text-zinc-400 font-mono">
                                {state.activeTrade.entry.toFixed(5)}
                              </td>
                              <td className="py-3.5 text-white font-bold animate-pulse">
                                {currentPrice.toFixed(5)}
                              </td>
                              <td className="py-3.5">
                                <div className="flex flex-col text-[10px] text-zinc-500 font-mono">
                                  <span>SL: <strong className="text-rose-400/80 font-bold">{state.activeTrade.sl.toFixed(5)}</strong></span>
                                  <span>TP: <strong className="text-emerald-400/80 font-bold">{state.activeTrade.tp.toFixed(5)}</strong></span>
                                </div>
                              </td>
                              <td className="py-3.5 text-center text-emerald-400 font-bold">
                                1:{state.activeTrade.rr}
                              </td>
                              <td className={`py-3.5 text-right font-black font-mono text-sm ${runningPnL >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                                {runningPnL >= 0 ? `+$${runningPnL.toLocaleString("en-US", { minimumFractionDigits: 2 })}` : `-$${Math.abs(runningPnL).toLocaleString("en-US", { minimumFractionDigits: 2 })}`}
                              </td>
                              <td className="py-3.5 pr-2 text-right">
                                <button
                                  onClick={forceCloseTrade}
                                  className="px-3 py-1.5 bg-rose-500/10 hover:bg-rose-500/25 text-rose-400 border border-rose-500/20 hover:border-rose-500/40 rounded-xl text-[10px] font-extrabold cursor-pointer transition hover:scale-[1.02]"
                                >
                                  FORCE CLOSE
                                </button>
                              </td>
                            </tr>
                          );
                        })()}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-10 text-center px-4 bg-zinc-950/20 rounded-xl border border-dashed border-zinc-850">
                    <ShieldCheck className="w-10 h-10 text-zinc-600 mb-3" />
                    <span className="text-sm font-bold text-zinc-400">No Open Automated Positions</span>
                    <p className="text-xs text-zinc-500 mt-1 max-w-[340px]">
                      The SMC core execution engines are currently searching for institutional liquidity sweeps and order block alignments.
                    </p>
                  </div>
                )}
              </div>

              {/* B2) ACTIVE DEPLOYED STRATEGY RUNTIMES & STATUS */}
              <StrategyRuntimeStatus />

              {/* B3) REAL-TIME COMPLETED TRADE LEDGER */}
              <TradeExecutionHistory />

              {/* Broker Reconnection Section */}
              <div className="mt-2 p-3 bg-zinc-950/40 border border-zinc-850 rounded-xl flex flex-col sm:flex-row items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className={`w-3 h-3 rounded-full ${state.brokerConnection.status === "CONNECTED" ? "bg-emerald-500 animate-pulse" : "bg-rose-500"}`}></div>
                  <div className="flex flex-col">
                    <span className="text-xs text-zinc-300 font-bold font-mono">
                      Broker Socket Gateway: <span className={state.brokerConnection.status === "CONNECTED" ? "text-emerald-400" : "text-rose-400"}>{state.brokerConnection.status}</span>
                    </span>
                    <span className="text-[10px] text-zinc-500 font-mono mt-0.5">
                      Order rate: {state.brokerConnection.orderSuccessRate}% | Pulse: {state.brokerConnection.heartbeat}
                    </span>
                  </div>
                </div>
                <button
                  onClick={reconnectBroker}
                  disabled={state.brokerConnection.status === "RECONNECTING"}
                  className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold border transition cursor-pointer ${
                    state.brokerConnection.status === "RECONNECTING"
                      ? "bg-zinc-900 border-zinc-850 text-zinc-600 cursor-not-allowed"
                      : "bg-zinc-900 border-zinc-800 text-zinc-300 hover:text-white hover:border-zinc-700"
                  }`}
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${state.brokerConnection.status === "RECONNECTING" ? "animate-spin" : ""}`} /> 
                  {state.brokerConnection.status === "RECONNECTING" ? "RECONNECTING..." : "RECYCLE SOCKET GATEWAY"}
                </button>
              </div>
          </>
          ) : (
            <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-xl flex flex-col gap-4" id="sandbox-active-orders-panel">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 border-b border-zinc-800/60 pb-3">
                <h3 className="text-xs font-extrabold text-white tracking-wider uppercase flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-teal-400 animate-pulse" />
                  Active Sandbox Positions &amp; Capital Allocations
                </h3>
                <div className="flex items-center gap-1.5 text-[10px] font-mono text-zinc-400 bg-zinc-950/80 px-2.5 py-1.5 rounded-xl border border-zinc-850">
                  <span>Positions: {activeSandboxOrdersCount} Open</span>
                </div>
              </div>

              {activeSandboxOrdersCount > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-left font-mono text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-zinc-800 text-zinc-500 text-[10px] font-bold uppercase tracking-wider">
                        <th className="pb-3 pl-2">Ticket ID</th>
                        <th className="pb-3">Instrument</th>
                        <th className="pb-3">Type</th>
                        <th className="pb-3">Lots</th>
                        <th className="pb-3">Entry Price</th>
                        <th className="pb-3">Current Price</th>
                        <th className="pb-3">SL / TP Limits</th>
                        <th className="pb-3 text-right">Floating P&amp;L</th>
                        <th className="pb-3 pr-2 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {demoOrders
                        .filter(order => order.status === "FILLED")
                        .map((order) => {
                          const config = getAssetConfig(order.asset);
                          const pairData = state.pairs[order.asset];
                          const currentPrice = pairData ? pairData.price : order.price;
                          const pipsDiff = (currentPrice - order.price) / config.pip;
                          const multiplier = order.asset === "Step Index 100" ? 10 : 100;
                          const profit = order.type === "BUY" ? pipsDiff * multiplier * (order.lotSize || 1.0) : -pipsDiff * multiplier * (order.lotSize || 1.0);
                          return (
                            <tr key={order.id} className="border-b border-zinc-850 hover:bg-zinc-950/20 transition">
                              <td className="py-3.5 pl-2">
                                <span className="font-bold text-zinc-300">{order.id}</span>
                                <div className="text-[9px] text-zinc-600 mt-0.5">{order.time.split(" ")[1]}</div>
                              </td>
                              <td className="py-3.5">
                                <span className="text-white font-extrabold">{order.asset}</span>
                              </td>
                              <td className="py-3.5">
                                <span className={`px-2 py-0.5 rounded-md text-[9px] font-black border ${order.type === "BUY" ? "bg-teal-500/10 text-teal-400 border-teal-500/20" : "bg-rose-500/10 text-rose-400 border-rose-500/20"}`}>
                                  {order.type}
                                </span>
                              </td>
                              <td className="py-3.5 text-zinc-300 font-semibold">
                                {(order.lotSize || 1.0).toFixed(2)}
                              </td>
                              <td className="py-3.5 text-zinc-400 font-mono">
                                {order.price.toFixed(config.decimals)}
                              </td>
                              <td className="py-3.5 text-white font-bold animate-pulse">
                                {currentPrice.toFixed(config.decimals)}
                              </td>
                              <td className="py-3.5">
                                <div className="flex flex-col text-[10px] text-zinc-500">
                                  <span>SL: <strong className="text-rose-400/80 font-bold">{order.sl.toFixed(config.decimals)}</strong></span>
                                  <span>TP: <strong className="text-emerald-400/80 font-bold">{order.tp.toFixed(config.decimals)}</strong></span>
                                </div>
                              </td>
                              <td className={`py-3.5 text-right font-black ${profit >= 0 ? "text-teal-400" : "text-rose-400"}`}>
                                {profit >= 0 ? `+$${profit.toFixed(2)}` : `-$${Math.abs(profit).toFixed(2)}`}
                              </td>
                              <td className="py-3.5 pr-2 text-right">
                                <button
                                  onClick={() => closeSandboxOrder(order.id)}
                                  className="px-3 py-1 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 rounded-lg text-[10px] font-extrabold cursor-pointer transition hover:scale-[1.02]"
                                >
                                  CLOSE
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-10 text-center px-4 bg-zinc-950/20 rounded-xl border border-dashed border-zinc-850">
                  <ShieldCheck className="w-10 h-10 text-zinc-600 mb-3" />
                  <span className="text-sm font-bold text-zinc-400">No Open Sandbox Trades</span>
                  <p className="text-xs text-zinc-500 mt-1 max-w-[340px]">
                    Place a BUY or SELL market order above with your paper gateway connected to deploy capital structures instantly.
                  </p>
                </div>
              )}

              {/* Closed sandbox history sub-drawer */}
              {demoOrders.some(o => o.status === "CLOSED") && (
                <div className="mt-4 border-t border-zinc-800/60 pt-4 flex flex-col gap-2.5">
                  <h4 className="text-[10px] font-mono font-extrabold text-zinc-500 uppercase tracking-wider flex items-center gap-1">
                    <Activity className="w-3.5 h-3.5 text-teal-400" />
                    Closed Trade Execution Logs (Realized Sandbox History)
                  </h4>
                  <div className="max-h-44 overflow-y-auto border border-zinc-850 bg-zinc-950/50 rounded-xl">
                    <table className="w-full text-left font-mono text-[10px] border-collapse">
                      <thead>
                        <tr className="border-b border-zinc-900 bg-zinc-950 text-zinc-500 py-2 px-2 text-[9px] font-extrabold uppercase">
                          <th className="py-2 pl-3">Ticket</th>
                          <th className="py-2">Instrument</th>
                          <th className="py-2">Type</th>
                          <th className="py-2">Entry &rArr; Exit</th>
                          <th className="py-2 text-right pr-3">Realized Net profit</th>
                        </tr>
                      </thead>
                      <tbody>
                        {demoOrders
                          .filter(order => order.status === "CLOSED")
                          .map((order) => {
                            const config = getAssetConfig(order.asset);
                            return (
                              <tr key={order.id} className="border-b border-zinc-900/40 hover:bg-zinc-900/10 text-zinc-400">
                                <td className="py-2 pl-3 font-semibold text-zinc-500">{order.id}</td>
                                <td className="py-2 text-zinc-300 font-bold">{order.asset}</td>
                                <td className="py-2">
                                  <span className={order.type === "BUY" ? "text-teal-400" : "text-rose-400"}>{order.type}</span>
                                </td>
                                <td className="py-2">
                                  {order.price.toFixed(config.decimals)} &rArr; {order.exitPrice?.toFixed(config.decimals) || "N/A"}
                                </td>
                                <td className={`py-2 text-right pr-3 font-bold ${order.profit && order.profit >= 0 ? "text-teal-400" : "text-rose-400"}`}>
                                  {order.profit && order.profit >= 0 ? `+$${order.profit.toFixed(2)}` : `-$${Math.abs(order.profit || 0).toFixed(2)}`}
                                </td>
                              </tr>
                            );
                          })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* C) REAL-TIME OPERATIONAL CONSOLE & LOG EVENT STREAM */}
          <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-xl flex flex-col gap-4" id="ops-console-log-stream">
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3 border-b border-zinc-800/60 pb-3.5">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-emerald-400 animate-pulse" />
                <h3 className="text-xs font-extrabold text-white tracking-wider uppercase">
                  Real-Time Operations Console Logs
                </h3>
              </div>

              {/* Filters & Search Row */}
              <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
                {/* Search Bar */}
                <div className="relative flex-1 md:flex-initial">
                  <input
                    type="text"
                    placeholder="Search logs..."
                    value={logSearch}
                    onChange={(e) => setLogSearch(e.target.value)}
                    className="w-full md:w-44 bg-zinc-950 border border-zinc-850 rounded-xl px-2.5 py-1.5 pl-8 text-xs font-mono text-zinc-300 outline-none focus:border-zinc-700"
                  />
                  <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-2.5 top-2.5" />
                </div>

                {/* Level Quick Filter Buttons */}
                <div className="flex items-center gap-1 bg-zinc-950/80 p-1 border border-zinc-850 rounded-xl">
                  {["ALL", "INFO", "SUCCESS", "WARNING", "CRITICAL"].map((level) => (
                    <button
                      key={level}
                      onClick={() => setLogFilter(level)}
                      className={`px-2 py-1 text-[9px] font-mono font-black rounded-lg transition cursor-pointer ${logFilter === level ? "bg-zinc-800 text-white" : "text-zinc-500 hover:text-zinc-300"}`}
                    >
                      {level}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Scrollable Log Terminal Display */}
            <div className="bg-zinc-950 border border-zinc-900 rounded-xl p-3 h-52 overflow-y-auto font-mono text-[10px] leading-relaxed flex flex-col gap-1.5 shadow-inner">
              {filteredEvents.map((evt) => {
                let textCol = "text-zinc-400";
                let badgeCol = "bg-zinc-900 text-zinc-400 border-zinc-800";
                if (evt.level === "SUCCESS") {
                  textCol = "text-emerald-400/95";
                  badgeCol = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
                } else if (evt.level === "WARNING") {
                  textCol = "text-amber-400/95";
                  badgeCol = "bg-amber-500/10 text-amber-400 border-amber-500/20";
                } else if (evt.level === "CRITICAL") {
                  textCol = "text-rose-400 font-extrabold animate-pulse";
                  badgeCol = "bg-rose-500/15 text-rose-400 border-rose-500/30";
                } else if (evt.level === "INFO") {
                  textCol = "text-zinc-300";
                  badgeCol = "bg-zinc-800/40 text-zinc-400 border-zinc-800/50";
                }

                return (
                  <div key={evt.id} className="flex items-start gap-2.5 py-0.5 border-b border-zinc-900/40 hover:bg-zinc-900/20 rounded">
                    {/* Log Timestamp */}
                    <span className="text-zinc-600 shrink-0 select-none">
                      [{new Date(evt.timestamp).toISOString().split("T")[1].slice(0, 11)}]
                    </span>
                    {/* Log Level Badge */}
                    <span className={`px-1.5 py-0.2 rounded font-black text-[8px] uppercase tracking-wider border shrink-0 ${badgeCol}`}>
                      {evt.level}
                    </span>
                    {/* Log message */}
                    <span className={`font-medium ${textCol}`}>
                      {evt.message}
                    </span>
                  </div>
                );
              })}
              {filteredEvents.length === 0 && (
                <div className="flex-1 flex items-center justify-center text-zinc-600 text-xs">
                  No system console events match the current filter criteria.
                </div>
              )}
              <div ref={consoleEndRef}></div>
            </div>

            {/* Error Diagnostics / Queue Status Box */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Failed Orders */}
              <div className="bg-zinc-950/60 border border-zinc-850 p-3 rounded-xl flex flex-col gap-1.5">
                <span className="text-[9px] text-rose-400 font-black uppercase tracking-wider">Failed Order Logs</span>
                <div className="flex flex-col gap-1 font-mono text-[9px] text-zinc-500 max-h-[80px] overflow-y-auto">
                  {state.failedOrders?.map((err, i) => (
                    <div key={i} className="flex gap-1.5 items-start">
                      <span className="text-rose-500 font-bold">●</span>
                      <span>{err}</span>
                    </div>
                  )) || <div>No failed orders in current session.</div>}
                </div>
              </div>

              {/* Retry Queue */}
              <div className="bg-zinc-950/60 border border-zinc-850 p-3 rounded-xl flex flex-col gap-1.5">
                <span className="text-[9px] text-amber-400 font-black uppercase tracking-wider">Broker Execution Retry Queue</span>
                <div className="flex flex-col gap-1 font-mono text-[9px] text-zinc-500 max-h-[80px] overflow-y-auto">
                  {state.retryQueue?.map((ret, i) => (
                    <div key={i} className="flex gap-1.5 items-start animate-pulse">
                      <span className="text-amber-500 font-bold">↻</span>
                      <span className="text-zinc-400">{ret}</span>
                    </div>
                  )) || <div>Retry queue empty. Execution latency within bounds.</div>}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
