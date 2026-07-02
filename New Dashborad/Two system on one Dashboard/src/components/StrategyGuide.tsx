/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from "react";
import { BookOpen, ChevronDown, ChevronUp, Clock, HelpCircle } from "lucide-react";

export const StrategyGuide: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);

  // Compute live UTC hour to place needle
  const utcHour = new Date().getUTCHours();
  const utcMinutes = new Date().getUTCMinutes();
  const utcDecimalTime = utcHour + utcMinutes / 60;

  // London: 07-11 UTC. New York: 12-16 UTC.
  const isInsideKillZone =
    (utcDecimalTime >= 7 && utcDecimalTime <= 11) ||
    (utcDecimalTime >= 12 && utcDecimalTime <= 16);

  // Map 24 hours to 100% width
  const needlePercent = (utcDecimalTime / 24) * 100;

  return (
    <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-lg flex flex-col gap-3">
      {/* Clickable Header */}
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        className="w-full flex items-center justify-between font-sans cursor-pointer text-left focus:outline-none"
      >
        <div className="flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-emerald-400" />
          <h3 className="font-semibold text-zinc-200 text-sm">Automated Strategy Blueprint & Educational Guide</h3>
        </div>
        <div className="flex items-center gap-2 text-xs text-zinc-400 font-semibold">
          <span>{isOpen ? "COLLAPSE GUIDE" : "EXPAND GUIDE"}</span>
          {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </div>
      </button>

      {/* Guide Content */}
      {isOpen && (
        <div className="mt-2.5 flex flex-col gap-6 pt-3.5 border-t border-zinc-800/60 transition-all duration-300">
          
          {/* Dynamic 24-Hour Kill Zone Timeline */}
          <div className="flex flex-col gap-3.5 bg-zinc-950/40 border border-zinc-850 p-4 rounded-xl">
            <h4 className="font-sans font-bold text-zinc-300 text-xs flex items-center gap-1.5 uppercase tracking-wider">
              <Clock className="w-4 h-4 text-emerald-400" /> Active Session Kill Zones Timeline (UTC)
            </h4>

            {/* Timeline Graphic */}
            <div className="relative w-full h-8 bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden flex">
              {/* Hour grid ticks */}
              {Array.from({ length: 24 }).map((_, i) => (
                <div
                  key={i}
                  className="absolute h-full border-r border-zinc-850/40 text-[7px] font-mono text-zinc-600 flex flex-col justify-end pb-1"
                  style={{ left: `${(i / 24) * 100}%` }}
                >
                  <span className="pl-0.5">{i.toString().padStart(2, "0")}</span>
                </div>
              ))}

              {/* London Shaded Area (07-11 UTC) */}
              <div
                className="absolute h-full bg-emerald-500/10 border-l border-r border-emerald-500/30 flex items-center justify-center"
                style={{ left: `${(7 / 24) * 100}%`, width: `${(4 / 24) * 100}%` }}
              >
                <span className="text-[9px] font-sans font-extrabold text-emerald-400 opacity-80 uppercase tracking-widest hidden sm:inline">
                  London (07-11)
                </span>
              </div>

              {/* New York Shaded Area (12-16 UTC) */}
              <div
                className="absolute h-full bg-cyan-500/10 border-l border-r border-cyan-500/30 flex items-center justify-center"
                style={{ left: `${(12 / 24) * 100}%`, width: `${(4 / 24) * 100}%` }}
              >
                <span className="text-[9px] font-sans font-extrabold text-cyan-400 opacity-80 uppercase tracking-widest hidden sm:inline">
                  New York (12-16)
                </span>
              </div>

              {/* Live Time needle indicator */}
              <div
                className="absolute top-0 bottom-0 w-0.5 bg-white shadow-[0_0_8px_rgba(255,255,255,0.8)] z-10 transition-all duration-300"
                style={{ left: `${needlePercent}%` }}
              >
                <div className="absolute top-0 left-1/2 transform -translate-x-1/2 -translate-y-1.5 w-2 h-2 rounded-full bg-white"></div>
              </div>
            </div>

            <div className="flex items-center justify-between text-xs font-sans text-zinc-400 font-medium">
              <span>
                Current UTC Time: <span className="font-mono text-white font-bold">{utcHour.toString().padStart(2, "0")}:{utcMinutes.toString().padStart(2, "0")} UTC</span>
              </span>
              <div className="flex items-center gap-1.5">
                <span className="text-zinc-500">Status:</span>
                <span
                  className={`font-mono text-[10px] px-2 py-0.5 rounded border ${
                    isInsideKillZone
                      ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                      : "bg-zinc-800 border-zinc-700 text-zinc-500"
                  }`}
                >
                  {isInsideKillZone ? "INSIDE KILL ZONE (ACTIVE)" : "OUTSIDE KILL ZONE (PAUSED)"}
                </span>
              </div>
            </div>
          </div>

          {/* Core Rules and Parameters Splits */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 text-sm">
            {/* Left Column: Entry Rules */}
            <div className="flex flex-col gap-3.5 bg-zinc-950/20 border border-zinc-850/50 p-4 rounded-xl">
              <h4 className="font-sans font-bold text-white text-xs border-b border-zinc-800 pb-2 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400"></span> ENTRY VALIDATION CRITERIA
              </h4>
              <ol className="space-y-3.5 text-xs font-sans text-zinc-300">
                <li className="flex flex-col gap-1">
                  <div className="flex items-center gap-1.5 font-bold text-zinc-200">
                    <span className="font-mono text-emerald-400 font-bold bg-emerald-500/10 border border-emerald-500/20 w-5 h-5 rounded-full flex items-center justify-center text-[10px]">1</span>
                    Break of Structure (BOS)
                  </div>
                  <p className="text-zinc-400 pl-6.5 leading-relaxed">
                    A trend breakout closed candles high or low. Calculated via code utilizing:{" "}
                    <code className="bg-zinc-900 border border-zinc-800 px-1.5 py-0.5 rounded font-mono text-[10px] text-zinc-300">
                      smc.bos_choch(close_break=True)
                    </code>
                  </p>
                </li>

                <li className="flex flex-col gap-1">
                  <div className="flex items-center gap-1.5 font-bold text-zinc-200">
                    <span className="font-mono text-emerald-400 font-bold bg-emerald-500/10 border border-emerald-500/20 w-5 h-5 rounded-full flex items-center justify-center text-[10px]">2</span>
                    Institutional Order Block (OB)
                  </div>
                  <p className="text-zinc-400 pl-6.5 leading-relaxed">
                    The last opposing body candle prior to the Break of Structure. We target only untouched, pristine blocks where{" "}
                    <code className="bg-zinc-900 border border-zinc-800 px-1.5 py-0.5 rounded font-mono text-[10px] text-zinc-300">
                      MitigatedIndex == 0
                    </code>
                    .
                  </p>
                </li>

                <li className="flex flex-col gap-1">
                  <div className="flex items-center gap-1.5 font-bold text-zinc-200">
                    <span className="font-mono text-emerald-400 font-bold bg-emerald-500/10 border border-emerald-500/20 w-5 h-5 rounded-full flex items-center justify-center text-[10px]">3</span>
                    Fair Value Gap (FVG) Imbalance
                  </div>
                  <p className="text-zinc-400 pl-6.5 leading-relaxed">
                    An inefficient 3-candle imbalance range that overlaps within a threshold range of 1 ATR from the Order Block boundaries.
                  </p>
                </li>

                <li className="flex flex-col gap-1">
                  <div className="flex items-center gap-1.5 font-bold text-zinc-200">
                    <span className="font-mono text-emerald-400 font-bold bg-emerald-500/10 border border-emerald-500/20 w-5 h-5 rounded-full flex items-center justify-center text-[10px]">4</span>
                    Confluence Zone Pullback
                  </div>
                  <p className="text-zinc-400 pl-6.5 leading-relaxed">
                    Trigger executes ONLY when price retests inside the Order Block buffer zone (calculated as OB boundary range ± 5 pip trigger buffer).
                  </p>
                </li>

                <li className="flex flex-col gap-1">
                  <div className="flex items-center gap-1.5 font-bold text-zinc-200">
                    <span className="font-mono text-emerald-400 font-bold bg-emerald-500/10 border border-emerald-500/20 w-5 h-5 rounded-full flex items-center justify-center text-[10px]">5</span>
                    Kill Zone Active Sessions
                  </div>
                  <p className="text-zinc-400 pl-6.5 leading-relaxed">
                    Active execution restricted strictly to peak volume sessions: London (07:00 - 11:00 UTC) and New York (12:00 - 16:00 UTC).
                  </p>
                </li>
              </ol>
            </div>

            {/* Right Column: Live Parameters & Exit Rules */}
            <div className="flex flex-col gap-4">
              {/* Parameters Card */}
              <div className="bg-zinc-950/20 border border-zinc-850/50 p-4 rounded-xl flex flex-col gap-3">
                <h4 className="font-sans font-bold text-white text-xs border-b border-zinc-800 pb-2 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-cyan-400"></span> BOT LIVE PARAMETERS
                </h4>
                <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                  <div className="flex justify-between py-1 border-b border-zinc-800/40">
                    <span className="text-zinc-500">Risk Size:</span>
                    <span className="text-emerald-400 font-bold">1.0% / trade</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-zinc-800/40">
                    <span className="text-zinc-500">Target R:R:</span>
                    <span className="text-cyan-400 font-bold">1:3.0 Min</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-zinc-800/40">
                    <span className="text-zinc-500">Swing Window:</span>
                    <span className="text-zinc-300 font-bold">15 Candles</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-zinc-800/40">
                    <span className="text-zinc-500">ATR Window:</span>
                    <span className="text-zinc-300 font-bold">14 Periods</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-zinc-800/40">
                    <span className="text-zinc-500">Spread Limit:</span>
                    <span className="text-rose-400 font-bold">1.5 pips Max</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-zinc-800/40">
                    <span className="text-zinc-500">Daily Trade Cap:</span>
                    <span className="text-zinc-300 font-bold">3 Positions</span>
                  </div>
                </div>
              </div>

              {/* Exit Rules Card */}
              <div className="bg-zinc-950/20 border border-zinc-850/50 p-4 rounded-xl flex flex-col gap-3">
                <h4 className="font-sans font-bold text-white text-xs border-b border-zinc-800 pb-2 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-rose-400"></span> EXIT & RISK SAFEGUARDS
                </h4>
                <div className="space-y-2 text-xs text-zinc-400 leading-relaxed font-sans">
                  <p>
                    <strong className="text-zinc-300">Stop Loss (SL):</strong> Automatically anchored at the low of the selected bullish Order Block (or the high of the bearish block) to guarantee strict capital reservation.
                  </p>
                  <p>
                    <strong className="text-zinc-300">Take Profit (TP):</strong> Set at key structural swing highs, targeting a minimum mathematical outcome of 3.0x risk limits.
                  </p>
                  <p>
                    <strong className="text-zinc-300">Lot Sizing Calculator:</strong> Adjusted dynamically based on ATR distance to SL and active account balance: <br />
                    <code className="bg-zinc-900 border border-zinc-800 px-1 py-0.5 rounded font-mono text-[10px] text-emerald-400">
                      Lots = (AccountBalance * Risk%) / (SLDistanceInPips * PipValue)
                    </code>
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Example Trade SVG Section */}
          <div className="flex flex-col gap-4 bg-zinc-950/40 border border-zinc-850 p-4 rounded-xl">
            <h4 className="font-sans font-bold text-zinc-300 text-xs uppercase tracking-wider">
              Bullish Smart Money Setup Candle Blueprint (17 Candles Example)
            </h4>

            {/* High-fidelity SVG of 17 Candles */}
            <div className="w-full overflow-x-auto">
              <svg className="w-full min-w-[600px] h-48 select-none" viewBox="0 0 700 180">
                {/* Background lines */}
                <line x1="0" y1="30" x2="700" y2="30" className="stroke-zinc-900" strokeWidth="0.8" />
                <line x1="0" y1="90" x2="700" y2="90" className="stroke-zinc-900" strokeWidth="0.8" />
                <line x1="0" y1="140" x2="700" y2="140" className="stroke-zinc-900" strokeWidth="0.8" />

                {/* Candles data list */}
                {/* X positions start at 30, spaced by 35 */}
                {[
                  { x: 40, o: 60, c: 80, h: 50, l: 90, b: false }, // Candle 1: down
                  { x: 75, o: 80, c: 95, h: 70, l: 110, b: false }, // Candle 2: down
                  { x: 110, o: 95, c: 115, h: 90, l: 125, b: false }, // Candle 3: down
                  { x: 145, o: 115, c: 130, h: 105, l: 140, b: false }, // Candle 4: down (Order Block Candle!)
                  { x: 180, o: 130, c: 75, h: 65, l: 135, b: true }, // Candle 5: HUGE UP (BOS and CHoCH!)
                  { x: 215, o: 75, c: 55, h: 45, l: 80, b: true }, // Candle 6: up
                  { x: 250, o: 55, c: 40, h: 30, l: 60, b: true }, // Candle 7: up (creates Swing High)
                  { x: 285, o: 40, c: 55, h: 35, l: 60, b: false }, // Candle 8: down pullback starts
                  { x: 320, o: 55, c: 68, h: 50, l: 75, b: false }, // Candle 9: down
                  { x: 355, o: 68, c: 82, h: 60, l: 90, b: false }, // Candle 10: down
                  { x: 390, o: 82, c: 110, h: 75, l: 115, b: false }, // Candle 11: down
                  { x: 425, o: 110, c: 128, h: 100, l: 132, b: false }, // Candle 12: taps OB inside FVG buffer! ENTRY!
                  { x: 460, o: 128, c: 105, h: 95, l: 130, b: true }, // Candle 13: rapid reversal up!
                  { x: 495, o: 105, c: 80, h: 70, l: 110, b: true }, // Candle 14: up
                  { x: 530, o: 80, c: 62, h: 55, l: 85, b: true }, // Candle 15: up
                  { x: 565, o: 62, c: 45, h: 35, l: 70, b: true }, // Candle 16: up
                  { x: 600, o: 45, c: 30, h: 20, l: 50, b: true }, // Candle 17: hits target TP!
                ].map((c, i) => {
                  const fill = c.b ? "fill-emerald-500/80 stroke-emerald-400" : "fill-rose-500/80 stroke-rose-400";
                  const isOb = i === 3;
                  return (
                    <g key={i}>
                      {/* Wick */}
                      <line x1={c.x} y1={c.h} x2={c.x} y2={c.l} className={c.b ? "stroke-emerald-500/40" : "stroke-rose-500/40"} strokeWidth="1" />
                      {/* Body */}
                      <rect
                        x={c.x - 7}
                        y={Math.min(c.o, c.c)}
                        width="14"
                        height={Math.max(2, Math.abs(c.o - c.c))}
                        className={`${fill} ${isOb ? "stroke-zinc-100 stroke-1.5 shadow" : ""}`}
                        strokeWidth="0.7"
                      />
                    </g>
                  );
                })}

                {/* Shaded OB Zone (at Y: 115 to 130, X: 145 to 650) */}
                <rect x="138" y="115" width="520" height="15" className="fill-emerald-500/10 stroke-emerald-500/30" strokeWidth="0.8" strokeDasharray="3 3" />
                <text x="650" y="126" className="fill-emerald-400 font-mono text-[7px] font-bold" textAnchor="end">ORDER BLOCK (OB)</text>

                {/* Shaded FVG Zone (at Y: 95 to 115, X: 180 to 450) */}
                <rect x="173" y="80" width="300" height="35" className="fill-cyan-500/5 stroke-cyan-500/20" strokeWidth="0.8" strokeDasharray="2 3" />
                <text x="465" y="92" className="fill-cyan-400 font-mono text-[7px] font-bold" textAnchor="end">FVG IMBALANCE</text>

                {/* BOS line */}
                <line x1="173" y1="75" x2="300" y2="75" className="stroke-emerald-400/50" strokeWidth="1" strokeDasharray="2 2" />
                <text x="230" y="70" className="fill-emerald-400 font-mono text-[7px] font-bold">BOS LEVEL</text>

                {/* Trades Line indicators */}
                {/* SL Line */}
                <line x1="410" y1="140" x2="480" y2="140" className="stroke-rose-500" strokeWidth="1.2" strokeDasharray="3 1" />
                <text x="485" y="143" className="fill-rose-400 font-mono text-[7px] font-bold">STOP LOSS</text>

                {/* Entry Dot */}
                <circle cx="425" cy="120" r="4" className="fill-white stroke-emerald-400" strokeWidth="1.5" />
                <text x="425" y="112" className="fill-white font-mono text-[7px] font-bold text-center" textAnchor="middle">ENTRY</text>

                {/* TP Line */}
                <line x1="425" y1="30" x2="650" y2="30" className="stroke-cyan-500" strokeWidth="1.2" strokeDasharray="3 1" />
                <text x="655" y="33" className="fill-cyan-400 font-mono text-[7px] font-bold">TAKE PROFIT</text>

                {/* Stage markers under the chart */}
                <text x="90" y="165" className="fill-zinc-500 font-sans text-[8px] font-bold text-center" textAnchor="middle">Downtrend</text>
                <text x="180" y="165" className="fill-emerald-400 font-sans text-[8px] font-bold text-center" textAnchor="middle">BOS</text>
                <text x="350" y="165" className="fill-zinc-400 font-sans text-[8px] font-bold text-center" textAnchor="middle">Pullback</text>
                <text x="425" y="165" className="fill-emerald-400 font-sans text-[8px] font-bold text-center" textAnchor="middle">OB / FVG Entry</text>
                <text x="600" y="165" className="fill-cyan-400 font-sans text-[8px] font-bold text-center" textAnchor="middle">Target TP Hit</text>
              </svg>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
