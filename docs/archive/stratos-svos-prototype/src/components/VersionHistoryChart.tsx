/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from "recharts";
import { Strategy, VersionHistoryPoint } from "../types";
import { TrendingUp, Award, ShieldAlert, Sparkles, AlertCircle, BarChart3 } from "lucide-react";

interface VersionHistoryChartProps {
  strategy: Strategy;
  compareStrategy?: Strategy | null;
}

export default function VersionHistoryChart({ strategy, compareStrategy }: VersionHistoryChartProps) {
  const [compareMetric, setCompareMetric] = useState<"return" | "audit" | "safety" | "all">("all");
  const [showSMA, setShowSMA] = useState(true);
  const [smaWindow, setSmaWindow] = useState(3);

  const historyA = strategy.versionHistory || [];
  const historyB = compareStrategy?.versionHistory || [];

  if (historyA.length === 0 && historyB.length === 0) {
    return (
      <div className="bg-white border border-slate-200 rounded-lg p-6 shadow-sm flex flex-col justify-center items-center h-64 text-center">
        <AlertCircle className="h-8 w-8 text-slate-300 mb-2" />
        <p className="text-xs font-mono text-slate-500 uppercase tracking-widest">No Version History Available</p>
        <p className="text-[11px] text-slate-400 mt-1 max-w-xs">
          Promote this strategy through the validation gates to populate its version checkpoints and track scores.
        </p>
      </div>
    );
  }

  // Helper to calculate simple moving average
  const calculateSMA = (values: number[], windowSize: number): number[] => {
    const result: number[] = [];
    for (let i = 0; i < values.length; i++) {
      const start = Math.max(0, i - windowSize + 1);
      const sub = values.slice(start, i + 1);
      const sum = sub.reduce((acc, val) => acc + val, 0);
      result.push(sum / sub.length);
    }
    return result;
  };

  // Pre-calculate SMAs
  const auditScoresA = historyA.map(h => h.auditScore);
  const safetyScoresA = historyA.map(h => h.safetyScore);
  const returnScoresA = historyA.map(h => h.backtestReturnPct);

  const auditSMA_A = calculateSMA(auditScoresA, smaWindow);
  const safetySMA_A = calculateSMA(safetyScoresA, smaWindow);
  const returnSMA_A = calculateSMA(returnScoresA, smaWindow);

  const auditScoresB = historyB.map(h => h.auditScore);
  const safetyScoresB = historyB.map(h => h.safetyScore);
  const returnScoresB = historyB.map(h => h.backtestReturnPct);

  const auditSMA_B = calculateSMA(auditScoresB, smaWindow);
  const safetySMA_B = calculateSMA(safetyScoresB, smaWindow);
  const returnSMA_B = calculateSMA(returnScoresB, smaWindow);

  // Determine chart format based on comparison mode
  let data: any[] = [];
  let isComparisonMode = !!compareStrategy;

  if (isComparisonMode) {
    const maxLength = Math.max(historyA.length, historyB.length);
    data = Array.from({ length: maxLength }).map((_, idx) => {
      const pA = historyA[idx];
      const pB = historyB[idx];
      return {
        step: `Step ${idx + 1}`,
        versionA: pA ? pA.version : "",
        versionB: pB ? pB.version : "",
        dateA: pA ? pA.date : "",
        dateB: pB ? pB.date : "",
        [`${strategy.name} Return %`]: pA ? pA.backtestReturnPct : null,
        [`${strategy.name} Return % SMA`]: pA ? parseFloat(returnSMA_A[idx].toFixed(1)) : null,
        [`${strategy.name} Audit Score`]: pA ? pA.auditScore : null,
        [`${strategy.name} Audit Score SMA`]: pA ? parseFloat(auditSMA_A[idx].toFixed(1)) : null,
        [`${strategy.name} Safety Score`]: pA ? pA.safetyScore : null,
        [`${strategy.name} Safety Score SMA`]: pA ? parseFloat(safetySMA_A[idx].toFixed(1)) : null,
        [`${compareStrategy?.name} Return %`]: pB ? pB.backtestReturnPct : null,
        [`${compareStrategy?.name} Return % SMA`]: pB ? parseFloat(returnSMA_B[idx].toFixed(1)) : null,
        [`${compareStrategy?.name} Audit Score`]: pB ? pB.auditScore : null,
        [`${compareStrategy?.name} Audit Score SMA`]: pB ? parseFloat(auditSMA_B[idx].toFixed(1)) : null,
        [`${compareStrategy?.name} Safety Score`]: pB ? pB.safetyScore : null,
        [`${compareStrategy?.name} Safety Score SMA`]: pB ? parseFloat(safetySMA_B[idx].toFixed(1)) : null,
      };
    });
  } else {
    data = historyA.map((point, idx) => ({
      version: point.version,
      date: point.date,
      "Audit Score": point.auditScore,
      "Audit Score SMA": parseFloat(auditSMA_A[idx].toFixed(1)),
      "Safety Score": point.safetyScore,
      "Safety Score SMA": parseFloat(safetySMA_A[idx].toFixed(1)),
      "Backtest Return %": point.backtestReturnPct,
      "Backtest Return % SMA": parseFloat(returnSMA_A[idx].toFixed(1)),
      status: point.status || "Validation Stage"
    }));
  }

  // Calculate stats for Primary
  const firstPointA = historyA[0] || { auditScore: 0, safetyScore: 0, backtestReturnPct: 0 };
  const lastPointA = historyA[historyA.length - 1] || { auditScore: 0, safetyScore: 0, backtestReturnPct: 0 };
  const auditImprovementA = lastPointA.auditScore - firstPointA.auditScore;
  const safetyImprovementA = lastPointA.safetyScore - firstPointA.safetyScore;
  const returnImprovementA = lastPointA.backtestReturnPct - firstPointA.backtestReturnPct;

  // Calculate stats for Comparison
  const firstPointB = historyB[0] || { auditScore: 0, safetyScore: 0, backtestReturnPct: 0 };
  const lastPointB = historyB[historyB.length - 1] || { auditScore: 0, safetyScore: 0, backtestReturnPct: 0 };
  const auditImprovementB = lastPointB.auditScore - firstPointB.auditScore;
  const safetyImprovementB = lastPointB.safetyScore - firstPointB.safetyScore;
  const returnImprovementB = lastPointB.backtestReturnPct - firstPointB.backtestReturnPct;

  // Custom Tooltip
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const dataPoint = payload[0].payload;
      return (
        <div className="bg-slate-950 text-slate-50 border border-slate-800 p-3 rounded-lg shadow-xl font-mono text-[10px] space-y-1.5 max-w-xs">
          <div className="border-b border-slate-800 pb-1 mb-1 flex justify-between items-center">
            <span className="font-bold text-slate-200 text-[11px]">{label}</span>
            <span className="text-slate-500 text-[9px]">Checkpoint Info</span>
          </div>
          {isComparisonMode ? (
            <div className="space-y-1 text-[9px] mb-2 leading-tight text-slate-300">
              <div>
                <span className="text-white font-semibold">Primary: </span>
                {dataPoint.versionA ? `${dataPoint.versionA} (${dataPoint.dateA})` : "N/A"}
              </div>
              <div>
                <span className="text-white font-semibold">Compare: </span>
                {dataPoint.versionB ? `${dataPoint.versionB} (${dataPoint.dateB})` : "N/A"}
              </div>
            </div>
          ) : (
            <p className="text-slate-400 mb-1 leading-relaxed text-[9px]">
              Stage: <span className="text-white font-semibold">{dataPoint.status}</span>
            </p>
          )}
          <div className="space-y-1">
            {payload.map((item: any) => (
              <div key={item.name} className="flex justify-between items-center space-x-4">
                <span className="flex items-center space-x-1">
                  <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: item.color }} />
                  <span className="text-slate-400 truncate max-w-[140px]">{item.name}</span>
                </span>
                <span className="font-bold font-mono text-right" style={{ color: item.color }}>
                  {item.value !== null && item.value !== undefined 
                    ? `${item.value.toFixed(1)}${item.name.includes("%") || item.name.includes("Return") ? "%" : ""}` 
                    : "N/A"}
                </span>
              </div>
            ))}
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-6 shadow-sm space-y-5 transition-colors duration-200" id="registry-trend-chart-card">
      <div className="flex flex-col xl:flex-row xl:justify-between xl:items-start border-b border-slate-100 dark:border-slate-800 pb-4 gap-4">
        <div>
          <span className="text-[10px] font-mono text-indigo-600 dark:text-indigo-400 font-semibold uppercase tracking-widest block flex items-center space-x-1">
            <Sparkles className="h-3 w-3" />
            <span>{isComparisonMode ? "Benchmarking Strategy Comparison Overlay" : "Institutional Metric Tracker"}</span>
          </span>
          <h3 className="font-display font-bold text-slate-900 dark:text-slate-100 text-base mt-1">
            {isComparisonMode 
              ? `Performance Trends: ${strategy.name} vs ${compareStrategy?.name}` 
              : "Historical Validation &amp; Score Evolution"}
          </h3>
          <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
            {isComparisonMode
              ? "Overlaying validation scores and simulated return rates to evaluate relative strengths."
              : "Progressive tracking of compliance scores and simulated alpha performance over version history."}
          </p>
        </div>

        {/* Dynamic Controls: Metric Selector & SMA Toggle Options */}
        <div className="flex flex-wrap gap-3 items-center self-start xl:self-center">
          {/* SMA Moving Average Controls */}
          <div className="flex items-center space-x-2 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 px-2.5 py-1 rounded-md text-[10px] font-mono">
            <span className="text-slate-500 dark:text-slate-400 font-medium">Trend (SMA):</span>
            <button
              onClick={() => setShowSMA(!showSMA)}
              className={`px-1.5 py-0.5 rounded transition-all font-bold cursor-pointer ${
                showSMA 
                  ? "bg-indigo-600 text-white" 
                  : "bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-300 dark:hover:bg-slate-700"
              }`}
              title="Toggle Simple Moving Average (SMA) Trend Lines"
              id="toggle-sma-btn"
            >
              {showSMA ? "ON" : "OFF"}
            </button>
            {showSMA && (
              <select
                value={smaWindow}
                onChange={(e) => setSmaWindow(Number(e.target.value))}
                className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-[9px] font-mono rounded px-1 py-0.5 text-slate-700 dark:text-slate-300 focus:ring-1 focus:ring-indigo-500 focus:outline-none cursor-pointer"
                title="Select moving average window interval"
                id="select-sma-window"
              >
                <option value={2}>W = 2</option>
                <option value={3}>W = 3</option>
                <option value={4}>W = 4</option>
              </select>
            )}
          </div>

          {/* Metric Selector Tabs for clean filtering in comparison mode */}
          {isComparisonMode && (
            <div className="flex bg-slate-100 dark:bg-slate-950 p-1 rounded-md text-[10px] font-mono border dark:border-slate-800">
              {(["all", "return", "audit", "safety"] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setCompareMetric(m)}
                  className={`px-2 py-1 rounded transition-all capitalize cursor-pointer ${
                    compareMetric === m
                      ? "bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 shadow-sm font-bold"
                      : "text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200"
                  }`}
                >
                  {m === "all" ? "All Metrics" : m === "return" ? "Return %" : `${m} score`}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Improvement Summary Badges */}
        {!isComparisonMode && (
          <div className="flex flex-wrap gap-2 text-[10px] font-mono self-start xl:self-center">
            <div className="bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-100 dark:border-indigo-900/40 text-indigo-700 dark:text-indigo-300 px-2 py-1 rounded flex items-center space-x-1">
              <span>Audit:</span>
              <span className="font-bold">+{auditImprovementA >= 0 ? "" : ""}{auditImprovementA}pts</span>
            </div>
            <div className="bg-purple-50 dark:bg-purple-950/40 border border-purple-100 dark:border-purple-900/40 text-purple-700 dark:text-purple-300 px-2 py-1 rounded flex items-center space-x-1">
              <span>Safety:</span>
              <span className="font-bold">+{safetyImprovementA >= 0 ? "" : ""}{safetyImprovementA}pts</span>
            </div>
            <div className={`px-2 py-1 rounded flex items-center space-x-1 border ${
              returnImprovementA >= 0 
                ? "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-100 dark:border-emerald-900/40 text-emerald-700 dark:text-emerald-300" 
                : "bg-rose-50 dark:bg-rose-950/40 border-rose-100 dark:border-rose-900/40 text-rose-700 dark:text-rose-300"
            }`}>
              <span>Return:</span>
              <span className="font-bold">{returnImprovementA >= 0 ? "+" : ""}{returnImprovementA.toFixed(1)}%</span>
            </div>
          </div>
        )}
      </div>

      {/* Main Chart Canvas */}
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={data}
            margin={{ top: 10, right: 10, left: -10, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--chart-grid)" />
            <XAxis
              dataKey={isComparisonMode ? "step" : "version"}
              stroke="var(--chart-axis)"
              fontSize={10}
              fontFamily="monospace"
              tickLine={false}
              axisLine={false}
              dy={10}
            />
            {/* Left Y-axis: Audit and Safety scores (0 to 100) */}
            <YAxis
              yAxisId="left"
              domain={[0, 100]}
              stroke="var(--chart-axis)"
              fontSize={10}
              fontFamily="monospace"
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `${v}`}
            />
            {/* Right Y-axis: Return percentage (Auto-scaled) */}
            <YAxis
              yAxisId="right"
              orientation="right"
              stroke="#10b981"
              fontSize={10}
              fontFamily="monospace"
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              verticalAlign="top"
              height={36}
              iconType="circle"
              iconSize={6}
              wrapperStyle={{
                fontFamily: "monospace",
                fontSize: "10px",
                color: "#475569"
              }}
            />

            {/* Render dynamic curves based on mode and active selections */}
            {isComparisonMode ? (
              <>
                {/* Primary Strategy Lines */}
                {(compareMetric === "all" || compareMetric === "audit") && (
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey={`${strategy.name} Audit Score`}
                    stroke="#4f46e5"
                    strokeWidth={2}
                    dot={{ stroke: "#4f46e5", strokeWidth: 1.5, r: 3.5, fill: "#ffffff" }}
                    activeDot={{ r: 5 }}
                    name={`${strategy.name} (Audit)`}
                  />
                )}
                {(compareMetric === "all" || compareMetric === "audit") && showSMA && (
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey={`${strategy.name} Audit Score SMA`}
                    stroke="#4f46e5"
                    strokeDasharray="3 3"
                    strokeWidth={1.5}
                    opacity={0.6}
                    dot={false}
                    name={`${strategy.name} Audit SMA (W=${smaWindow})`}
                  />
                )}

                {(compareMetric === "all" || compareMetric === "safety") && (
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey={`${strategy.name} Safety Score`}
                    stroke="#9333ea"
                    strokeWidth={2}
                    dot={{ stroke: "#9333ea", strokeWidth: 1.5, r: 3.5, fill: "#ffffff" }}
                    activeDot={{ r: 5 }}
                    name={`${strategy.name} (Safety)`}
                  />
                )}
                {(compareMetric === "all" || compareMetric === "safety") && showSMA && (
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey={`${strategy.name} Safety Score SMA`}
                    stroke="#9333ea"
                    strokeDasharray="3 3"
                    strokeWidth={1.5}
                    opacity={0.6}
                    dot={false}
                    name={`${strategy.name} Safety SMA (W=${smaWindow})`}
                  />
                )}

                {(compareMetric === "all" || compareMetric === "return") && (
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey={`${strategy.name} Return %`}
                    stroke="#10b981"
                    strokeWidth={2}
                    dot={{ stroke: "#10b981", strokeWidth: 1.5, r: 3.5, fill: "#ffffff" }}
                    activeDot={{ r: 5 }}
                    name={`${strategy.name} (Return %)`}
                  />
                )}
                {(compareMetric === "all" || compareMetric === "return") && showSMA && (
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey={`${strategy.name} Return % SMA`}
                    stroke="#10b981"
                    strokeDasharray="3 3"
                    strokeWidth={1.5}
                    opacity={0.6}
                    dot={false}
                    name={`${strategy.name} Return SMA (W=${smaWindow})`}
                  />
                )}

                {/* Comparison Strategy Lines - Represented by Distinct Dashed Outlines */}
                {(compareMetric === "all" || compareMetric === "audit") && (
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey={`${compareStrategy?.name} Audit Score`}
                    stroke="#06b6d4"
                    strokeDasharray="4 4"
                    strokeWidth={2}
                    dot={{ stroke: "#06b6d4", strokeWidth: 1.5, r: 3.5, fill: "#ffffff" }}
                    activeDot={{ r: 5 }}
                    name={`${compareStrategy?.name} (Audit - Compare)`}
                  />
                )}
                {(compareMetric === "all" || compareMetric === "audit") && showSMA && (
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey={`${compareStrategy?.name} Audit Score SMA`}
                    stroke="#06b6d4"
                    strokeDasharray="1 3"
                    strokeWidth={1.5}
                    opacity={0.6}
                    dot={false}
                    name={`${compareStrategy?.name} Audit SMA (W=${smaWindow})`}
                  />
                )}

                {(compareMetric === "all" || compareMetric === "safety") && (
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey={`${compareStrategy?.name} Safety Score`}
                    stroke="#ec4899"
                    strokeDasharray="4 4"
                    strokeWidth={2}
                    dot={{ stroke: "#ec4899", strokeWidth: 1.5, r: 3.5, fill: "#ffffff" }}
                    activeDot={{ r: 5 }}
                    name={`${compareStrategy?.name} (Safety - Compare)`}
                  />
                )}
                {(compareMetric === "all" || compareMetric === "safety") && showSMA && (
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey={`${compareStrategy?.name} Safety Score SMA`}
                    stroke="#ec4899"
                    strokeDasharray="1 3"
                    strokeWidth={1.5}
                    opacity={0.6}
                    dot={false}
                    name={`${compareStrategy?.name} Safety SMA (W=${smaWindow})`}
                  />
                )}

                {(compareMetric === "all" || compareMetric === "return") && (
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey={`${compareStrategy?.name} Return %`}
                    stroke="#f97316"
                    strokeDasharray="4 4"
                    strokeWidth={2}
                    dot={{ stroke: "#f97316", strokeWidth: 1.5, r: 3.5, fill: "#ffffff" }}
                    activeDot={{ r: 5 }}
                    name={`${compareStrategy?.name} (Return % - Compare)`}
                  />
                )}
                {(compareMetric === "all" || compareMetric === "return") && showSMA && (
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey={`${compareStrategy?.name} Return % SMA`}
                    stroke="#f97316"
                    strokeDasharray="1 3"
                    strokeWidth={1.5}
                    opacity={0.6}
                    dot={false}
                    name={`${compareStrategy?.name} Return SMA (W=${smaWindow})`}
                  />
                )}
              </>
            ) : (
              <>
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="Audit Score"
                  stroke="#4f46e5"
                  strokeWidth={2}
                  dot={{ stroke: "#4f46e5", strokeWidth: 1.5, r: 3, fill: "#ffffff" }}
                  activeDot={{ r: 5 }}
                  name="Audit Score"
                />
                {showSMA && (
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="Audit Score SMA"
                    stroke="#4f46e5"
                    strokeDasharray="3 3"
                    strokeWidth={1.5}
                    opacity={0.6}
                    dot={false}
                    name={`Audit SMA (W=${smaWindow})`}
                  />
                )}

                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="Safety Score"
                  stroke="#9333ea"
                  strokeWidth={2}
                  dot={{ stroke: "#9333ea", strokeWidth: 1.5, r: 3, fill: "#ffffff" }}
                  activeDot={{ r: 5 }}
                  name="Safety Score"
                />
                {showSMA && (
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="Safety Score SMA"
                    stroke="#9333ea"
                    strokeDasharray="3 3"
                    strokeWidth={1.5}
                    opacity={0.6}
                    dot={false}
                    name={`Safety SMA (W=${smaWindow})`}
                  />
                )}

                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="Backtest Return %"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={{ stroke: "#10b981", strokeWidth: 1.5, r: 3, fill: "#ffffff" }}
                  activeDot={{ r: 5 }}
                  name="Backtest Return %"
                />
                {showSMA && (
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="Backtest Return % SMA"
                    stroke="#10b981"
                    strokeDasharray="3 3"
                    strokeWidth={1.5}
                    opacity={0.6}
                    dot={false}
                    name={`Return SMA (W=${smaWindow})`}
                  />
                )}
              </>
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Footer Info Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 border-t border-slate-100 pt-4">
        <div className="p-3 bg-slate-50 rounded-lg flex items-start space-x-2.5">
          <Award className="h-4 w-4 text-indigo-600 mt-0.5 stroke-[1.5]" />
          <div>
            <span className="font-display font-semibold text-slate-800 text-[11px] block">
              {isComparisonMode ? "Relative Auditing" : "Audit Target Met"}
            </span>
            <span className="text-[10px] text-slate-500 font-mono">
              {isComparisonMode 
                ? `${strategy.name.slice(0, 10)}..: ${lastPointA.auditScore} vs ${compareStrategy?.name.slice(0, 10)}..: ${lastPointB.auditScore}`
                : `Current: ${lastPointA.auditScore}/100 (Required: >=85)`}
            </span>
          </div>
        </div>
        <div className="p-3 bg-slate-50 rounded-lg flex items-start space-x-2.5">
          <ShieldAlert className="h-4 w-4 text-purple-600 mt-0.5 stroke-[1.5]" />
          <div>
            <span className="font-display font-semibold text-slate-800 text-[11px] block">
              {isComparisonMode ? "Relative Safety" : "Execution Safeguards"}
            </span>
            <span className="text-[10px] text-slate-500 font-mono">
              {isComparisonMode
                ? `${strategy.name.slice(0, 10)}..: ${lastPointA.safetyScore} vs ${compareStrategy?.name.slice(0, 10)}..: ${lastPointB.safetyScore}`
                : `Current: ${lastPointA.safetyScore}/100 (Required: >=90)`}
            </span>
          </div>
        </div>
        <div className="p-3 bg-slate-50 rounded-lg flex items-start space-x-2.5">
          <TrendingUp className="h-4 w-4 text-emerald-600 mt-0.5 stroke-[1.5]" />
          <div>
            <span className="font-display font-semibold text-slate-800 text-[11px] block">
              {isComparisonMode ? "Relative Performance" : "Historical Efficacy"}
            </span>
            <span className="text-[10px] text-slate-500 font-mono">
              {isComparisonMode
                ? `${strategy.name.slice(0, 10)}..: ${lastPointA.backtestReturnPct.toFixed(1)}% vs ${compareStrategy?.name.slice(0, 10)}..: ${lastPointB.backtestReturnPct.toFixed(1)}%`
                : `Return: ${lastPointA.backtestReturnPct >= 0 ? "+" : ""}${lastPointA.backtestReturnPct.toFixed(1)}% (Inception)`}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
