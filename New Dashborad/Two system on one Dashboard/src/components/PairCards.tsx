/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
import { PairState, TrendBias } from "../types.js";
import { TrendingUp, TrendingDown, ArrowRight, ShieldCheck, Layers, Landmark } from "lucide-react";

interface Props {
  pairs: Record<string, PairState>;
  selectedPair: string;
  onSelectPair: (symbol: string) => void;
}

export const PairCards: React.FC<Props> = ({ pairs, selectedPair, onSelectPair }) => {
  const getTrendBadge = (trend: TrendBias) => {
    switch (trend) {
      case TrendBias.BULLISH:
        return (
          <span className="flex items-center gap-1 text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded-full font-bold">
            <TrendingUp className="w-3 h-3" /> BULLISH
          </span>
        );
      case TrendBias.BEARISH:
        return (
          <span className="flex items-center gap-1 text-[10px] bg-rose-500/10 text-rose-400 border border-rose-500/20 px-2 py-0.5 rounded-full font-bold">
            <TrendingDown className="w-3 h-3" /> BEARISH
          </span>
        );
      default:
        return (
          <span className="text-[10px] bg-zinc-500/10 text-zinc-400 border border-zinc-500/20 px-2 py-0.5 rounded-full font-bold">
            NEUTRAL
          </span>
        );
    }
  };

  const getHtfBiasText = (bias: TrendBias) => {
    switch (bias) {
      case TrendBias.BULLISH:
        return <span className="text-emerald-400 font-bold">BULLISH BIAS</span>;
      case TrendBias.BEARISH:
        return <span className="text-rose-400 font-bold">BEARISH BIAS</span>;
      default:
        return <span className="text-zinc-400 font-bold">NEUTRAL BIAS</span>;
    }
  };

  const activePair = pairs[selectedPair];

  return (
    <div className="flex flex-col gap-4">
      {/* Pair Quick Selection Row */}
      <div className="grid grid-cols-3 gap-3">
        {Object.keys(pairs).map((symbol) => {
          const p = pairs[symbol];
          const isSelected = selectedPair === symbol;
          return (
            <button
              key={symbol}
              onClick={() => onSelectPair(symbol)}
              id={`pair-btn-${symbol}`}
              className={`flex flex-col text-left p-3 rounded-xl border transition-all duration-300 cursor-pointer ${
                isSelected
                  ? "bg-zinc-800/80 border-emerald-500/40 shadow-emerald-500/5 shadow-md scale-[1.02]"
                  : "bg-zinc-900 border-zinc-800/80 hover:border-zinc-700 hover:bg-zinc-800/30"
              }`}
            >
              <div className="flex items-center justify-between w-full mb-1">
                <span className="font-sans font-bold text-sm tracking-tight text-white">{symbol}</span>
                {getTrendBadge(p.trend)}
              </div>
              <div className="flex items-baseline justify-between w-full mt-1.5">
                <span className="font-mono text-base font-bold text-zinc-100">{p.price.toFixed(symbol === "USDJPY" ? 2 : 5)}</span>
                <span className="font-mono text-[10px] text-zinc-500">
                  Spread: <span className={p.spread > 1.5 ? "text-amber-400" : "text-zinc-300"}>{p.spread.toFixed(1)}</span>
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {/* Priority 4: Live Market Structure Card */}
      {activePair && (
        <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-lg flex flex-col gap-3.5">
          <div className="flex items-center justify-between border-b border-zinc-800/60 pb-2.5">
            <div className="flex items-center gap-2">
              <Landmark className="w-4 h-4 text-emerald-400" />
              <h3 className="font-sans font-semibold text-zinc-200 text-sm">Market Structure ({selectedPair})</h3>
            </div>
            <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-widest font-bold">M5/M1 Confluences</span>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1 px-3 py-2 rounded bg-zinc-950/50 border border-zinc-800/40">
              <span className="font-sans text-[11px] text-zinc-500">HTF Trend Bias (H1/H4)</span>
              <div className="font-sans text-[13px] flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-zinc-400" />
                {getHtfBiasText(activePair.htfBias)}
              </div>
            </div>

            <div className="flex flex-col gap-1 px-3 py-2 rounded bg-zinc-950/50 border border-zinc-800/40">
              <span className="font-sans text-[11px] text-zinc-500">Active Trend Mode</span>
              <div className="font-sans text-[13px] font-semibold text-zinc-200 flex items-center gap-1.5">
                <TrendingUp className={`w-3.5 h-3.5 ${activePair.trend === TrendBias.BULLISH ? "text-emerald-400" : "text-rose-400"}`} />
                {activePair.trend}
              </div>
            </div>
          </div>

          <div className="space-y-2 text-xs font-mono">
            <div className="flex justify-between items-center py-1 border-b border-zinc-800/30">
              <span className="text-zinc-500">Swing High Point</span>
              <span className="text-zinc-300 font-bold">{activePair.swingHigh.toFixed(selectedPair === "USDJPY" ? 2 : 5)}</span>
            </div>
            <div className="flex justify-between items-center py-1 border-b border-zinc-800/30">
              <span className="text-zinc-500">Swing Low Point</span>
              <span className="text-zinc-300 font-bold">{activePair.swingLow.toFixed(selectedPair === "USDJPY" ? 2 : 5)}</span>
            </div>
            <div className="flex justify-between items-center py-1 border-b border-zinc-800/30">
              <span className="text-zinc-500">Average True Range (ATR)</span>
              <span className="text-zinc-300 font-bold">{activePair.atr.toFixed(1)} pips</span>
            </div>
            <div className="flex justify-between items-center py-1 border-b border-zinc-800/30">
              <span className="text-zinc-500">Current Spread</span>
              <span className={`font-bold ${activePair.spread > 1.5 ? "text-rose-400" : "text-emerald-400"}`}>{activePair.spread.toFixed(1)} pips</span>
            </div>
            <div className="flex justify-between items-center py-1 border-b border-zinc-800/30">
              <span className="text-zinc-500">Last BOS High Breakout</span>
              <span className="text-emerald-400 flex items-center gap-1">
                {selectedPair === "USDJPY" ? "155.10" : "1.0845"} <ShieldCheck className="w-3.5 h-3.5" />
              </span>
            </div>
            <div className="flex justify-between items-center py-1">
              <span className="text-zinc-500">Last CHoCH Shift Level</span>
              <span className="text-amber-400 flex items-center gap-1">
                {selectedPair === "USDJPY" ? "155.32" : "1.0832"} <ArrowRight className="w-3 h-3" />
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
