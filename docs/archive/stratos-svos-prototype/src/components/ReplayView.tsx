/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from "react";
import { ReplayReport, Trade } from "../types";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from "recharts";
import {
  TrendingUp,
  Activity,
  AlertTriangle,
  ArrowUpRight,
  ArrowDownRight,
  HelpCircle,
  FileText,
  Brain,
  RefreshCw,
  Search,
  CheckCircle2
} from "lucide-react";

interface ReplayViewProps {
  replayReport?: ReplayReport;
  strategyName: string;
}

export default function ReplayView({ replayReport, strategyName }: ReplayViewProps) {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [aiDiagnosis, setAiDiagnosis] = useState<any | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [tradeFilter, setTradeFilter] = useState<"ALL" | "WIN" | "LOSS">("ALL");

  if (!replayReport) {
    return (
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-8 text-center text-slate-500 dark:text-slate-400 transition-colors duration-200 animate-fade-in">
        <Activity className="h-10 w-10 text-slate-400 dark:text-slate-500 mx-auto mb-3" />
        <p className="font-semibold text-sm text-slate-800 dark:text-slate-200">No Replay Evidence Generated</p>
        <p className="text-xs text-slate-500 dark:text-slate-450 mt-1">Please promote your strategy to the Historical Replay stage to run simulation engines.</p>
      </div>
    );
  }

  // Handle AI failure diagnosis
  const handleAiDiagnosis = async () => {
    const lossTrades = replayReport.trades.filter(t => t.profit < 0);
    if (lossTrades.length === 0) {
      setAiDiagnosis({
        primaryCause: "Strategy has zero losses over backtest period.",
        diagnosis: "Perfect performance over active backtest sample. No structural failures identified.",
        actionableFixes: ["Increase backtest window to verify performance in bear markets."]
      });
      return;
    }

    setIsAnalyzing(true);
    try {
      const response = await fetch("/api/gemini/explain-failure", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          trades: lossTrades,
          strategyName
        })
      });

      if (!response.ok) {
        throw new Error("Failed to get diagnosis.");
      }

      const data = await response.json();
      setAiDiagnosis(data);
    } catch (e) {
      console.error(e);
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Filtered trades
  const filteredTrades = replayReport.trades.filter(t => {
    const matchesSearch = t.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          t.entryTime.includes(searchTerm) ||
                          t.exitTime.includes(searchTerm);
    const matchesFilter = tradeFilter === "ALL" ||
                          (tradeFilter === "WIN" && t.profit > 0) ||
                          (tradeFilter === "LOSS" && t.profit <= 0);
    return matchesSearch && matchesFilter;
  });

  // Calculate metrics
  const totalTrades = replayReport.totalTrades;
  const winRatePct = (replayReport.winRate * 100).toFixed(1);
  const totalReturn = replayReport.totalReturnPct.toFixed(2);
  const drawdownPct = (replayReport.maxDrawdown * 100).toFixed(1);
  const profitFactor = replayReport.profitFactor.toFixed(2);

  // Formatting chart data
  const chartData = replayReport.equityCurve.map(pt => ({
    time: pt.time,
    Equity: Math.round(pt.equity),
    Drawdown: parseFloat((pt.drawdown * 100).toFixed(2)),
    AssetPrice: parseFloat(pt.price.toFixed(2))
  }));

  return (
    <div className="space-y-6">
      {/* Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-4 shadow-sm transition-colors duration-200">
          <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-wider block">Total Simulated Return</span>
          <div className="flex items-baseline space-x-1.5 mt-1">
            <span className={`text-2xl font-mono font-bold ${replayReport.totalReturnPct >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}>
              {replayReport.totalReturnPct >= 0 ? "+" : ""}{totalReturn}%
            </span>
          </div>
          <span className="text-[10px] font-mono text-slate-500 dark:text-slate-400 block mt-1">Starting Capital: $100,000</span>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-4 shadow-sm transition-colors duration-200">
          <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-wider block">Win Rate</span>
          <div className="flex items-baseline space-x-1.5 mt-1">
            <span className="text-2xl font-mono font-bold text-slate-900 dark:text-slate-100">{winRatePct}%</span>
          </div>
          <span className="text-[10px] font-mono text-slate-500 dark:text-slate-400 block mt-1">{replayReport.winningTrades} Wins / {replayReport.losingTrades} Losses</span>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-4 shadow-sm transition-colors duration-200">
          <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-wider block">Profit Factor</span>
          <div className="flex items-baseline space-x-1.5 mt-1">
            <span className="text-2xl font-mono font-bold text-slate-900 dark:text-slate-100">{profitFactor}</span>
          </div>
          <span className="text-[10px] font-mono text-slate-500 dark:text-slate-400 block mt-1">Gross Win/Loss ratio</span>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-4 shadow-sm transition-colors duration-200">
          <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-wider block">Maximum Drawdown</span>
          <div className="flex items-baseline space-x-1.5 mt-1">
            <span className="text-2xl font-mono font-bold text-red-600 dark:text-red-400">{drawdownPct}%</span>
          </div>
          <span className="text-[10px] font-mono text-slate-500 dark:text-slate-400 block mt-1">Peak-to-trough drop</span>
        </div>
      </div>

      {/* Equity Curve Chart */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm transition-colors duration-200">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h3 className="font-display font-semibold text-slate-900 dark:text-slate-100 text-sm flex items-center space-x-2">
              <TrendingUp className="h-4 w-4 text-slate-600 dark:text-slate-400" />
              <span>Simulated Cumulative Equity Curve</span>
            </h3>
            <p className="text-[10px] text-slate-500 dark:text-slate-400 font-sans mt-0.5">Chronological trade compounding path</p>
          </div>
        </div>

        <div className="h-72 w-full font-mono text-[10px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--chart-grid)" />
              <XAxis dataKey="time" stroke="var(--chart-axis)" tickLine={false} />
              <YAxis
                stroke="var(--chart-axis)"
                tickLine={false}
                domain={["dataMin - 1000", "dataMax + 1000"]}
                tickFormatter={(val) => `$${(val / 1000).toFixed(0)}k`}
              />
              <Tooltip
                contentStyle={{ background: "var(--tooltip-bg)", border: "1px solid var(--tooltip-border)", borderRadius: "6px", color: "var(--tooltip-text)" }}
                labelStyle={{ color: "var(--chart-axis)", fontWeight: "bold" }}
              />
              <Area
                type="monotone"
                dataKey="Equity"
                stroke="#10b981"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#colorEquity)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Trades Registry Log */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm transition-colors duration-200">
        <div className="flex flex-col sm:flex-row justify-between sm:items-center border-b border-slate-100 dark:border-slate-800 pb-4 mb-4 gap-3">
          <div>
            <h3 className="font-display font-semibold text-slate-900 dark:text-slate-100 text-sm flex items-center space-x-2">
              <FileText className="h-4 w-4 text-slate-600 dark:text-slate-400" />
              <span>Evidence Ledger: Trade History</span>
            </h3>
            <p className="text-[10px] text-slate-500 dark:text-slate-400 font-sans mt-0.5">{replayReport.trades.length} trades recorded in history</p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Search */}
            <div className="relative">
              <Search className="h-3.5 w-3.5 absolute left-2.5 top-2.5 text-slate-400 dark:text-slate-500" />
              <input
                type="text"
                placeholder="Search trade ID..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="font-sans text-xs bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-slate-100 rounded-md pl-8 pr-3 py-1.5 w-36 focus:outline-none focus:ring-1 focus:ring-slate-900 dark:focus:ring-slate-100"
                id="trades-search-input"
              />
            </div>

            {/* Filter buttons */}
            <div className="flex border border-slate-200 dark:border-slate-800 rounded-md p-0.5 bg-slate-50 dark:bg-slate-950 text-[10px] font-mono">
              <button
                onClick={() => setTradeFilter("ALL")}
                className={`px-2 py-1 rounded cursor-pointer ${tradeFilter === "ALL" ? "bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 font-bold shadow-sm" : "text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200"}`}
                id="filter-all-trades"
              >
                ALL
              </button>
              <button
                onClick={() => setTradeFilter("WIN")}
                className={`px-2 py-1 rounded cursor-pointer ${tradeFilter === "WIN" ? "bg-white dark:bg-slate-800 text-emerald-600 dark:text-emerald-400 font-bold shadow-sm" : "text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200"}`}
                id="filter-win-trades"
              >
                WINS
              </button>
              <button
                onClick={() => setTradeFilter("LOSS")}
                className={`px-2 py-1 rounded cursor-pointer ${tradeFilter === "LOSS" ? "bg-white dark:bg-slate-800 text-red-600 dark:text-red-400 font-bold shadow-sm" : "text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200"}`}
                id="filter-loss-trades"
              >
                LOSS
              </button>
            </div>
          </div>
        </div>

        {/* Trade List Table */}
        <div className="overflow-x-auto max-h-72 dark-scrollbar">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-100 dark:border-slate-800 text-[10px] font-mono uppercase text-slate-400 dark:text-slate-500 tracking-wider">
                <th className="pb-2">ID</th>
                <th className="pb-2">Type</th>
                <th className="pb-2">Entry Price / Time</th>
                <th className="pb-2">Exit Price / Time</th>
                <th className="pb-2 text-right">Qty</th>
                <th className="pb-2 text-right">PnL (%)</th>
                <th className="pb-2 text-right">Return ($)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50 dark:divide-slate-800/50 font-mono text-[11px] text-slate-700 dark:text-slate-300">
              {filteredTrades.map((t) => (
                <tr key={t.id} className="hover:bg-slate-50 dark:hover:bg-slate-850/30 transition-colors">
                  <td className="py-2.5 font-bold text-slate-900 dark:text-slate-100">{t.id}</td>
                  <td className="py-2.5">
                    <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${t.type === "BUY" ? "bg-emerald-50 dark:bg-emerald-950/20 text-emerald-700 dark:text-emerald-400 border border-emerald-100 dark:border-emerald-900/30" : "bg-red-50 dark:bg-red-950/20 text-red-700 dark:text-red-400 border border-red-100 dark:border-red-900/30"}`}>
                      {t.type}
                    </span>
                  </td>
                  <td className="py-2.5">
                    <span className="font-semibold text-slate-900 dark:text-slate-100">${t.entryPrice.toFixed(2)}</span>
                    <span className="block text-[9px] text-slate-400 dark:text-slate-500">{t.entryTime}</span>
                  </td>
                  <td className="py-2.5">
                    <span className="font-semibold text-slate-900 dark:text-slate-100">${t.exitPrice.toFixed(2)}</span>
                    <span className="block text-[9px] text-slate-400 dark:text-slate-500">{t.exitTime}</span>
                  </td>
                  <td className="py-2.5 text-right">{t.quantity.toFixed(0)}</td>
                  <td className={`py-2.5 text-right font-bold ${t.profitPct >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}>
                    {t.profitPct >= 0 ? "+" : ""}{t.profitPct.toFixed(2)}%
                  </td>
                  <td className={`py-2.5 text-right font-bold ${t.profit >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}>
                    {t.profit >= 0 ? "+" : ""}${Math.round(t.profit).toLocaleString()}
                  </td>
                </tr>
              ))}
              {filteredTrades.length === 0 && (
                <tr>
                  <td colSpan={7} className="text-center py-6 text-slate-400 dark:text-slate-500 italic">No historical trades found matching search filters.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* AI Failure Diagnostics */}
      <div className="bg-slate-900 text-slate-100 rounded-lg p-5 border border-slate-800 shadow-lg">
        <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4 border-b border-slate-800 pb-4 mb-4">
          <div className="flex items-center space-x-2.5">
            <div className="bg-slate-800 p-1.5 rounded-lg border border-slate-700">
              <Brain className="h-5 w-5 text-indigo-400 animate-pulse" />
            </div>
            <div>
              <h3 className="font-display font-bold text-sm text-white">AI-Assisted Root Cause Diagnosis</h3>
              <p className="text-[10px] text-slate-400">Instruct Gemini to analyze and diagnose strategy losses</p>
            </div>
          </div>

          <button
            onClick={handleAiDiagnosis}
            disabled={isAnalyzing}
            className="bg-indigo-600 hover:bg-indigo-500 text-white font-mono text-xs uppercase px-4 py-2 rounded-md flex items-center justify-center space-x-2 border border-indigo-700 disabled:opacity-50 transition-colors"
            id="replay-trigger-ai-diagnosis"
          >
            {isAnalyzing ? (
              <>
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                <span>Deconstructing Trades...</span>
              </>
            ) : (
              <>
                <Brain className="h-3.5 w-3.5" />
                <span>Diagnose Failures</span>
              </>
            )}
          </button>
        </div>

        {aiDiagnosis ? (
          <div className="space-y-4 text-xs">
            <div className="bg-slate-950 border border-slate-800 rounded-lg p-4 font-sans text-slate-300 leading-relaxed">
              <div className="flex items-start space-x-2">
                <AlertTriangle className="h-5 w-5 text-indigo-400 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-white font-mono text-[10px] tracking-wider uppercase text-slate-400">
                    Primary Loss Variable:
                  </p>
                  <p className="font-bold text-slate-100 text-sm mt-0.5">{aiDiagnosis.primaryCause}</p>
                  <p className="mt-3 text-slate-300 leading-relaxed">{aiDiagnosis.diagnosis}</p>
                </div>
              </div>
            </div>

            <div className="bg-indigo-950/40 border border-indigo-900/30 rounded-lg p-4">
              <p className="font-bold font-mono text-[10px] uppercase text-indigo-300 tracking-wider mb-2 flex items-center space-x-1.5">
                <CheckCircle2 className="h-3.5 w-3.5 text-indigo-400" />
                <span>Actionable Strategic Rectifications:</span>
              </p>
              <ul className="list-disc list-inside space-y-1.5 font-sans text-slate-300">
                {aiDiagnosis.actionableFixes.map((fix: string, idx: number) => (
                  <li key={idx} className="marker:text-indigo-400">{fix}</li>
                ))}
              </ul>
            </div>
          </div>
        ) : (
          <div className="text-center py-6 text-slate-500 border border-dashed border-slate-800 rounded-lg text-xs">
            No diagnostic run completed. Click the button above to feed transaction logs to Gemini.
          </div>
        )}
      </div>
    </div>
  );
}
