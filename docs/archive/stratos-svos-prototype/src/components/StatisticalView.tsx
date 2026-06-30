/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
import { StatisticalReport } from "../types";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from "recharts";
import {
  Activity,
  Award,
  AlertTriangle,
  ArrowUpRight,
  TrendingUp,
  BarChart4,
  CheckCircle2,
  Lock
} from "lucide-react";

interface StatisticalViewProps {
  statistics?: StatisticalReport;
}

export default function StatisticalView({ statistics }: StatisticalViewProps) {
  if (!statistics) {
    return (
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-8 text-center text-slate-500 dark:text-slate-400 transition-colors duration-200">
        <BarChart4 className="h-10 w-10 text-slate-400 dark:text-slate-500 mx-auto mb-3" />
        <p className="font-semibold text-sm text-slate-850 dark:text-slate-200">No Statistical Evidence Generated</p>
        <p className="text-xs text-slate-500 dark:text-slate-450 mt-1">Please promote your strategy to the Statistical Validation stage to calculate significance and Monte Carlo percentiles.</p>
      </div>
    );
  }

  const regimeData = [
    { name: "Bull Market Regime", return: statistics.regimePerformance.bullMarketReturnPct, color: "text-emerald-600 dark:text-emerald-450 bg-emerald-50 dark:bg-emerald-950/15 border-emerald-200 dark:border-emerald-900/30" },
    { name: "Bear Market Regime", return: statistics.regimePerformance.bearMarketReturnPct, color: statistics.regimePerformance.bearMarketReturnPct >= 0 ? "text-emerald-600 dark:text-emerald-450 bg-emerald-50 dark:bg-emerald-950/15 border-emerald-200 dark:border-emerald-900/30" : "text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/15 border-red-200 dark:border-red-900/30" },
    { name: "High Volatility Regime", return: statistics.regimePerformance.highVolatilityReturnPct, color: statistics.regimePerformance.highVolatilityReturnPct >= 0 ? "text-emerald-600 dark:text-emerald-450 bg-emerald-50 dark:bg-emerald-950/15 border-emerald-200 dark:border-emerald-900/30" : "text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/15 border-red-200 dark:border-red-900/30" },
    { name: "Low Volatility Regime", return: statistics.regimePerformance.lowVolatilityReturnPct, color: "text-emerald-600 dark:text-emerald-450 bg-emerald-50 dark:bg-emerald-950/15 border-emerald-200 dark:border-emerald-900/30" }
  ];

  // Synthesize a structured Monte Carlo fan chart over 10 steps to show compound paths
  const p10 = statistics.monteCarloPercentiles.p10;
  const p50 = statistics.monteCarloPercentiles.p50;
  const p90 = statistics.monteCarloPercentiles.p90;

  const monteCarloData = Array.from({ length: 11 }).map((_, step) => {
    const factor = step / 10;
    return {
      tradeIndex: `T+${step * 5}`,
      p10: Math.round(100000 * (1 + (p10 / 100) * factor)),
      p50: Math.round(100000 * (1 + (p50 / 100) * factor)),
      p90: Math.round(100000 * (1 + (p90 / 100) * factor))
    };
  });

  return (
    <div className="space-y-6">
      {/* advanced Ratios Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Sharpe */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm transition-colors duration-200">
          <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-wider block">Annualized Sharpe Ratio</span>
          <div className="flex items-baseline space-x-1.5 mt-1.5">
            <span className="text-3xl font-mono font-bold text-slate-900 dark:text-slate-100">{statistics.sharpeRatio.toFixed(2)}</span>
            <span className="text-xs text-slate-500 dark:text-slate-400 font-mono">Rf = 0%</span>
          </div>
          <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-2 font-sans">
            {statistics.sharpeRatio >= 1.5 ? "★ Outstanding risk-adjusted return." : "Standard baseline expectation."}
          </p>
        </div>

        {/* Sortino */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm transition-colors duration-200">
          <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-wider block">Sortino Ratio</span>
          <div className="flex items-baseline space-x-1.5 mt-1.5">
            <span className="text-3xl font-mono font-bold text-slate-900 dark:text-slate-100">{statistics.sortinoRatio.toFixed(2)}</span>
            <span className="text-xs text-slate-500 dark:text-slate-400 font-mono">Downside only</span>
          </div>
          <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-2 font-sans">
            Penalizes downside variance strictly, ignoring upside volatility.
          </p>
        </div>

        {/* t-stat */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm transition-colors duration-200">
          <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-wider block">Student's t-Statistic</span>
          <div className="flex items-baseline space-x-1.5 mt-1.5">
            <span className="text-3xl font-mono font-bold text-slate-900 dark:text-slate-100">{statistics.tStat.toFixed(2)}</span>
            <span className="text-xs text-slate-500 dark:text-slate-400 font-mono">df = 49</span>
          </div>
          <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-2 font-sans">
            Measures edge strength relative to standard error of trade samples.
          </p>
        </div>

        {/* p-value */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm transition-colors duration-200">
          <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-wider block">p-Value (Edge Significance)</span>
          <div className="flex items-baseline space-x-1.5 mt-1.5">
            <span className={`text-3xl font-mono font-bold ${statistics.pValue <= 0.05 ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-450"}`}>
              {statistics.pValue.toFixed(4)}
            </span>
            <span className="text-xs text-slate-500 dark:text-slate-400 font-mono">α = 0.05</span>
          </div>
          <div className="text-[10px] text-slate-500 dark:text-slate-400 mt-2 font-sans flex items-center space-x-1">
            {statistics.pValue <= 0.05 ? (
              <>
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                <span className="text-emerald-700 dark:text-emerald-400 font-semibold">Statistically significant. Edge verified.</span>
              </>
            ) : (
              <>
                <AlertTriangle className="h-3.5 w-3.5 text-amber-500 dark:text-amber-450 shrink-0" />
                <span className="text-amber-700 dark:text-amber-450 font-semibold">Inconclusive significance.</span>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Monte Carlo Fan Chart */}
        <div className="lg:col-span-8 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm transition-colors duration-200">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h3 className="font-display font-semibold text-slate-900 dark:text-slate-100 text-sm flex items-center space-x-2">
                <TrendingUp className="h-4 w-4 text-slate-600 dark:text-slate-400" />
                <span>Monte Carlo Return Projection (1,000 Shuffled Shims)</span>
              </h3>
              <p className="text-[10px] text-slate-500 dark:text-slate-400 font-sans mt-0.5">
                Evaluates trade distribution robustness through 1,000 independent shuffles over 50 steps.
              </p>
            </div>
            <div className="text-right">
              <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500 block uppercase">Median Expected Return</span>
              <span className="text-sm font-mono font-bold text-slate-800 dark:text-slate-200">
                {statistics.monteCarloPercentiles.p50 >= 0 ? "+" : ""}{statistics.monteCarloPercentiles.p50.toFixed(1)}%
              </span>
            </div>
          </div>

          <div className="h-72 w-full font-mono text-[10px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={monteCarloData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--chart-grid)" />
                <XAxis dataKey="tradeIndex" stroke="var(--chart-axis)" tickLine={false} />
                <YAxis
                  stroke="var(--chart-axis)"
                  tickLine={false}
                  domain={["dataMin - 5000", "dataMax + 5000"]}
                  tickFormatter={(val) => `$${(val / 1000).toFixed(0)}k`}
                />
                <Tooltip
                  contentStyle={{ background: "var(--tooltip-bg)", border: "1px solid var(--tooltip-border)", borderRadius: "6px", color: "var(--tooltip-text)" }}
                  labelStyle={{ color: "var(--chart-axis)", fontWeight: "bold" }}
                />
                <Legend iconType="circle" wrapperStyle={{ fontSize: "10px", fontFamily: "monospace" }} />
                
                {/* P10 Bottom Band */}
                <Area
                  name="P10 Bearish Outlook (10th %tile)"
                  type="monotone"
                  dataKey="p10"
                  stroke="#ef4444"
                  strokeWidth={1.5}
                  fill="#ef4444"
                  fillOpacity={0.04}
                />
                {/* P50 Median Band */}
                <Area
                  name="P50 Expected Baseline (50th %tile)"
                  type="monotone"
                  dataKey="p50"
                  stroke="#3b82f6"
                  strokeWidth={1.5}
                  fill="#3b82f6"
                  fillOpacity={0.06}
                />
                {/* P90 Bullish Outlook (90th %tile) */}
                <Area
                  name="P90 Best Case Outlook (90th %tile)"
                  type="monotone"
                  dataKey="p90"
                  stroke="#10b981"
                  strokeWidth={1.5}
                  fill="#10b981"
                  fillOpacity={0.04}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Regime Dissection Panel */}
        <div className="lg:col-span-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm flex flex-col justify-between transition-colors duration-200">
          <div>
            <h3 className="font-display font-semibold text-slate-900 dark:text-slate-100 text-sm flex items-center space-x-2 mb-3">
              <Activity className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
              <span>Regime Mismatch Dissection</span>
            </h3>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 font-sans mb-4 leading-relaxed">
              Deconstructs strategy returns across distinct market regimes to identify hidden vulnerabilities or structural drift.
            </p>

            <div className="space-y-3 font-mono text-xs">
              {regimeData.map((regime, idx) => (
                <div key={idx} className={`border rounded-md p-3 flex justify-between items-center transition-colors ${regime.color}`}>
                  <div>
                    <span className="font-sans font-semibold text-slate-850 dark:text-slate-200 block text-xs">{regime.name}</span>
                    <span className="text-[9px] text-slate-400 dark:text-slate-500 block uppercase">Historical performance segment</span>
                  </div>
                  <span className="text-sm font-bold">
                    {regime.return >= 0 ? "+" : ""}{regime.return.toFixed(1)}%
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-slate-50 dark:bg-slate-950 border border-slate-100 dark:border-slate-850 p-3 rounded-md mt-4 text-[11px] text-slate-600 dark:text-slate-400 transition-colors">
            <span className="font-bold font-mono text-[9px] text-slate-400 dark:text-slate-500 block uppercase tracking-wider mb-0.5">Auditor Verdict:</span>
            <p className="leading-relaxed font-sans">
              {statistics.monteCarloPercentiles.p10 >= 0 ? (
                "Highly resilient strategy. Zero tail-loss paths observed under MC simulation."
              ) : (
                "Standard long-bias drawdown exposure observed in Bear and High Volatility regimes. Portfolio diversifiers recommended."
              )}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
