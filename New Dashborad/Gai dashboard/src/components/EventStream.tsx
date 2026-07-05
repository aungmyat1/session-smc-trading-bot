/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
import { EventLog } from "../types.js";
import { Terminal, ShieldAlert, Sparkles, HelpCircle } from "lucide-react";

interface Props {
  events: EventLog[];
}

export const EventStream: React.FC<Props> = ({ events }) => {
  const getBadgeStyle = (level: string) => {
    switch (level) {
      case "SUCCESS":
        return "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
      case "WARNING":
        return "text-amber-400 bg-amber-500/10 border-amber-500/20";
      case "CRITICAL":
        return "text-rose-400 bg-rose-500/10 border-rose-500/20";
      default:
        return "text-blue-400 bg-blue-500/10 border-blue-500/20";
    }
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-lg flex flex-col gap-3">
      <div className="flex items-center justify-between border-b border-zinc-800/60 pb-2.5">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-emerald-400" />
          <h3 className="font-sans font-semibold text-zinc-200 text-sm">Chronological Strategy Event Stream</h3>
        </div>
        <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-widest font-bold">Standard Log Output</span>
      </div>

      {/* Terminal Board */}
      <div className="bg-zinc-950/90 border border-zinc-900 rounded-xl p-3 h-44 overflow-y-auto font-mono text-[11px] flex flex-col gap-1.5 scrollbar-thin scrollbar-thumb-zinc-800 scrollbar-track-transparent">
        {events.length === 0 ? (
          <div className="flex items-center justify-center h-full text-zinc-600">
            Awaiting standard events broadcast...
          </div>
        ) : (
          events.map((ev) => {
            const timeStr = new Date(ev.timestamp).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit"
            });
            return (
              <div key={ev.id} className="flex items-start gap-2.5 hover:bg-zinc-900/40 p-1 rounded transition duration-150">
                <span className="text-zinc-600 shrink-0 font-semibold">[{timeStr}]</span>
                <span
                  className={`px-1.5 py-0.2 rounded border text-[8px] font-bold tracking-tight shrink-0 ${getBadgeStyle(
                    ev.level
                  )}`}
                >
                  {ev.level}
                </span>
                <span className="text-zinc-300 select-all leading-normal">{ev.message}</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
