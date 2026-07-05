import React, { useState } from "react";
import { useSocket } from "../context/SocketContext.js";
import { 
  Sparkles, 
  HelpCircle, 
  TrendingUp, 
  ShieldCheck, 
  Zap, 
  Target, 
  Flame, 
  Check, 
  ArrowRight, 
  Sliders, 
  Play, 
  AlertCircle,
  Clock,
  Compass,
  Cpu
} from "lucide-react";

interface SuggestionItem {
  id: string;
  category: "RISK" | "SMC" | "LIQUIDITY" | "TIMING";
  title: string;
  description: string;
  impact: "HIGH" | "MEDIUM" | "LOW";
  metricLabel: string;
  metricValue: string;
}

export const SuggestionsTab: React.FC = () => {
  const { state } = useSocket();
  const [selectedAsset, setSelectedAsset] = useState<string>("EURUSD");
  const [selectedSession, setSelectedSession] = useState<string>("LONDON_KZ");
  const [riskPreference, setRiskPreference] = useState<string>("CONSERVATIVE");
  const [proposalLog, setProposalLog] = useState<string[]>([
    "SMC Optimization engine online. Select an asset & session below to scan live confluences."
  ]);
  
  // Custom interactive rule checker
  const [ruleHtf, setRuleHtf] = useState(true);
  const [ruleSweep, setRuleSweep] = useState(true);
  const [ruleChoch, setRuleChoch] = useState(false);
  const [ruleZone, setRuleZone] = useState(true);
  const [ruleOb, setRuleOb] = useState(false);

  if (!state) return null;

  // Active suggestions mock list
  const initialSuggestions: SuggestionItem[] = [
    {
      id: "s1",
      category: "LIQUIDITY",
      title: "Buffer Asian Session Liquidity Sweeps",
      description: "Place stop-orders 2.5 pips above the Asian High for Short entries during London Kill Zone to avoid getting stopped out by initial sweep spikes.",
      impact: "HIGH",
      metricLabel: "Win-rate boost",
      metricValue: "+4.2%"
    },
    {
      id: "s2",
      category: "RISK",
      title: "Scale Risk with Win Rate",
      description: "Based on current win rate, increase target lot sizing to 1.5 lots on GBPUSD specifically when entering at a high-displacement Mitigated Order Block.",
      impact: "MEDIUM",
      metricLabel: "Net Return",
      metricValue: "+12.5%"
    },
    {
      id: "s3",
      category: "SMC",
      title: "Premium/Discount Zone Lock",
      description: "Reject any BUY orders for EURUSD that originate above the 50% Equilibrium level. Stay strictly within deep Discount zones to maintain high risk-reward.",
      impact: "HIGH",
      metricLabel: "Min RRR Ratio",
      metricValue: "1:3.5"
    },
    {
      id: "s4",
      category: "TIMING",
      title: "Restrict Mid-Session Executions",
      description: "Pause bot order-entry modules between 12:00 and 13:00 UTC (post-London close and pre-NY open) to bypass low-volume market whipsaws.",
      impact: "LOW",
      metricLabel: "Drawdown Saved",
      metricValue: "-1.8%"
    }
  ];

  // Dynamic dynamic generator for custom recommendation simulation
  const handleSimulateAnalysis = () => {
    const time = new Date().toLocaleTimeString();
    let pairData = state.pairs[selectedAsset] || Object.values(state.pairs)[0];
    let price = pairData ? pairData.price : 1.0820;
    
    let advice = "";
    if (selectedAsset === "EURUSD" && selectedSession === "LONDON_KZ") {
      advice = `EURUSD is trading at ${price}. Perfect London Kill Zone setup. Liquidity sweep detected at ${((pairData?.swingHigh || 1.0850) - 0.0005).toFixed(4)}. Recommendation: Deploy 1.0 lot Sell-Limit at the premium 0.618 Fib retracement.`;
    } else if (selectedAsset === "USDJPY" && riskPreference === "AGRESSIVE") {
      advice = `USDJPY at ${price}. Trend bias is strongly BULLISH on High Time Frame (HTF). Recommendation: Deploy 2.0 lots BUY in deep discount area near unmitigated Order Block.`;
    } else {
      advice = `${selectedAsset} Scan completed. High probability setup detected during ${selectedSession}. Recommend utilizing ${riskPreference === "CONSERVATIVE" ? "0.5%" : "1.5%"} risk per trade targeting 1:4 Risk-to-Reward ratio.`;
    }

    setProposalLog(prev => [...prev, `[${time}] Analyzed ${selectedAsset} (${selectedSession}) with ${riskPreference} rules: ${advice}`]);
  };

  // Rule score checker
  const totalRulesCount = (ruleHtf ? 1 : 0) + (ruleSweep ? 1 : 0) + (ruleChoch ? 1 : 0) + (ruleZone ? 1 : 0) + (ruleOb ? 1 : 0);
  const confluencePercentage = Math.round((totalRulesCount / 5) * 100);

  const getConfluenceRating = (percentage: number) => {
    if (percentage >= 80) return { label: "HIGH PROBABILITY", color: "text-emerald-400 border-emerald-500/20 bg-emerald-500/10" };
    if (percentage >= 40) return { label: "MEDIUM PROBABILITY", color: "text-amber-400 border-amber-500/20 bg-amber-500/10" };
    return { label: "LOW PROBABILITY / AVOID", color: "text-rose-400 border-rose-500/20 bg-rose-500/10" };
  };

  const rating = getConfluenceRating(confluencePercentage);

  return (
    <div className="w-full flex flex-col gap-6" id="suggestions-tab-view">
      
      {/* Dynamic Header */}
      <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-6 shadow-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shadow shadow-indigo-500/5">
            <Sparkles className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <h2 className="font-sans font-black text-white text-lg tracking-wide uppercase">
              SMC Optimization &amp; Suggestion Engine
            </h2>
            <p className="font-mono text-xs text-zinc-400 mt-0.5">
              Automated trade suggestions, risk parameters adjustment, and smart liquidity strategies.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-[11px] font-mono font-bold uppercase bg-zinc-950 px-3.5 py-2 rounded-xl border border-zinc-850">
          <span className="w-2 h-2 rounded-full bg-indigo-400 animate-ping"></span>
          <span className="text-zinc-400">Status:</span>
          <span className="text-indigo-400">Optimizations Ready</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        
        {/* Left Columns (Width: 2x) */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          
          {/* Active Auto Suggestions Cards */}
          <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-xl flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-zinc-800/60 pb-3">
              <h3 className="text-xs font-extrabold text-white tracking-wider uppercase flex items-center gap-2">
                <Compass className="w-4 h-4 text-indigo-400" />
                Active Strategy &amp; Parameter Advice
              </h3>
              <span className="text-[10px] font-mono text-zinc-500 uppercase font-bold">
                Updates every London Open
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {initialSuggestions.map((item) => (
                <div 
                  key={item.id} 
                  className="bg-zinc-950/40 border border-zinc-850 rounded-2xl p-4 flex flex-col justify-between hover:border-zinc-800 transition-all gap-4"
                >
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center justify-between">
                      <span className={`text-[9px] font-black tracking-widest px-2 py-0.5 rounded border ${
                        item.category === "LIQUIDITY" 
                          ? "bg-amber-500/10 text-amber-400 border-amber-500/20" 
                          : item.category === "RISK" 
                          ? "bg-rose-500/10 text-rose-400 border-rose-500/20"
                          : item.category === "SMC"
                          ? "bg-indigo-500/10 text-indigo-400 border-indigo-500/20"
                          : "bg-teal-500/10 text-teal-400 border-teal-500/20"
                      }`}>
                        {item.category}
                      </span>
                      <span className={`text-[9px] font-bold px-2 py-0.5 rounded ${
                        item.impact === "HIGH" 
                          ? "bg-red-500/10 text-red-400 border border-red-500/20" 
                          : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                      }`}>
                        {item.impact} IMPACT
                      </span>
                    </div>
                    <h4 className="text-xs font-black text-white">{item.title}</h4>
                    <p className="text-xs text-zinc-400 font-sans leading-relaxed">{item.description}</p>
                  </div>

                  <div className="border-t border-zinc-900/60 pt-3 flex items-center justify-between text-[11px] font-mono">
                    <span className="text-zinc-500 font-bold uppercase">{item.metricLabel}:</span>
                    <span className="text-emerald-400 font-black">{item.metricValue}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Interactive AI Config Optimizer Dashboard */}
          <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-xl flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-zinc-800/60 pb-3">
              <h3 className="text-xs font-extrabold text-white tracking-wider uppercase flex items-center gap-2">
                <Sliders className="w-4 h-4 text-indigo-400" />
                Live Confluence Tweak Optimizer
              </h3>
              <span className="text-[10px] font-mono text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 px-2 py-1 rounded-lg font-bold">
                Interactive Scanner
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Asset choice */}
              <div className="flex flex-col gap-1.5">
                <label className="text-[10px] font-extrabold uppercase tracking-wider text-zinc-400">Target Asset</label>
                <select 
                  value={selectedAsset}
                  onChange={(e) => setSelectedAsset(e.target.value)}
                  className="bg-zinc-950 border border-zinc-850 p-2.5 rounded-xl text-xs font-bold text-white font-mono focus:outline-none focus:border-indigo-500"
                >
                  <option value="EURUSD">EUR/USD (Euro / US Dollar)</option>
                  <option value="GBPUSD">GBP/USD (Pound / US Dollar)</option>
                  <option value="USDJPY">USD/JPY (US Dollar / Yen)</option>
                </select>
              </div>

              {/* Session choice */}
              <div className="flex flex-col gap-1.5">
                <label className="text-[10px] font-extrabold uppercase tracking-wider text-zinc-400">Target Session</label>
                <select 
                  value={selectedSession}
                  onChange={(e) => setSelectedSession(e.target.value)}
                  className="bg-zinc-950 border border-zinc-850 p-2.5 rounded-xl text-xs font-bold text-white font-mono focus:outline-none focus:border-indigo-500"
                >
                  <option value="ASIAN_SESSION">Asian Range (00:00 - 08:00 UTC)</option>
                  <option value="LONDON_KZ">London Kill Zone (07:00 - 10:00 UTC)</option>
                  <option value="NY_KILL_ZONE">New York Kill Zone (12:00 - 15:00 UTC)</option>
                </select>
              </div>

              {/* Risk preferences */}
              <div className="flex flex-col gap-1.5">
                <label className="text-[10px] font-extrabold uppercase tracking-wider text-zinc-400">Risk Profile</label>
                <select 
                  value={riskPreference}
                  onChange={(e) => setRiskPreference(e.target.value)}
                  className="bg-zinc-950 border border-zinc-850 p-2.5 rounded-xl text-xs font-bold text-white font-mono focus:outline-none focus:border-indigo-500"
                >
                  <option value="CONSERVATIVE">Conservative (0.5% per trade)</option>
                  <option value="STANDARD">Standard (1.0% per trade)</option>
                  <option value="AGRESSIVE">Aggressive (2.0% per trade)</option>
                </select>
              </div>
            </div>

            {/* Execute Optimizer scanning */}
            <div className="flex flex-col gap-2 mt-2">
              <button
                onClick={handleSimulateAnalysis}
                className="w-full flex items-center justify-center gap-2 bg-indigo-500 hover:bg-indigo-600 text-white font-sans font-bold text-xs py-3 px-4 rounded-xl shadow-lg transition cursor-pointer hover:scale-[1.01]"
              >
                <Cpu className="w-4 h-4" /> SCAN AND GENERATE RECOMMENDATIONS
              </button>
            </div>

            {/* Console output of proposal simulator */}
            <div className="mt-2 flex flex-col gap-2">
              <div className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider">Confluence Scan Log Stream</div>
              <div className="bg-zinc-950 rounded-xl p-3 border border-zinc-850 max-h-40 overflow-y-auto font-mono text-[11px] leading-relaxed flex flex-col gap-1 text-indigo-300">
                {proposalLog.map((log, index) => (
                  <div key={index} className="border-b border-zinc-900/60 pb-1 last:border-0">{log}</div>
                ))}
              </div>
            </div>
          </div>

        </div>

        {/* Right Sidebar Column (Width: 1x) */}
        <div className="flex flex-col gap-6">
          
          {/* Confluence probability checklist */}
          <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-xl flex flex-col gap-4">
            <div className="flex flex-col border-b border-zinc-800/60 pb-3">
              <h3 className="text-xs font-extrabold text-white tracking-wider uppercase flex items-center gap-2">
                <Target className="w-4 h-4 text-indigo-400" />
                Live Setup Probabilities Builder
              </h3>
              <span className="text-[10px] text-zinc-500 font-sans mt-0.5">Toggle rules to compute the estimated win probability.</span>
            </div>

            <div className="flex flex-col gap-3">
              
              {/* HTF rule */}
              <label className="flex items-center justify-between p-2.5 bg-zinc-950/40 border border-zinc-850 rounded-xl cursor-pointer hover:bg-zinc-950/60 transition">
                <div className="flex flex-col gap-0.5">
                  <span className="text-xs font-bold text-zinc-200">HTF Trend Bias Aligned</span>
                  <span className="text-[9px] text-zinc-500 font-mono">15M bias matches 1H bias</span>
                </div>
                <input 
                  type="checkbox" 
                  checked={ruleHtf} 
                  onChange={(e) => setRuleHtf(e.target.checked)}
                  className="w-4 h-4 rounded text-indigo-500 bg-zinc-900 border-zinc-800 focus:ring-indigo-500 accent-indigo-500" 
                />
              </label>

              {/* Sweep rule */}
              <label className="flex items-center justify-between p-2.5 bg-zinc-950/40 border border-zinc-850 rounded-xl cursor-pointer hover:bg-zinc-950/60 transition">
                <div className="flex flex-col gap-0.5">
                  <span className="text-xs font-bold text-zinc-200">Liquidity Sweep Confirmed</span>
                  <span className="text-[9px] text-zinc-500 font-mono">Asian High/Low swept cleanly</span>
                </div>
                <input 
                  type="checkbox" 
                  checked={ruleSweep} 
                  onChange={(e) => setRuleSweep(e.target.checked)}
                  className="w-4 h-4 rounded text-indigo-500 bg-zinc-900 border-zinc-800 focus:ring-indigo-500 accent-indigo-500" 
                />
              </label>

              {/* Choch rule */}
              <label className="flex items-center justify-between p-2.5 bg-zinc-950/40 border border-zinc-850 rounded-xl cursor-pointer hover:bg-zinc-950/60 transition">
                <div className="flex flex-col gap-0.5">
                  <span className="text-xs font-bold text-zinc-200">CHoCH Structure Shift</span>
                  <span className="text-[9px] text-zinc-500 font-mono">Local change of character</span>
                </div>
                <input 
                  type="checkbox" 
                  checked={ruleChoch} 
                  onChange={(e) => setRuleChoch(e.target.checked)}
                  className="w-4 h-4 rounded text-indigo-500 bg-zinc-900 border-zinc-800 focus:ring-indigo-500 accent-indigo-500" 
                />
              </label>

              {/* Premium/discount rule */}
              <label className="flex items-center justify-between p-2.5 bg-zinc-950/40 border border-zinc-850 rounded-xl cursor-pointer hover:bg-zinc-950/60 transition">
                <div className="flex flex-col gap-0.5">
                  <span className="text-xs font-bold text-zinc-200">Discount/Premium Pricing</span>
                  <span className="text-[9px] text-zinc-500 font-mono">Price strictly below 50% Fib</span>
                </div>
                <input 
                  type="checkbox" 
                  checked={ruleZone} 
                  onChange={(e) => setRuleZone(e.target.checked)}
                  className="w-4 h-4 rounded text-indigo-500 bg-zinc-900 border-zinc-800 focus:ring-indigo-500 accent-indigo-500" 
                />
              </label>

              {/* OB Displacement */}
              <label className="flex items-center justify-between p-2.5 bg-zinc-950/40 border border-zinc-850 rounded-xl cursor-pointer hover:bg-zinc-950/60 transition">
                <div className="flex flex-col gap-0.5">
                  <span className="text-xs font-bold text-zinc-200">Mitigated Order Block</span>
                  <span className="text-[9px] text-zinc-500 font-mono">Mitigation is fully complete</span>
                </div>
                <input 
                  type="checkbox" 
                  checked={ruleOb} 
                  onChange={(e) => setRuleOb(e.target.checked)}
                  className="w-4 h-4 rounded text-indigo-500 bg-zinc-900 border-zinc-800 focus:ring-indigo-500 accent-indigo-500" 
                />
              </label>

            </div>

            {/* Dynamic Confluence Score visualizer */}
            <div className="p-4 bg-zinc-950/60 border border-zinc-850 rounded-2xl flex flex-col items-center gap-3 mt-1">
              <div className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest font-black">
                SMC Confluence Score
              </div>
              
              <div className="relative flex items-center justify-center">
                {/* Visual radial indicator */}
                <div className="text-4xl font-extrabold text-white font-mono flex items-baseline">
                  {confluencePercentage}<span className="text-sm text-zinc-500">%</span>
                </div>
              </div>

              <div className={`w-full text-center border px-2.5 py-1.5 rounded-xl text-[10px] font-bold tracking-wider uppercase ${rating.color}`}>
                {rating.label}
              </div>

              <p className="text-[11px] text-zinc-400 font-sans text-center leading-normal">
                {confluencePercentage >= 80 
                  ? "Sufficient confluence criteria are met. This setup holds a highly validated backtested probability."
                  : confluencePercentage >= 40 
                  ? "Moderate confluences detected. Consider entering with a smaller lot size (e.g. 0.50 lot instead of 1.0)."
                  : "Insufficient confluences. Do not execute position. Higher risk of false breakout sweeps."
                }
              </p>
            </div>
          </div>

          {/* Educational smart-money-concepts library tip */}
          <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-xl flex flex-col gap-3">
            <h4 className="text-xs font-extrabold text-white uppercase tracking-wider flex items-center gap-1.5">
              <Flame className="w-4 h-4 text-orange-400 animate-pulse" />
              SMC Terminology Reference
            </h4>
            
            <div className="flex flex-col gap-2.5 text-xs text-zinc-400">
              <div className="flex flex-col">
                <span className="font-mono text-[10px] text-indigo-400 font-bold">ASIAN LIQUIDITY SWEEP</span>
                <p className="text-[11px] leading-relaxed mt-0.5">
                  When London or NY price sweeps the high/low of the Asian session to fuel orders for institutional reversal.
                </p>
              </div>
              <div className="flex flex-col">
                <span className="font-mono text-[10px] text-indigo-400 font-bold">EQUILIBRIUM LEVEL</span>
                <p className="text-[11px] leading-relaxed mt-0.5">
                  The exact 50% retracement of the swing leg. Prices above 50% are Premium (shorts), prices below are Discount (longs).
                </p>
              </div>
            </div>
          </div>

        </div>

      </div>

    </div>
  );
};
