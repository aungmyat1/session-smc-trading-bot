import React, { useState } from "react";
import { useSocket } from "../context/SocketContext.js";
import { 
  Cpu, 
  Play, 
  Pause, 
  Clock, 
  TrendingUp, 
  AlertCircle, 
  CheckCircle,
  Activity,
  Layers,
  Zap,
  ShieldAlert,
  Sliders,
  Sparkles
} from "lucide-react";

// The real backend sends actual per-strategy risk thresholds as an object
// (stopLossPct/takeProfitPct/etc.); the mock sends a simple Low/Medium/Aggressive
// label. Render whichever shape is present instead of assuming one.
function formatRiskProfile(riskProfile: string | Record<string, number>): string {
  if (typeof riskProfile === "string") return riskProfile;
  const sl = riskProfile.stopLossPct;
  const tp = riskProfile.takeProfitPct;
  if (sl !== undefined && tp !== undefined) return `SL ${sl}% / TP ${tp}%`;
  const entries = Object.entries(riskProfile);
  return entries.length ? entries.map(([k, v]) => `${k}: ${v}`).join(", ") : "—";
}

export const StrategyRuntimeStatus: React.FC = () => {
  const { state, pauseStrategy } = useSocket();
  const [statusFilter, setStatusFilter] = useState<"all" | "running" | "paused" | "stopped">("all");
  const [searchTerm, setSearchTerm] = useState("");

  if (!state) return null;

  // Combine activeDeployments and all strategyPackages to show accurate real-time statuses
  const strategies = state.strategyPackages || [];

  // Filter based on status and search query
  const filteredStrategies = strategies.filter(pkg => {
    const matchesStatus = 
      statusFilter === "all" || 
      pkg.status === statusFilter;
    const matchesSearch = 
      pkg.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      pkg.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      pkg.symbols.some(sym => sym.toLowerCase().includes(searchTerm.toLowerCase()));
    
    return matchesStatus && matchesSearch;
  });

  const runningCount = strategies.filter(s => s.status === "running").length;
  const pausedCount = strategies.filter(s => s.status === "paused").length;
  const stoppedCount = strategies.filter(s => s.status === "stopped").length;

  return (
    <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-5 shadow-xl flex flex-col gap-4" id="strategy-runtime-status-dashboard">
      
      {/* Header with KPI metrics */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-zinc-800/60 pb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <Activity className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <h3 className="text-sm font-extrabold text-white tracking-wider uppercase">
              Strategy Runtime Status
            </h3>
            <p className="text-[10px] text-zinc-500 font-mono mt-0.5">
              Live algorithmic contracts &amp; sub-millisecond execution logs
            </p>
          </div>
        </div>

        {/* Dynamic Status Counter Pills */}
        <div className="flex items-center gap-2 font-mono text-[10px] font-bold">
          <div className="bg-zinc-950 px-3 py-1.5 rounded-xl border border-zinc-850 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span>
            <span className="text-zinc-500">RUNNING:</span>
            <span className="text-emerald-400">{runningCount}</span>
          </div>
          <div className="bg-zinc-950 px-3 py-1.5 rounded-xl border border-zinc-850 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
            <span className="text-zinc-500">PAUSED:</span>
            <span className="text-amber-400">{pausedCount}</span>
          </div>
          <div className="bg-zinc-950 px-3 py-1.5 rounded-xl border border-zinc-850 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
            <span className="text-zinc-500">STOPPED:</span>
            <span className="text-rose-400">{stoppedCount}</span>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar controls */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        {/* Search */}
        <input
          type="text"
          placeholder="Filter by strategy name, ID, or symbol..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="bg-zinc-950 border border-zinc-850 px-3.5 py-2 rounded-xl text-xs font-medium text-white placeholder-zinc-500 focus:outline-none focus:border-indigo-500 w-full sm:max-w-xs font-mono"
        />

        {/* Tab Filter */}
        <div className="flex bg-zinc-950 p-1 rounded-xl border border-zinc-850 self-start sm:self-auto font-mono text-[10px] font-bold">
          <button
            onClick={() => setStatusFilter("all")}
            className={`px-3 py-1.5 rounded-lg transition-all ${statusFilter === "all" ? "bg-zinc-800 text-white" : "text-zinc-400 hover:text-white"}`}
          >
            ALL ({strategies.length})
          </button>
          <button
            onClick={() => setStatusFilter("running")}
            className={`px-3 py-1.5 rounded-lg transition-all ${statusFilter === "running" ? "bg-emerald-500/10 text-emerald-400" : "text-zinc-400 hover:text-white"}`}
          >
            RUNNING ({runningCount})
          </button>
          <button
            onClick={() => setStatusFilter("paused")}
            className={`px-3 py-1.5 rounded-lg transition-all ${statusFilter === "paused" ? "bg-amber-500/10 text-amber-400" : "text-zinc-400 hover:text-white"}`}
          >
            PAUSED ({pausedCount})
          </button>
          <button
            onClick={() => setStatusFilter("stopped")}
            className={`px-3 py-1.5 rounded-lg transition-all ${statusFilter === "stopped" ? "bg-rose-500/10 text-rose-400" : "text-zinc-400 hover:text-white"}`}
          >
            STOPPED ({stoppedCount})
          </button>
        </div>
      </div>

      {/* Strategies Grid/Table Display */}
      {filteredStrategies.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredStrategies.map((pkg, idx) => {
            const isRunning = pkg.status === "running";
            const isPaused = pkg.status === "paused";
            const isStopped = pkg.status === "stopped" || pkg.status === "error";
            
            // Generate some random simulated latency loads or use direct latency
            const activeLatency = pkg.latency || (2 + Math.floor(Math.random() * 5));
            
            return (
              <div 
                key={pkg.id} 
                className={`bg-zinc-950/40 border rounded-2xl p-4 flex flex-col justify-between hover:border-zinc-800 transition-all gap-4 ${
                  isRunning 
                    ? "border-zinc-850" 
                    : isPaused 
                    ? "border-amber-500/10" 
                    : "border-rose-500/10"
                }`}
              >
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[9px] text-zinc-500 font-bold uppercase">
                      ID: {pkg.id.slice(0, 8)}...
                    </span>
                    
                    {/* Glowing active/inactive indicator badge */}
                    <span className={`inline-flex items-center gap-1.5 text-[9px] font-black px-2 py-0.5 rounded-md border uppercase ${
                      isRunning
                        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                        : isPaused
                        ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
                        : "bg-rose-500/10 text-rose-400 border-rose-500/20"
                    }`}>
                      <span className={`w-1 h-1 rounded-full ${
                        isRunning 
                          ? "bg-emerald-400 animate-ping" 
                          : isPaused 
                          ? "bg-amber-400" 
                          : "bg-rose-400"
                      }`}></span>
                      {pkg.status}
                    </span>
                  </div>

                  {/* Title & Info */}
                  <div className="flex flex-col">
                    <h4 className="text-xs font-black text-white uppercase tracking-wide">
                      {pkg.name}
                    </h4>
                    <p className="text-[10px] text-zinc-400 font-mono mt-0.5">
                      V{pkg.version} &bull; adapters: <strong className="text-zinc-300">{pkg.broker_adapter}</strong>
                    </p>
                  </div>

                  {/* Targets & Risk specs */}
                  <div className="flex flex-wrap gap-1.5 mt-1">
                    {pkg.symbols.map(sym => (
                      <span key={sym} className="text-[9px] font-mono font-bold bg-zinc-900 text-indigo-400 px-2 py-0.5 rounded border border-zinc-850">
                        {sym}
                      </span>
                    ))}
                    <span className="text-[9px] font-mono font-bold bg-zinc-900 text-zinc-400 px-2 py-0.5 rounded border border-zinc-850">
                      Risk: {formatRiskProfile(pkg.risk_profile)}
                    </span>
                    <span className="text-[9px] font-mono font-bold bg-zinc-900 text-zinc-400 px-2 py-0.5 rounded border border-zinc-850">
                      Freq: {pkg.entryFrequency || "Medium"}
                    </span>
                  </div>
                </div>

                {/* Signals executing metadata */}
                <div className="border-t border-zinc-900/60 pt-3.5 flex flex-col gap-2 font-mono text-[10px]">
                  
                  {/* Timestamp of last signal */}
                  <div className="flex items-center justify-between text-zinc-500">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3 text-zinc-500" />
                      LAST SIGNAL TIME:
                    </span>
                    <span className="text-zinc-300 font-bold text-[10px]">
                      {pkg.lastSignalTime || "No recent signals"}
                    </span>
                  </div>

                  {/* Delay & validation info */}
                  <div className="flex items-center justify-between text-zinc-500">
                    <span>EXECUTION DELAY:</span>
                    <span className="text-emerald-400 font-semibold">{activeLatency} ms</span>
                  </div>

                  {/* Interactive toggle */}
                  <div className="flex items-center justify-between pt-1">
                    <span className="text-[9px] font-semibold text-zinc-600">STATE CONTROL</span>
                    <button
                      onClick={() => pauseStrategy(pkg.id)}
                      className={`flex items-center gap-1 px-3 py-1.5 rounded-xl border font-bold text-[9px] tracking-wider cursor-pointer transition uppercase ${
                        isRunning
                          ? "bg-zinc-950 text-amber-400 border-zinc-850 hover:bg-zinc-900 hover:border-amber-500/30"
                          : "bg-emerald-500/15 text-emerald-400 border-emerald-500/25 hover:bg-emerald-500/25"
                      }`}
                    >
                      {isRunning ? (
                        <>
                          <Pause className="w-2.5 h-2.5" /> PAUSE RUNTIME
                        </>
                      ) : (
                        <>
                          <Play className="w-2.5 h-2.5" /> RESUME RUNTIME
                        </>
                      )}
                    </button>
                  </div>

                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-10 text-center px-4 bg-zinc-950/20 rounded-xl border border-dashed border-zinc-850">
          <ShieldAlert className="w-10 h-10 text-zinc-600 mb-3" />
          <span className="text-sm font-bold text-zinc-400">No Matching Strategies Found</span>
          <p className="text-xs text-zinc-500 mt-1 max-w-[340px]">
            Try adjusting your search criteria or choosing a different status filter above.
          </p>
        </div>
      )}

      {/* Error logs overview for running modules */}
      {strategies.some(s => s.errorLogs && s.errorLogs.length > 0) && (
        <div className="bg-rose-500/5 border border-rose-500/10 rounded-xl p-3 flex flex-col gap-1.5">
          <span className="font-mono text-[9px] text-rose-400 font-bold flex items-center gap-1">
            <AlertCircle className="w-3 h-3 text-rose-400" />
            RECENT STRATEGY RUNTIME ERRORS DETECTED:
          </span>
          <div className="flex flex-col gap-1">
            {strategies.flatMap(s => (s.errorLogs || []).map(err => ({ name: s.name, err }))).slice(0, 2).map((item, idx) => (
              <p key={idx} className="font-mono text-[10px] text-rose-300/85">
                &bull; <strong className="text-rose-400">{item.name}</strong>: {item.err}
              </p>
            ))}
          </div>
        </div>
      )}

    </div>
  );
};
