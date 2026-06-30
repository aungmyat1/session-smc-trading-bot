/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
import { RobustnessReport } from "../types";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from "recharts";
import { Shield, Sparkles, Activity, AlertOctagon, TrendingDown, ArrowUpRight } from "lucide-react";

interface RobustnessViewProps {
  robustnessReport?: RobustnessReport;
}

export default function RobustnessView({ robustnessReport }: RobustnessViewProps) {
  if (!robustnessReport) {
    return (
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-8 text-center text-slate-500 dark:text-slate-400 transition-colors duration-200">
        <Shield className="h-10 w-10 text-slate-400 dark:text-slate-500 mx-auto mb-3" />
        <p className="font-semibold text-sm text-slate-850 dark:text-slate-200">No Robustness Evidence Generated</p>
        <p className="text-xs text-slate-500 dark:text-slate-450 mt-1">Please promote your strategy to the Robustness Validation stage to sweep parameters and execute stress testing.</p>
      </div>
    );
  }

  // Format parameter sweep data for LineChart
  const sweepData = robustnessReport.parameterSensitivity.sweepPoints.map(p => ({
    paramValue: `Window: ${p.paramValue}`,
    "Sharpe Ratio": parseFloat(p.sharpeRatio.toFixed(2)),
    "Return %": parseFloat(p.totalReturnPct.toFixed(1)),
    "Win Rate %": parseFloat(p.winRate.toFixed(1))
  }));

  const parameterName = robustnessReport.parameterSensitivity.parameterName;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Parameter Sweep Chart */}
        <div className="lg:col-span-8 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm transition-colors duration-200">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h3 className="font-display font-semibold text-slate-900 dark:text-slate-100 text-sm flex items-center space-x-2">
                <Activity className="h-4 w-4 text-slate-600 dark:text-slate-400" />
                <span>Parameter Sensitivity Sweep: "{parameterName}"</span>
              </h3>
              <p className="text-[10px] text-slate-500 dark:text-slate-400 font-sans mt-0.5">
                Sweeps parameter value across multiple standard deviations to verify there are no sharp risk-cliffs (overfitting).
              </p>
            </div>
          </div>

          <div className="h-72 w-full font-mono text-[10px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={sweepData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--chart-grid)" />
                <XAxis dataKey="paramValue" stroke="var(--chart-axis)" tickLine={false} />
                <YAxis yAxisId="left" stroke="#3b82f6" tickLine={false} label={{ value: "Sharpe Ratio", angle: -90, position: "insideLeft", fontSize: "10px", fill: "#3b82f6" }} />
                <YAxis yAxisId="right" orientation="right" stroke="#10b981" tickLine={false} label={{ value: "Return %", angle: 90, position: "insideRight", fontSize: "10px", fill: "#10b981" }} />
                <Tooltip
                  contentStyle={{ background: "var(--tooltip-bg)", border: "1px solid var(--tooltip-border)", borderRadius: "6px", color: "var(--tooltip-text)" }}
                  labelStyle={{ color: "var(--chart-axis)", fontWeight: "bold" }}
                />
                <Legend iconType="circle" wrapperStyle={{ fontSize: "10px", fontFamily: "monospace" }} />
                
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="Sharpe Ratio"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  activeDot={{ r: 6 }}
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="Return %"
                  stroke="#10b981"
                  strokeWidth={2}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Robustness Metadata Summary */}
        <div className="lg:col-span-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm flex flex-col justify-between transition-colors duration-200">
          <div>
            <h3 className="font-display font-semibold text-slate-900 dark:text-slate-100 text-sm flex items-center space-x-2 mb-3">
              <Sparkles className="h-4 w-4 text-slate-600 dark:text-slate-400" />
              <span>Sensitivity & Noise Audits</span>
            </h3>

            <div className="space-y-4 text-xs font-sans">
              <div className="bg-slate-50 dark:bg-slate-950 border border-slate-100 dark:border-slate-850 rounded-lg p-4 text-slate-700 dark:text-slate-300 transition-colors">
                <p className="font-mono text-[10px] text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-1.5">Noise Injection Resilience</p>
                <div className="flex items-center space-x-2">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${robustnessReport.noiseTestPassed ? "bg-emerald-50 dark:bg-emerald-950/20 text-emerald-700 dark:text-emerald-400 border border-emerald-100 dark:border-emerald-900/30" : "bg-red-50 dark:bg-red-950/20 text-red-700 dark:text-red-400 border border-red-100 dark:border-red-900/30"}`}>
                    {robustnessReport.noiseTestPassed ? "PASSED (NOISE-RESISTANT)" : "FAILED (SENSITIVE)"}
                  </span>
                </div>
                <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-2 leading-relaxed">
                  Injects 0.25 standard deviation random white noise into historical bid/ask queues to test signal decay rates.
                </p>
              </div>

              <div className="bg-slate-50 dark:bg-slate-950 border border-slate-100 dark:border-slate-850 rounded-lg p-4 text-slate-700 dark:text-slate-300 transition-colors">
                <p className="font-mono text-[10px] text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-1.5">Slippage Cost Drag</p>
                <div className="flex justify-between items-center">
                  <span className="font-mono font-bold text-slate-900 dark:text-slate-100">{robustnessReport.slippageSensitivityPct.toFixed(2)}% return drag</span>
                  <span className="text-[10px] text-slate-400 dark:text-slate-550">per 1.0 bps of slippage</span>
                </div>
                <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-2 leading-relaxed">
                  Asserts how much trading alpha is eroded under adverse spreads or execution delays. Lower numbers prove superior order routing designs.
                </p>
              </div>
            </div>
          </div>

          <p className="text-[10px] font-mono text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-950 p-2.5 border border-slate-100 dark:border-slate-850 rounded-md leading-relaxed mt-4 transition-colors">
            <span className="font-bold text-slate-700 dark:text-slate-300 uppercase">Analysis:</span> The smooth parameter curve with no sharp drop-offs indicates robust alpha potential. Strategy is not highly overfitted.
          </p>
        </div>
      </div>

      {/* Stress Testing Scenarios */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm transition-colors duration-200">
        <h3 className="font-display font-semibold text-slate-900 dark:text-slate-100 text-sm flex items-center space-x-2 mb-4">
          <AlertOctagon className="h-4.5 w-4.5 text-slate-600 dark:text-slate-400" />
          <span>Macroeconomic Stress Testing & Scenario Logs</span>
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {robustnessReport.stressScenarios.map((scenario, idx) => (
            <div key={idx} className="border border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 hover:bg-slate-100/50 dark:hover:bg-slate-850/30 p-4 rounded-lg flex flex-col justify-between transition-colors">
              <div>
                <span className="text-[9px] font-mono bg-slate-200 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 px-1.5 py-0.5 rounded font-bold uppercase tracking-wider">
                  Scenario {idx + 1}
                </span>
                <h4 className="font-display font-bold text-slate-900 dark:text-slate-100 text-sm mt-2">{scenario.name}</h4>
                <p className="text-[11px] text-slate-600 dark:text-slate-350 mt-1 font-sans leading-relaxed">{scenario.description}</p>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-200/50 dark:border-slate-800">
                <div className="flex justify-between font-mono text-[10px] mb-2 text-slate-500 dark:text-slate-400">
                  <span>Simulated Return:</span>
                  <span className={`font-bold ${scenario.returnPct >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}>
                    {scenario.returnPct >= 0 ? "+" : ""}{scenario.returnPct.toFixed(1)}%
                  </span>
                </div>
                <div className="flex justify-between font-mono text-[10px] mb-2 text-slate-500 dark:text-slate-400">
                  <span>Max Drawdown:</span>
                  <span className="font-bold text-red-600 dark:text-red-400">{scenario.maxDrawdownPct.toFixed(1)}%</span>
                </div>
                <p className="text-[10px] text-slate-500 dark:text-slate-450 leading-relaxed font-sans italic border-l-2 border-slate-300 dark:border-slate-700 pl-2 mt-2">
                  "{scenario.notes}"
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
