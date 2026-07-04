import React, { useState } from "react";
import { useSocket } from "../context/SocketContext.js";
import { ExecutedTrade } from "../types.js";
import { 
  History, 
  Search, 
  ArrowUpRight, 
  ArrowDownRight, 
  Clock, 
  Activity,
  Percent,
  TrendingUp,
  BarChart2,
  ChevronDown,
  ChevronUp,
  Info,
  Calendar,
  AlertCircle
} from "lucide-react";

export const TradeExecutionHistory: React.FC = () => {
  const { state } = useSocket();
  const [searchTerm, setSearchTerm] = useState("");
  const [typeFilter, setTypeFilter] = useState<"all" | "BUY" | "SELL">("all");
  const [outcomeFilter, setOutcomeFilter] = useState<"all" | "PROFIT" | "LOSS">("all");
  const [expandedTradeId, setExpandedTradeId] = useState<string | null>(null);

  if (!state) return null;

  const history = state.history || [];

  // Filter logic
  const filteredHistory = history.filter((trade) => {
    const matchesSearch = 
      trade.pair.toLowerCase().includes(searchTerm.toLowerCase()) ||
      trade.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (trade.exitReason && trade.exitReason.toLowerCase().includes(searchTerm.toLowerCase()));

    const matchesType = typeFilter === "all" || trade.type === typeFilter;
    
    const matchesOutcome = 
      outcomeFilter === "all" || 
      (outcomeFilter === "PROFIT" && trade.pnl >= 0) || 
      (outcomeFilter === "LOSS" && trade.pnl < 0);

    return matchesSearch && matchesType && matchesOutcome;
  });

  // Calculate high-fidelity KPIs
  const totalTrades = history.length;
  const profitableTrades = history.filter(t => t.pnl > 0).length;
  const winRate = totalTrades > 0 ? ((profitableTrades / totalTrades) * 100).toFixed(1) : "0.0";
  
  const netPnL = history.reduce((sum, t) => sum + t.pnl, 0);
  const totalLots = history.reduce((sum, t) => sum + t.lots, 0);

  const toggleExpand = (id: string) => {
    setExpandedTradeId((prev) => (prev === id ? null : id));
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-5 shadow-xl flex flex-col gap-4" id="trade-execution-history-dashboard">
      
      {/* Header section with icon and subtitle */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-zinc-800/60 pb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <History className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-extrabold text-white tracking-wider uppercase flex items-center gap-2">
              Trade Execution History
            </h3>
            <p className="text-[10px] text-zinc-500 font-mono mt-0.5">
              Archived ledger of live smart money contract executions and realized yield
            </p>
          </div>
        </div>

        <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-widest font-black bg-zinc-950 border border-zinc-850 px-2.5 py-1.5 rounded-xl">
          Live Session Sync Enabled
        </span>
      </div>

      {/* KPI Stats Panel Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {/* KPI 1: Net PnL */}
        <div className="bg-zinc-950/60 border border-zinc-850/80 rounded-xl p-3 flex flex-col justify-between min-h-[70px]">
          <span className="text-[9px] font-mono text-zinc-500 font-extrabold uppercase">Net Yield</span>
          <div className="flex items-baseline gap-1.5 mt-1">
            <span className={`text-sm font-black font-mono ${netPnL >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              {netPnL >= 0 ? `+$${netPnL.toLocaleString("en-US", { minimumFractionDigits: 2 })}` : `-$${Math.abs(netPnL).toLocaleString("en-US", { minimumFractionDigits: 2 })}`}
            </span>
            {netPnL >= 0 ? (
              <ArrowUpRight className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
            ) : (
              <ArrowDownRight className="w-3.5 h-3.5 text-rose-400 shrink-0" />
            )}
          </div>
        </div>

        {/* KPI 2: Win Rate */}
        <div className="bg-zinc-950/60 border border-zinc-850/80 rounded-xl p-3 flex flex-col justify-between min-h-[70px]">
          <span className="text-[9px] font-mono text-zinc-500 font-extrabold uppercase">Win Ratio</span>
          <div className="flex items-baseline gap-1.5 mt-1">
            <span className="text-sm font-black text-white font-mono">{winRate}%</span>
            <span className="text-[9px] font-mono text-zinc-500">
              ({profitableTrades}/{totalTrades})
            </span>
          </div>
        </div>

        {/* KPI 3: Total Lots */}
        <div className="bg-zinc-950/60 border border-zinc-850/80 rounded-xl p-3 flex flex-col justify-between min-h-[70px]">
          <span className="text-[9px] font-mono text-zinc-500 font-extrabold uppercase">Total Volume</span>
          <div className="flex items-baseline gap-1.5 mt-1">
            <span className="text-sm font-black text-zinc-300 font-mono">{totalLots.toFixed(2)}</span>
            <span className="text-[9px] font-mono text-zinc-500">Lots</span>
          </div>
        </div>

        {/* KPI 4: Execution count */}
        <div className="bg-zinc-950/60 border border-zinc-850/80 rounded-xl p-3 flex flex-col justify-between min-h-[70px]">
          <span className="text-[9px] font-mono text-zinc-500 font-extrabold uppercase">Contracts Filled</span>
          <div className="flex items-baseline gap-1.5 mt-1">
            <span className="text-sm font-black text-zinc-300 font-mono">{totalTrades}</span>
            <span className="text-[9px] font-mono text-zinc-500">Orders</span>
          </div>
        </div>
      </div>

      {/* Interactive Controls & Filters */}
      <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <input
            type="text"
            placeholder="Search by instrument, ticket id, exit reason..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-850 rounded-xl px-3 py-2 pl-9 text-xs font-medium text-white placeholder-zinc-500 focus:outline-none focus:border-indigo-500 font-mono"
          />
          <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-3 top-3" />
        </div>

        {/* Combined Filter Controls */}
        <div className="flex flex-wrap items-center gap-2 font-mono text-[9px] font-black">
          {/* Action Type Filter */}
          <div className="flex bg-zinc-950 p-1 border border-zinc-850 rounded-xl">
            <button
              onClick={() => setTypeFilter("all")}
              className={`px-2.5 py-1 rounded-lg transition-all uppercase ${typeFilter === "all" ? "bg-zinc-800 text-white" : "text-zinc-500 hover:text-zinc-300"}`}
            >
              ALL TYPES
            </button>
            <button
              onClick={() => setTypeFilter("BUY")}
              className={`px-2.5 py-1 rounded-lg transition-all ${typeFilter === "BUY" ? "bg-emerald-500/10 text-emerald-400" : "text-zinc-500 hover:text-zinc-300"}`}
            >
              BUY
            </button>
            <button
              onClick={() => setTypeFilter("SELL")}
              className={`px-2.5 py-1 rounded-lg transition-all ${typeFilter === "SELL" ? "bg-rose-500/10 text-rose-400" : "text-zinc-500 hover:text-zinc-300"}`}
            >
              SELL
            </button>
          </div>

          {/* Outcome Outcome Filter */}
          <div className="flex bg-zinc-950 p-1 border border-zinc-850 rounded-xl">
            <button
              onClick={() => setOutcomeFilter("all")}
              className={`px-2.5 py-1 rounded-lg transition-all uppercase ${outcomeFilter === "all" ? "bg-zinc-800 text-white" : "text-zinc-500 hover:text-zinc-300"}`}
            >
              ALL OUTCOMES
            </button>
            <button
              onClick={() => setOutcomeFilter("PROFIT")}
              className={`px-2.5 py-1 rounded-lg transition-all ${outcomeFilter === "PROFIT" ? "bg-emerald-500/10 text-emerald-400" : "text-zinc-500 hover:text-zinc-300"}`}
            >
              PROFIT ONLY
            </button>
            <button
              onClick={() => setOutcomeFilter("LOSS")}
              className={`px-2.5 py-1 rounded-lg transition-all ${outcomeFilter === "LOSS" ? "bg-rose-500/10 text-rose-400" : "text-zinc-500 hover:text-zinc-300"}`}
            >
              LOSS ONLY
            </button>
          </div>
        </div>
      </div>

      {/* Main Execution Logs Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left font-mono text-xs border-collapse">
          <thead>
            <tr className="border-b border-zinc-800 text-zinc-500 text-[10px] font-bold uppercase tracking-wider">
              <th className="pb-3 pl-2">Ticket ID</th>
              <th className="pb-3">Symbol</th>
              <th className="pb-3">Type</th>
              <th className="pb-3">Lots</th>
              <th className="pb-3 text-right">Entry Price</th>
              <th className="pb-3 text-right">Exit Price</th>
              <th className="pb-3 text-center">Duration</th>
              <th className="pb-3 text-right">Realized Profit</th>
              <th className="pb-3 pr-2 text-right">Diagnostics</th>
            </tr>
          </thead>
          <tbody>
            {filteredHistory.length > 0 ? (
              filteredHistory.map((trade) => {
                const isExpanded = expandedTradeId === trade.id;
                const isProfit = trade.pnl >= 0;
                
                // Formulate beautiful human-friendly ticket or short ID
                const shortId = `TX-${trade.id.slice(-6).toUpperCase()}`;
                
                // Compute local execution time
                const timeStr = new Date(trade.entryTime).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit"
                });

                return (
                  <React.Fragment key={trade.id}>
                    <tr 
                      onClick={() => toggleExpand(trade.id)}
                      className="border-b border-zinc-850 hover:bg-zinc-950/20 transition cursor-pointer"
                    >
                      <td className="py-3.5 pl-2">
                        <span className="font-bold text-zinc-300">{shortId}</span>
                        <div className="text-[9px] text-zinc-600 mt-0.5">{timeStr}</div>
                      </td>
                      <td className="py-3.5">
                        <span className="text-white font-extrabold font-sans text-xs">{trade.pair}</span>
                      </td>
                      <td className="py-3.5">
                        <span className={`px-2 py-0.5 rounded-md text-[9px] font-black border uppercase ${
                          trade.type === "BUY" 
                            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" 
                            : "bg-rose-500/10 text-rose-400 border-rose-500/20"
                        }`}>
                          {trade.type}
                        </span>
                      </td>
                      <td className="py-3.5 text-zinc-300 font-semibold">
                        {trade.lots.toFixed(2)}
                      </td>
                      <td className="py-3.5 text-right text-zinc-400">
                        {trade.entry.toFixed(trade.pair === "USDJPY" ? 2 : 5)}
                      </td>
                      <td className="py-3.5 text-right text-white font-semibold">
                        {trade.exit.toFixed(trade.pair === "USDJPY" ? 2 : 5)}
                      </td>
                      <td className="py-3.5 text-center text-zinc-400">
                        <span className="inline-flex items-center gap-1 bg-zinc-950 border border-zinc-850 px-2 py-0.5 rounded-md text-[10px]">
                          <Clock className="w-2.5 h-2.5 text-zinc-500" />
                          {trade.duration}
                        </span>
                      </td>
                      <td className={`py-3.5 text-right font-black text-sm ${isProfit ? "text-emerald-400" : "text-rose-400"}`}>
                        {isProfit ? `+$${trade.pnl.toLocaleString("en-US", { minimumFractionDigits: 2 })}` : `-$${Math.abs(trade.pnl).toLocaleString("en-US", { minimumFractionDigits: 2 })}`}
                      </td>
                      <td className="py-3.5 pr-2 text-right">
                        <button className="text-zinc-500 hover:text-zinc-300 font-sans text-[10px] font-extrabold inline-flex items-center gap-0.5 cursor-pointer">
                          {isExpanded ? "COLLAPSE" : "INSPECT"}
                          {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                        </button>
                      </td>
                    </tr>

                    {/* Expandable detailed post-trade telemetry logs */}
                    {isExpanded && (
                      <tr className="bg-zinc-950/40">
                        <td colSpan={9} className="py-4 px-6 border-l-2 border-indigo-500">
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            
                            {/* Analytics table column */}
                            <div className="flex flex-col gap-2 bg-zinc-900 border border-zinc-850 rounded-xl p-3.5 shadow-inner">
                              <h4 className="text-[10px] font-sans font-extrabold text-white uppercase tracking-wider flex items-center gap-1.5 border-b border-zinc-800 pb-2">
                                <Info className="w-3.5 h-3.5 text-indigo-400" />
                                Post-Trade Telemetry Diagnostics
                              </h4>
                              <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-[10px] font-mono text-zinc-400">
                                <div className="flex justify-between py-0.5 border-b border-zinc-850/40">
                                  <span>Exit Trigger:</span>
                                  <span className="font-bold text-white font-sans">{trade.exitReason}</span>
                                </div>
                                <div className="flex justify-between py-0.5 border-b border-zinc-850/40">
                                  <span>Slippage Cost:</span>
                                  <span className="text-amber-400 font-bold">+{trade.slippage.toFixed(1)} pips</span>
                                </div>
                                <div className="flex justify-between py-0.5 border-b border-zinc-850/40">
                                  <span>Execution Latency:</span>
                                  <span className="text-zinc-200 font-bold">{trade.latency} ms</span>
                                </div>
                                <div className="flex justify-between py-0.5 border-b border-zinc-850/40">
                                  <span>Adverse Excursion (MAE):</span>
                                  <span className="text-rose-400 font-bold">-{trade.mae.toFixed(1)} pips</span>
                                </div>
                                <div className="flex justify-between py-0.5 border-b border-zinc-850/40">
                                  <span>Favorable Excursion (MFE):</span>
                                  <span className="text-emerald-400 font-bold">+{trade.mfe.toFixed(1)} pips</span>
                                </div>
                                <div className="flex justify-between py-0.5 border-b border-zinc-850/40">
                                  <span>Broker Fee:</span>
                                  <span className="text-zinc-300 font-bold">${trade.commission.toFixed(2)}</span>
                                </div>
                                <div className="flex justify-between py-0.5 border-b border-zinc-850/40 col-span-2">
                                  <span>Realized Risk/Reward (R:R Ratio):</span>
                                  <span className="text-emerald-400 font-extrabold">+{trade.realRr.toFixed(2)} R</span>
                                </div>
                              </div>
                            </div>

                            {/* Execution Checklist block */}
                            <div className="flex flex-col gap-2 bg-zinc-900 border border-zinc-850 rounded-xl p-3.5 shadow-inner">
                              <h4 className="text-[10px] font-sans font-extrabold text-white uppercase tracking-wider flex items-center gap-1.5 border-b border-zinc-800 pb-2">
                                <Activity className="w-3.5 h-3.5 text-indigo-400" />
                                Entry Confluence &amp; Rules Checklist
                              </h4>
                              <div className="flex flex-col gap-1.5 text-[10px] font-sans text-zinc-300">
                                {trade.explanation && trade.explanation.map((item, index) => (
                                  <div key={index} className="flex items-start gap-2 py-0.5 leading-normal">
                                    <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full mt-1 shrink-0"></span>
                                    <span>{item}</span>
                                  </div>
                                ))}
                              </div>
                            </div>

                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })
            ) : (
              <tr>
                <td colSpan={9} className="py-10 text-center">
                  <div className="flex flex-col items-center justify-center text-center px-4">
                    <History className="w-8 h-8 text-zinc-600 mb-2" />
                    <span className="text-xs font-bold text-zinc-400">No Historical Trades Found</span>
                    <p className="text-[11px] text-zinc-500 mt-1 max-w-[340px]">
                      Awaiting live algorithm trigger events or signal checks to register.
                    </p>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

    </div>
  );
};
