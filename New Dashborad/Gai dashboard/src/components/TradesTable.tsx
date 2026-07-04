/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from "react";
import { ExecutedTrade } from "../types.js";
import { ListCollapse, ChevronDown, ChevronUp, CheckCircle, Info, Landmark, HelpCircle } from "lucide-react";

interface Props {
  history: ExecutedTrade[];
}

export const TradesTable: React.FC<Props> = ({ history }) => {
  const [expandedTradeId, setExpandedTradeId] = useState<string | null>(null);

  const toggleExpand = (id: string) => {
    setExpandedTradeId((prev) => (prev === id ? null : id));
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-lg flex flex-col gap-3">
      <div className="flex items-center justify-between border-b border-zinc-800/60 pb-2.5">
        <div className="flex items-center gap-2">
          <ListCollapse className="w-4 h-4 text-emerald-400" />
          <h3 className="font-sans font-semibold text-zinc-200 text-sm">SMC Trade Ledger & Analytics Drawer</h3>
        </div>
        <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-widest font-bold">Post-Trade Diagnostics</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs font-mono">
          <thead>
            <tr className="border-b border-zinc-800/60 text-zinc-500 font-bold uppercase text-[10px] tracking-wider">
              <th className="py-2.5 px-3">Execution Time</th>
              <th className="py-2.5 px-3">Symbol</th>
              <th className="py-2.5 px-3">Action</th>
              <th className="py-2.5 px-3 text-right">Lots</th>
              <th className="py-2.5 px-3 text-right">Entry Price</th>
              <th className="py-2.5 px-3 text-right">Exit Price</th>
              <th className="py-2.5 px-3 text-right">PnL (USD)</th>
              <th className="py-2.5 px-3 text-center">Status</th>
              <th className="py-2.5 px-3 text-center">Diagnostics</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-850 text-zinc-300">
            {history.length === 0 ? (
              <tr>
                <td colSpan={9} className="py-8 text-center text-zinc-600 font-sans">
                  No trades recorded in current session. Awaiting first signal execution...
                </td>
              </tr>
            ) : (
              history.map((trade) => {
                const isExpanded = expandedTradeId === trade.id;
                const isProfit = trade.status === "PROFIT";
                const pnlClass = isProfit ? "text-emerald-400 font-bold" : "text-rose-400 font-bold";

                const entryTimeStr = new Date(trade.entryTime).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit"
                });

                return (
                  <React.Fragment key={trade.id}>
                    {/* Main Row */}
                    <tr
                      onClick={() => toggleExpand(trade.id)}
                      className="hover:bg-zinc-800/40 cursor-pointer transition-all duration-150 border-b border-zinc-850/30"
                    >
                      <td className="py-3 px-3 text-zinc-400">{entryTimeStr}</td>
                      <td className="py-3 px-3 font-sans font-bold text-white">{trade.pair}</td>
                      <td className="py-3 px-3">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                            trade.type === "BUY" ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"
                          }`}
                        >
                          {trade.type}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right text-zinc-400">{trade.lots.toFixed(1)}</td>
                      <td className="py-3 px-3 text-right font-semibold">{trade.entry.toFixed(trade.pair === "USDJPY" ? 2 : 5)}</td>
                      <td className="py-3 px-3 text-right font-semibold">{trade.exit.toFixed(trade.pair === "USDJPY" ? 2 : 5)}</td>
                      <td className={`py-3 px-3 text-right ${pnlClass}`}>
                        {trade.pnl >= 0 ? "+" : ""}${trade.pnl.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                      </td>
                      <td className="py-3 px-3 text-center">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase ${
                            isProfit ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"
                          }`}
                        >
                          {trade.status}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-center">
                        <button className="text-zinc-500 hover:text-zinc-300 font-sans text-[11px] font-bold flex items-center gap-1 mx-auto cursor-pointer">
                          {isExpanded ? "Hide" : "Inspect"}{" "}
                          {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                        </button>
                      </td>
                    </tr>

                    {/* Expandable Diagnostics Drawer */}
                    {isExpanded && (
                      <tr className="bg-zinc-950/40">
                        <td colSpan={9} className="py-3.5 px-5 border-l-2 border-emerald-500">
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 text-zinc-300">
                            {/* Priority 8: Post Trade Analysis */}
                            <div className="flex flex-col gap-2 bg-zinc-900/60 border border-zinc-850 p-3 rounded-xl shadow-inner">
                              <h4 className="font-sans font-bold text-zinc-200 text-xs flex items-center gap-1.5 border-b border-zinc-800 pb-1.5">
                                <Info className="w-3.5 h-3.5 text-emerald-400" /> Post-Trade Analytics
                              </h4>
                              <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[11px] font-mono">
                                <div className="flex justify-between py-0.5">
                                  <span className="text-zinc-500">Exit Reason:</span>
                                  <span className="font-sans font-bold text-zinc-300">{trade.exitReason}</span>
                                </div>
                                <div className="flex justify-between py-0.5">
                                  <span className="text-zinc-500">Duration:</span>
                                  <span className="text-zinc-300 font-bold">{trade.duration}</span>
                                </div>
                                <div className="flex justify-between py-0.5">
                                  <span className="text-zinc-500">MAE (Max Drawdown):</span>
                                  <span className="text-rose-400 font-bold">-{trade.mae.toFixed(1)} pips</span>
                                </div>
                                <div className="flex justify-between py-0.5">
                                  <span className="text-zinc-500">MFE (Max Run-up):</span>
                                  <span className="text-emerald-400 font-bold">+{trade.mfe.toFixed(1)} pips</span>
                                </div>
                                <div className="flex justify-between py-0.5">
                                  <span className="text-zinc-500">Exec Latency:</span>
                                  <span className="text-zinc-300 font-bold">{trade.latency} ms</span>
                                </div>
                                <div className="flex justify-between py-0.5">
                                  <span className="text-zinc-500">Slippage cost:</span>
                                  <span className="text-amber-400 font-bold">{trade.slippage.toFixed(1)} pips</span>
                                </div>
                                <div className="flex justify-between py-0.5">
                                  <span className="text-zinc-500">Broker Commission:</span>
                                  <span className="text-zinc-400 font-bold">${trade.commission.toFixed(2)}</span>
                                </div>
                                <div className="flex justify-between py-0.5">
                                  <span className="text-zinc-500">Realized R:R:</span>
                                  <span className="text-emerald-400 font-bold">+{trade.realRr.toFixed(2)} R</span>
                                </div>
                              </div>
                            </div>

                            {/* Priority 7: Trade Explanation */}
                            <div className="flex flex-col gap-2 bg-zinc-900/60 border border-zinc-850 p-3 rounded-xl shadow-inner">
                              <h4 className="font-sans font-bold text-zinc-200 text-xs flex items-center gap-1.5 border-b border-zinc-800 pb-1.5">
                                <Landmark className="w-3.5 h-3.5 text-emerald-400" /> Entry Qualification Checklist
                              </h4>
                              <div className="flex flex-col gap-1 text-[11px] font-sans">
                                {trade.explanation.map((item, idx) => (
                                  <div key={idx} className="flex items-start gap-1.5 py-0.5 text-zinc-300 leading-normal">
                                    <CheckCircle className="w-3.5 h-3.5 text-emerald-400 mt-0.5 shrink-0" />
                                    <span>{item}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
