/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
import { PendingTrade, PairState } from "../types.js";
import { Landmark, TrendingUp, ShieldAlert, Sparkles, AlertTriangle } from "lucide-react";

interface Props {
  activeTrade: PendingTrade | null;
  selectedPairState: PairState | null;
  onForceClose: () => void;
  isPaused: boolean;
}

export const ActiveTradeCard: React.FC<Props> = ({ activeTrade, selectedPairState, onForceClose, isPaused }) => {
  if (isPaused) {
    return (
      <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-5 shadow-lg flex flex-col items-center justify-center text-center gap-3 h-full min-h-[220px]">
        <div className="w-12 h-12 rounded-full bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-500 animate-pulse">
          <AlertTriangle className="w-6 h-6" />
        </div>
        <div className="flex flex-col gap-1">
          <h3 className="font-sans font-bold text-white text-sm uppercase tracking-wide">Trading Paused</h3>
          <p className="font-sans text-xs text-zinc-500 max-w-[240px] leading-relaxed">
            Trading engine execution is manually paused by operator override. Pipeline transitions are blocked.
          </p>
        </div>
      </div>
    );
  }

  if (!activeTrade || !selectedPairState) {
    return (
      <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-5 shadow-lg flex flex-col items-center justify-center text-center gap-3 h-full min-h-[220px]">
        <div className="w-10 h-10 rounded-full bg-zinc-950 border border-zinc-800 flex items-center justify-center text-zinc-600">
          <Landmark className="w-5 h-5" />
        </div>
        <div className="flex flex-col gap-1">
          <h3 className="font-sans font-bold text-zinc-400 text-sm">NO ACTIVE SIGNALS</h3>
          <p className="font-sans text-xs text-zinc-600 max-w-[220px] leading-tight">
            Scanning institutional liquidity grids for unmitigated order blocks & gaps...
          </p>
        </div>
      </div>
    );
  }

  // Determine if trade is pending or fully active based on price action proximity
  const isBuy = activeTrade.type === "BUY";
  const currentPrice = selectedPairState.price;

  // Let's approximate whether trade is executed or waiting:
  const isExecuted = selectedPairState.candles[selectedPairState.candles.length - 1].close !== activeTrade.entry;

  // Compute dynamic PnL
  const pipsDiff = isBuy ? (currentPrice - activeTrade.entry) : (activeTrade.entry - currentPrice);
  const pipsFactor = selectedPairState.symbol === "USDJPY" ? 100 : 10000;
  const runningPnL = pipsDiff * activeTrade.lotSize * pipsFactor * 10; // rough conversion index
  const isProfit = runningPnL >= 0;

  // Position between SL and TP
  const totalRange = Math.abs(activeTrade.tp - activeTrade.sl);
  const currentOffset = Math.abs(currentPrice - activeTrade.sl);
  const progressPercent = Math.max(0, Math.min(100, (currentOffset / totalRange) * 100));

  return (
    <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-lg flex flex-col justify-between gap-4 h-full min-h-[220px]">
      {/* Header Badge */}
      <div className="flex items-center justify-between border-b border-zinc-800/60 pb-2.5">
        <div className="flex items-center gap-2">
          <span className={`relative flex h-2 w-2`}>
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${isExecuted ? "bg-rose-500" : "bg-emerald-400"}`}></span>
            <span className={`relative inline-flex rounded-full h-2 w-2 ${isExecuted ? "bg-rose-500" : "bg-emerald-500"}`}></span>
          </span>
          <h3 className="font-sans font-bold text-white text-xs uppercase tracking-wide">
            {isExecuted ? "LIVE ACTIVE POSITION" : "PRE-EXECUTION CONFLUENCE"}
          </h3>
        </div>
        <span
          className={`font-mono text-[10px] px-2 py-0.5 rounded-full font-bold ${
            isBuy ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"
          }`}
        >
          {activeTrade.type} Order
        </span>
      </div>

      {/* Primary Details Block */}
      <div className="flex flex-col gap-3">
        <div className="flex items-baseline justify-between">
          <span className="font-sans font-extrabold text-white text-xl flex items-center gap-1.5">
            {selectedPairState.symbol}
            <span className="font-mono text-xs font-normal text-zinc-500">@{activeTrade.lotSize} Lots</span>
          </span>

          {isExecuted ? (
            <span className={`font-mono text-lg font-bold ${isProfit ? "text-emerald-400" : "text-rose-400"}`}>
              {isProfit ? "+" : ""}${runningPnL.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          ) : (
            <span className="font-sans text-xs text-zinc-500 flex items-center gap-1">
              <Sparkles className="w-3.5 h-3.5 text-emerald-400" /> Pending...
            </span>
          )}
        </div>

        {/* Trade Confluence Summary */}
        <p className="font-sans text-[11px] text-zinc-400 leading-normal border-l border-emerald-500/40 pl-2">
          {activeTrade.reason}
        </p>

        {/* Parameters Grid */}
        <div className="grid grid-cols-4 gap-2 text-center font-mono text-[10px] mt-1.5">
          <div className="bg-zinc-950/40 border border-zinc-850 p-1.5 rounded-lg flex flex-col">
            <span className="text-zinc-500">Entry</span>
            <span className="text-zinc-200 font-bold">{activeTrade.entry.toFixed(selectedPairState.symbol === "USDJPY" ? 2 : 5)}</span>
          </div>

          <div className="bg-zinc-950/40 border border-zinc-850 p-1.5 rounded-lg flex flex-col">
            <span className="text-zinc-500">Stop Loss</span>
            <span className="text-rose-400 font-bold">{activeTrade.sl.toFixed(selectedPairState.symbol === "USDJPY" ? 2 : 5)}</span>
          </div>

          <div className="bg-zinc-950/40 border border-zinc-850 p-1.5 rounded-lg flex flex-col">
            <span className="text-zinc-500">Target TP</span>
            <span className="text-cyan-400 font-bold">{activeTrade.tp.toFixed(selectedPairState.symbol === "USDJPY" ? 2 : 5)}</span>
          </div>

          <div className="bg-zinc-950/40 border border-zinc-850 p-1.5 rounded-lg flex flex-col">
            <span className="text-zinc-500">Risk/Reward</span>
            <span className="text-emerald-400 font-bold">1:{activeTrade.rr}</span>
          </div>
        </div>

        {/* Interactive Progress Slider between SL and TP */}
        {isExecuted && (
          <div className="flex flex-col gap-1.5 mt-1.5">
            <div className="flex items-center justify-between text-[8px] font-mono uppercase tracking-widest text-zinc-500 font-bold">
              <span>STOP LOSS ({activeTrade.sl.toFixed(selectedPairState.symbol === "USDJPY" ? 2 : 5)})</span>
              <span>TAKE PROFIT ({activeTrade.tp.toFixed(selectedPairState.symbol === "USDJPY" ? 2 : 5)})</span>
            </div>
            <div className="w-full bg-zinc-950 rounded-full h-1.5 overflow-hidden border border-zinc-850">
              <div
                className="h-full bg-gradient-to-r from-rose-500 via-zinc-400 to-cyan-500 transition-all duration-300"
                style={{ width: `${progressPercent}%` }}
              ></div>
            </div>
          </div>
        )}
      </div>

      {/* Action triggers */}
      <div className="flex items-center justify-between border-t border-zinc-800/60 pt-3">
        <div className="flex gap-4 font-mono text-[10px] text-zinc-500 font-semibold">
          <div>
            Risk: <span className="text-rose-400 font-bold">-{activeTrade.riskPercent}% (${activeTrade.riskAmount})</span>
          </div>
          <div>
            Exp Profit: <span className="text-emerald-400 font-bold">+${activeTrade.expectedProfit}</span>
          </div>
        </div>

        {isExecuted && (
          <button
            onClick={onForceClose}
            className="flex items-center gap-1.5 text-[10px] font-sans font-bold text-rose-400 hover:text-white bg-rose-500/10 hover:bg-rose-500/80 border border-rose-500/20 px-3 py-1.5 rounded-xl transition cursor-pointer"
          >
            <ShieldAlert className="w-3.5 h-3.5" /> FORCE EXIT
          </button>
        )}
      </div>
    </div>
  );
};
