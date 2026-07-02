/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
import { RejectionLog, SessionAnalytics } from "../types.js";
import { ShieldAlert, BarChart3, AlertTriangle, CheckSquare, XSquare, Activity, DollarSign, Percent } from "lucide-react";

interface Props {
  rejections: RejectionLog[];
  analytics: SessionAnalytics;
  onResetStats: () => void;
}

export const RejectionsAndAnalytics: React.FC<Props> = ({ rejections, analytics, onResetStats }) => {
  // Compute expectancy: WinRate * AvgProfitRatio - LossRate * 1 (normalized to standard metrics)
  const expectancy = analytics.winRate
    ? parseFloat(((analytics.winRate / 100) * analytics.avgRr - (1 - analytics.winRate / 100)).toFixed(2))
    : 0.0;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Priority 10: Session Analytics Panel */}
      <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-lg flex flex-col justify-between gap-4">
        <div className="flex items-center justify-between border-b border-zinc-800/60 pb-2.5">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-emerald-400" />
            <h3 className="font-sans font-semibold text-zinc-200 text-sm">Session Analytics Performance</h3>
          </div>
          <button
            onClick={onResetStats}
            className="font-mono text-[10px] text-zinc-400 hover:text-white px-2 py-1 rounded bg-zinc-800 border border-zinc-700/60 transition cursor-pointer"
          >
            RESET STATS
          </button>
        </div>

        {/* Analytics Grid */}
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-zinc-950/40 border border-zinc-850 p-3 rounded-xl flex flex-col gap-1.5">
            <div className="flex items-center gap-1 text-[10px] text-zinc-500 font-bold uppercase tracking-wider">
              <CheckSquare className="w-3.5 h-3.5 text-emerald-400" /> Qualified
            </div>
            <span className="font-mono text-lg font-bold text-zinc-100">{analytics.signalsQualified}</span>
          </div>

          <div className="bg-zinc-950/40 border border-zinc-850 p-3 rounded-xl flex flex-col gap-1.5">
            <div className="flex items-center gap-1 text-[10px] text-zinc-500 font-bold uppercase tracking-wider">
              <XSquare className="w-3.5 h-3.5 text-rose-400" /> Rejected
            </div>
            <span className="font-mono text-lg font-bold text-zinc-100">{analytics.signalsRejected}</span>
          </div>

          <div className="bg-zinc-950/40 border border-zinc-850 p-3 rounded-xl flex flex-col gap-1.5">
            <div className="flex items-center gap-1 text-[10px] text-zinc-500 font-bold uppercase tracking-wider">
              <Activity className="w-3.5 h-3.5 text-cyan-400" /> Executed
            </div>
            <span className="font-mono text-lg font-bold text-zinc-100">{analytics.signalsExecuted}</span>
          </div>

          <div className="bg-zinc-950/40 border border-zinc-850 p-3 rounded-xl flex flex-col gap-1.5">
            <div className="flex items-center gap-1 text-[10px] text-zinc-500 font-bold uppercase tracking-wider">
              <Percent className="w-3.5 h-3.5 text-emerald-400" /> Win Rate
            </div>
            <span className="font-mono text-lg font-bold text-emerald-400">{analytics.winRate.toFixed(1)}%</span>
          </div>

          <div className="bg-zinc-950/40 border border-zinc-850 p-3 rounded-xl flex flex-col gap-1.5">
            <div className="flex items-center gap-1 text-[10px] text-zinc-500 font-bold uppercase tracking-wider">
              <DollarSign className="w-3.5 h-3.5 text-amber-400" /> Average RR
            </div>
            <span className="font-mono text-lg font-bold text-zinc-100">{analytics.avgRr.toFixed(2)}</span>
          </div>

          <div className="bg-zinc-950/40 border border-zinc-850 p-3 rounded-xl flex flex-col gap-1.5">
            <div className="flex items-center gap-1 text-[10px] text-zinc-500 font-bold uppercase tracking-wider">
              <Activity className="w-3.5 h-3.5 text-zinc-400" /> Expectancy
            </div>
            <span className={`font-mono text-lg font-bold ${expectancy >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              {expectancy >= 0 ? "+" : ""}{expectancy} R
            </span>
          </div>
        </div>

        {/* Daily Risk Budget Utilized progress bar */}
        <div className="border-t border-zinc-800/60 pt-3.5 flex flex-col gap-2">
          <div className="flex items-center justify-between font-mono text-[11px]">
            <span className="text-zinc-500">Daily Risk Budget Utilized</span>
            <span className={`font-bold ${analytics.dailyRiskUsed > 4.0 ? "text-rose-400 animate-pulse" : "text-emerald-400"}`}>
              {analytics.dailyRiskUsed.toFixed(1)}% / 5.0% Max Cap
            </span>
          </div>
          <div className="w-full bg-zinc-950 rounded-full h-2 overflow-hidden border border-zinc-800/60">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                analytics.dailyRiskUsed > 4.0 ? "bg-rose-500" : "bg-emerald-500"
              }`}
              style={{ width: `${Math.min(100, (analytics.dailyRiskUsed / 5.0) * 100)}%` }}
            ></div>
          </div>
        </div>
      </div>

      {/* Priority 3: Signal Rejection Panel */}
      <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-lg flex flex-col gap-3">
        <div className="flex items-center justify-between border-b border-zinc-800/60 pb-2.5">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-rose-400" />
            <h3 className="font-sans font-semibold text-zinc-200 text-sm">Signal Rejection Engine Logs</h3>
          </div>
          <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-widest font-bold">Rule Breached</span>
        </div>

        {/* Scrollable List of Rejections */}
        <div className="flex-1 overflow-y-auto max-h-[190px] pr-1 flex flex-col gap-2">
          {rejections.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full py-8 text-center text-zinc-600">
              <AlertTriangle className="w-6 h-6 mb-1 text-zinc-800" />
              <span className="font-sans text-xs">No signals rejected in current session. Excellent alignment.</span>
            </div>
          ) : (
            rejections.map((rej) => {
              const timeStr = new Date(rej.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
              return (
                <div
                  key={rej.id}
                  className="flex flex-col gap-1 p-2.5 rounded-xl border border-rose-500/10 bg-rose-500/[0.02] hover:bg-rose-500/[0.04] transition duration-200"
                >
                  <div className="flex items-center justify-between font-mono text-[11px]">
                    <div className="flex items-center gap-1.5 font-sans font-bold text-rose-400">
                      <span>{rej.pair}</span>
                      <span className="text-zinc-600 font-normal">|</span>
                      <span className="bg-rose-500/10 px-1.5 py-0.5 rounded text-[9px] font-bold tracking-tight">
                        {rej.rule}
                      </span>
                    </div>
                    <span className="text-zinc-500 text-[10px]">{timeStr}</span>
                  </div>
                  <p className="font-sans text-xs text-zinc-300 leading-tight">
                    {rej.reason}
                  </p>
                  <span className="font-mono text-[9px] text-rose-400/80 mt-0.5 font-semibold">
                    {rej.metrics}
                  </span>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
