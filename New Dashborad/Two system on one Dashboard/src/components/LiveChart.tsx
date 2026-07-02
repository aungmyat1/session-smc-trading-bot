/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useMemo } from "react";
import { PairState, PendingTrade } from "../types.js";
import { TrendingUp, Award, RefreshCw } from "lucide-react";

interface Props {
  pair: PairState;
  activeTrade: PendingTrade | null;
}

export const LiveChart: React.FC<Props> = ({ pair, activeTrade }) => {
  const candles = pair.candles || [];

  // Determine scaling boundaries
  const limits = useMemo(() => {
    if (candles.length === 0) {
      return { min: 0, max: 100, range: 100 };
    }
    let maxPrice = -Infinity;
    let minPrice = Infinity;

    candles.forEach((c) => {
      if (c.high > maxPrice) maxPrice = c.high;
      if (c.low < minPrice) minPrice = c.low;
    });

    // Add buffers for SMC objects overlays
    pair.activeObjects.forEach((obj) => {
      maxPrice = Math.max(maxPrice, obj.rangeEnd);
      minPrice = Math.min(minPrice, obj.rangeStart);
    });

    if (activeTrade) {
      maxPrice = Math.max(maxPrice, activeTrade.tp, activeTrade.entry);
      minPrice = Math.min(minPrice, activeTrade.sl, activeTrade.entry);
    }

    const priceBuffer = (maxPrice - minPrice) * 0.15 || 0.0010;
    const max = maxPrice + priceBuffer;
    const min = minPrice - priceBuffer;

    return { min, max, range: max - min };
  }, [candles, pair.activeObjects, activeTrade]);

  const width = 640;
  const height = 280;
  const paddingRight = 60;
  const chartWidth = width - paddingRight;

  const getX = (index: number) => {
    if (candles.length <= 1) return 0;
    return (index / (candles.length - 1)) * (chartWidth - 20) + 10;
  };

  const getY = (val: number) => {
    if (limits.range === 0) return height / 2;
    return height - ((val - limits.min) / limits.range) * (height - 40) - 20;
  };

  // Build grid lines
  const gridLines = useMemo(() => {
    const lines = [];
    const count = 5;
    for (let i = 0; i <= count; i++) {
      const price = limits.min + (limits.range * i) / count;
      lines.push(price);
    }
    return lines;
  }, [limits]);

  return (
    <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-lg flex flex-col gap-3">
      {/* Chart Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-emerald-400 animate-pulse" />
          <h3 className="font-sans font-semibold text-zinc-200 text-sm">Live SMC Technical Overlay</h3>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="flex items-center gap-1.5 text-[10px] text-zinc-500">
            <span className="w-2.5 h-2.5 bg-emerald-500/10 border border-emerald-500/40 rounded-sm"></span> OB Zone
          </span>
          <span className="flex items-center gap-1.5 text-[10px] text-zinc-500">
            <span className="w-2.5 h-2.5 bg-cyan-500/10 border border-cyan-500/40 rounded-sm"></span> FVG Imbalance
          </span>
          <span className="flex items-center gap-1.5 text-[10px] text-zinc-500">
            <span className="w-2.5 h-1 bg-amber-400"></span> Sweep Liquidity
          </span>
        </div>
      </div>

      {/* SVG Canvas */}
      <div className="relative w-full overflow-hidden bg-zinc-950/80 border border-zinc-900 rounded-xl" style={{ height: `${height}px` }}>
        {candles.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-2">
            <RefreshCw className="w-6 h-6 text-zinc-700 animate-spin" />
            <span className="font-sans text-xs text-zinc-600">Syncing live market data stream...</span>
          </div>
        ) : (
          <svg className="w-full h-full select-none" viewBox={`0 0 ${width} ${height}`}>
            {/* Draw grid lines and price ticks */}
            {gridLines.map((price, idx) => {
              const y = getY(price);
              return (
                <g key={idx}>
                  <line
                    x1="0"
                    y1={y}
                    x2={chartWidth}
                    y2={y}
                    className="stroke-zinc-900/50"
                    strokeWidth="1"
                    strokeDasharray="4 4"
                  />
                  <text
                    x={chartWidth + 6}
                    y={y + 4}
                    className="fill-zinc-500 font-mono text-[9px] text-right font-semibold"
                  >
                    {price.toFixed(pair.symbol === "USDJPY" ? 2 : 5)}
                  </text>
                </g>
              );
            })}

            {/* Draw Kill Zone Band (Simulate timeline bands, London/NY shade overlay) */}
            <rect
              x={getX(Math.floor(candles.length * 0.4))}
              y="0"
              width={getX(Math.floor(candles.length * 0.95)) - getX(Math.floor(candles.length * 0.4))}
              height={height}
              className="fill-emerald-500/[0.015]"
            />

            {/* Draw Active SMC Objects Overlays */}
            {pair.activeObjects.map((obj, idx) => {
              const topY = getY(Math.max(obj.rangeStart, obj.rangeEnd));
              const botY = getY(Math.min(obj.rangeStart, obj.rangeEnd));
              const boxHeight = botY - topY;
              // Stretch the box from the candle of origin (approximated by age) to the right side
              const ageFactor = Math.max(0, candles.length - 1 - obj.age);
              const startX = getX(ageFactor);
              const boxWidth = chartWidth - startX;

              const isMitigated = obj.status === "MITIGATED";

              if (obj.type === "OB") {
                return (
                  <g key={obj.id || idx}>
                    <rect
                      x={startX}
                      y={topY}
                      width={boxWidth}
                      height={boxHeight}
                      className={isMitigated ? "fill-zinc-500/5 stroke-zinc-500/20" : "fill-emerald-500/10 stroke-emerald-500/30"}
                      strokeWidth="1"
                      strokeDasharray={isMitigated ? "2 2" : "none"}
                    />
                    <text
                      x={startX + 6}
                      y={topY + 12}
                      className={`font-mono text-[8px] font-bold ${isMitigated ? "fill-zinc-600" : "fill-emerald-400"}`}
                    >
                      M1 OB ZONE ({obj.strength}) {isMitigated ? "[MITIGATED]" : "[UNMITIGATED]"}
                    </text>
                  </g>
                );
              } else if (obj.type === "FVG") {
                return (
                  <g key={obj.id || idx}>
                    <rect
                      x={startX}
                      y={topY}
                      width={boxWidth}
                      height={boxHeight}
                      className="fill-cyan-500/5 stroke-cyan-500/25"
                      strokeWidth="1"
                      strokeDasharray="3 3"
                    />
                    <text
                      x={startX + 6}
                      y={topY + 12}
                      className="fill-cyan-400 font-mono text-[8px] font-bold"
                    >
                      FVG IMBALANCE
                    </text>
                  </g>
                );
              }
              return null;
            })}

            {/* Sweep Liquidity dotted line */}
            {pair.symbol === "EURUSD" && (
              <g>
                <line
                  x1="0"
                  y1={getY(1.0815)}
                  x2={chartWidth}
                  y2={getY(1.0815)}
                  className="stroke-amber-400/50"
                  strokeWidth="1"
                  strokeDasharray="2 3"
                />
                <text
                  x="10"
                  y={getY(1.0815) - 4}
                  className="fill-amber-400/80 font-mono text-[8px] font-bold"
                >
                   swept liquidity pool (1.0815) 
                </text>
              </g>
            )}

            {/* Technical BOS & CHoCH Break Lines */}
            <line
              x1="0"
              y1={getY(pair.symbol === "USDJPY" ? 155.32 : 1.0832)}
              x2={chartWidth}
              y2={getY(pair.symbol === "USDJPY" ? 155.32 : 1.0832)}
              className="stroke-amber-500/30"
              strokeWidth="1"
              strokeDasharray="2 4"
            />
            <text
              x="10"
              y={getY(pair.symbol === "USDJPY" ? 155.32 : 1.0832) - 4}
              className="fill-amber-500/70 font-mono text-[8px] font-semibold"
            >
              CHoCH LEVEL
            </text>

            <line
              x1="0"
              y1={getY(pair.symbol === "USDJPY" ? 155.10 : 1.0845)}
              x2={chartWidth}
              y2={getY(pair.symbol === "USDJPY" ? 155.10 : 1.0845)}
              className="stroke-emerald-500/30"
              strokeWidth="1"
              strokeDasharray="2 4"
            />
            <text
              x={chartWidth - 80}
              y={getY(pair.symbol === "USDJPY" ? 155.10 : 1.0845) - 4}
              className="fill-emerald-500/70 font-mono text-[8px] font-semibold"
            >
              BOS BREAKOUT
            </text>

            {/* Draw Candlesticks */}
            {candles.map((c, idx) => {
              const x = getX(idx);
              const oY = getY(c.open);
              const cY = getY(c.close);
              const hY = getY(c.high);
              const lY = getY(c.low);

              const isBullish = c.close >= c.open;
              const fill = isBullish ? "fill-emerald-500/85" : "fill-rose-500/85";
              const stroke = isBullish ? "stroke-emerald-400" : "stroke-rose-400";
              const wickStroke = isBullish ? "stroke-emerald-500/60" : "stroke-rose-500/60";

              const candleWidth = Math.max(2, (chartWidth / candles.length) * 0.6);

              return (
                <g key={idx}>
                  {/* Wick */}
                  <line x1={x} y1={hY} x2={x} y2={lY} className={wickStroke} strokeWidth="1.2" />
                  {/* Body */}
                  <rect
                    x={x - candleWidth / 2}
                    y={Math.min(oY, cY)}
                    width={candleWidth}
                    height={Math.max(1.5, Math.abs(cY - oY))}
                    className={`${fill} ${stroke}`}
                    strokeWidth="0.8"
                  />
                </g>
              );
            })}

            {/* Draw active position lines if in active trade */}
            {activeTrade && (
              <g>
                {/* Take Profit Line */}
                <line
                  x1="0"
                  y1={getY(activeTrade.tp)}
                  x2={chartWidth}
                  y2={getY(activeTrade.tp)}
                  className="stroke-cyan-400/80"
                  strokeWidth="1.2"
                  strokeDasharray="4 2"
                />
                <rect
                  x={chartWidth - 55}
                  y={getY(activeTrade.tp) - 9}
                  width="50"
                  height="16"
                  rx="3"
                  className="fill-cyan-950 stroke-cyan-500/40"
                  strokeWidth="0.8"
                />
                <text
                  x={chartWidth - 30}
                  y={getY(activeTrade.tp) + 2}
                  className="fill-cyan-400 font-mono text-[8px] font-bold text-center"
                  textAnchor="middle"
                >
                  TP: {activeTrade.tp.toFixed(pair.symbol === "USDJPY" ? 2 : 5)}
                </text>

                {/* Entry Line */}
                <line
                  x1="0"
                  y1={getY(activeTrade.entry)}
                  x2={chartWidth}
                  y2={getY(activeTrade.entry)}
                  className="stroke-emerald-400"
                  strokeWidth="1.2"
                />
                <rect
                  x="10"
                  y={getY(activeTrade.entry) - 9}
                  width="72"
                  height="16"
                  rx="3"
                  className="fill-emerald-950 stroke-emerald-500/40"
                  strokeWidth="0.8"
                />
                <text
                  x="46"
                  y={getY(activeTrade.entry) + 2}
                  className="fill-emerald-400 font-mono text-[8px] font-bold text-center"
                  textAnchor="middle"
                >
                  ENTRY: {activeTrade.entry.toFixed(pair.symbol === "USDJPY" ? 2 : 5)}
                </text>

                {/* Stop Loss Line */}
                <line
                  x1="0"
                  y1={getY(activeTrade.sl)}
                  x2={chartWidth}
                  y2={getY(activeTrade.sl)}
                  className="stroke-rose-400/80"
                  strokeWidth="1.2"
                  strokeDasharray="4 2"
                />
                <rect
                  x={chartWidth - 55}
                  y={getY(activeTrade.sl) - 9}
                  width="50"
                  height="16"
                  rx="3"
                  className="fill-rose-950 stroke-rose-500/40"
                  strokeWidth="0.8"
                />
                <text
                  x={chartWidth - 30}
                  y={getY(activeTrade.sl) + 2}
                  className="fill-rose-400 font-mono text-[8px] font-bold text-center"
                  textAnchor="middle"
                >
                  SL: {activeTrade.sl.toFixed(pair.symbol === "USDJPY" ? 2 : 5)}
                </text>
              </g>
            )}

            {/* Current Price Line */}
            <line
              x1="0"
              y1={getY(pair.price)}
              x2={chartWidth}
              y2={getY(pair.price)}
              className="stroke-white/20"
              strokeWidth="0.8"
              strokeDasharray="1 3"
            />
            <circle cx={chartWidth} cy={getY(pair.price)} r="3" className="fill-white" />
          </svg>
        )}
      </div>

      {/* Mini Active Object Info table */}
      <div className="bg-zinc-950/40 rounded-xl p-3 border border-zinc-800/40">
        <h4 className="font-sans font-semibold text-zinc-400 text-xs mb-2">Active SMC Objects Stack</h4>
        {pair.activeObjects.length === 0 ? (
          <span className="text-[11px] text-zinc-600 font-mono">No active unmitigated structures detected. Accumulating structure...</span>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-[11px] font-mono">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-500">
                  <th className="pb-1 font-bold">Type</th>
                  <th className="pb-1 font-bold">Range Bound</th>
                  <th className="pb-1 font-bold">Volume Strength</th>
                  <th className="pb-1 font-bold">Mitigation</th>
                  <th className="pb-1 font-bold text-right">Age (Candles)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-850 text-zinc-300">
                {pair.activeObjects.map((obj, i) => (
                  <tr key={i} className="hover:bg-zinc-900/30 transition">
                    <td className="py-1.5 font-bold">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[9px] ${
                          obj.type === "OB" ? "bg-emerald-500/10 text-emerald-400" : "bg-cyan-500/10 text-cyan-400"
                        }`}
                      >
                        {obj.type}
                      </span>
                    </td>
                    <td className="py-1.5">
                      {obj.rangeStart.toFixed(pair.symbol === "USDJPY" ? 2 : 5)} - {obj.rangeEnd.toFixed(pair.symbol === "USDJPY" ? 2 : 5)}
                    </td>
                    <td className="py-1.5 text-zinc-400">{obj.strength}</td>
                    <td className="py-1.5">
                      <span className={obj.status === "UNMITIGATED" ? "text-emerald-400 font-bold" : "text-zinc-500"}>
                        {obj.status}
                      </span>
                    </td>
                    <td className="py-1.5 text-right text-zinc-500">{obj.age} bars</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
