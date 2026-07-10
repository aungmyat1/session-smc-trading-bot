/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect } from "react";
import { SocketProvider, useSocket } from "./context/SocketContext.js";
import { SvosResearchDashboard } from "./components/SvosResearchDashboard.js";
import { LiveOperationsDashboard } from "./components/LiveOperationsDashboard.js";
import { SuggestionsTab } from "./components/SuggestionsTab.js";
import { OperatorLogin } from "./components/OperatorLogin.js";
import { ValidationDashboard } from "./components/ValidationDashboard.js";
import { Clock, Play, Pause, RefreshCw, Zap, BookOpen, Lightbulb, ShieldCheck } from "lucide-react";

const DashboardContent: React.FC = () => {
  const { state, isConnected, resumeTrading, pauseTrading } = useSocket();
  const [currentTime, setCurrentTime] = useState(new Date());
  const [activeTab, setActiveTab] = useState<"LIVE" | "SVOS" | "SUGGESTIONS" | "VALIDATION">("LIVE");

  // Keep a live UTC clock ticking
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  if (!state) {
    return (
      <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center gap-4 text-white">
        <div className="flex flex-col items-center gap-2">
          <RefreshCw className="w-8 h-8 text-emerald-400 animate-spin" />
          <h2 className="font-sans font-bold text-base tracking-widest uppercase">Connecting to SMC Operations Center</h2>
          <p className="font-sans text-xs text-zinc-500">Retrieving real-time market structures, pipeline states, and transaction histories...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans select-none antialiased selection:bg-emerald-500 selection:text-black">
      {/* 1. Header / Operations Bar */}
      <header className="border-b border-zinc-900 bg-zinc-900/65 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-col sm:flex-row items-center justify-between gap-3">
          {/* Logo & Status */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-zinc-950 font-black shadow-lg shadow-emerald-500/10">
              SMC
            </div>
            <div className="flex flex-col">
              <h1 className="text-sm font-extrabold tracking-wider text-white uppercase flex items-center gap-2">
                Session SMC Trading Bot Dashboard
                <span className="font-mono text-[9px] bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-bold px-1.5 py-0.2 rounded">
                  v3.4 Production
                </span>
              </h1>
              <span className="text-[10px] text-zinc-400 font-mono tracking-wide uppercase font-bold">
                Operations Control Center (OCC)
              </span>
            </div>
          </div>

          {/* Central Dashboards Switcher */}
          <div className="flex items-center gap-1 bg-zinc-950 p-1 border border-zinc-850 rounded-xl font-mono text-[11px] font-bold">
            <button
              onClick={() => setActiveTab("LIVE")}
              id="tab-live-operations"
              className={`px-4 py-1.5 rounded-lg transition-all cursor-pointer flex items-center gap-1.5 ${activeTab === "LIVE" ? "bg-emerald-500 text-zinc-950 font-black shadow" : "text-zinc-400 hover:text-white"}`}
            >
              <Zap className="w-3.5 h-3.5 fill-current" /> LIVE TRADING
            </button>
            <button
              onClick={() => setActiveTab("SVOS")}
              id="tab-svos-research"
              className={`px-4 py-1.5 rounded-lg transition-all cursor-pointer flex items-center gap-1.5 ${activeTab === "SVOS" ? "bg-emerald-500 text-zinc-950 font-black shadow" : "text-zinc-400 hover:text-white"}`}
            >
              <BookOpen className="w-3.5 h-3.5 fill-current" /> SMC QUANT LAB
            </button>
            <button
              onClick={() => setActiveTab("SUGGESTIONS")}
              id="tab-suggestions"
              className={`px-4 py-1.5 rounded-lg transition-all cursor-pointer flex items-center gap-1.5 ${activeTab === "SUGGESTIONS" ? "bg-emerald-500 text-zinc-950 font-black shadow" : "text-zinc-400 hover:text-white"}`}
            >
              <Lightbulb className="w-3.5 h-3.5 fill-current" /> SUGGESTIONS
            </button>
            <button
              onClick={() => setActiveTab("VALIDATION")}
              id="tab-validation"
              className={`px-4 py-1.5 rounded-lg transition-all cursor-pointer flex items-center gap-1.5 ${activeTab === "VALIDATION" ? "bg-emerald-500 text-zinc-950 font-black shadow" : "text-zinc-400 hover:text-white"}`}
            >
              <ShieldCheck className="w-3.5 h-3.5 fill-current" /> VALIDATION
            </button>
          </div>

          {/* Clock & Pause Controls */}
          <div className="flex items-center gap-3">
            {/* UTC Clock */}
            <div className="flex items-center gap-1.5 font-mono text-xs text-zinc-400 bg-zinc-950/80 border border-zinc-800/80 px-2.5 py-1.5 rounded-xl">
              <Clock className="w-3.5 h-3.5 text-zinc-500" />
              <span>{currentTime.toISOString().split("T")[1].slice(0, 8)} UTC</span>
            </div>

            <OperatorLogin />

            {/* Global Pause override */}
            {state.isTradingPaused ? (
              <button
                onClick={resumeTrading}
                id="btn-resume-engine"
                className="flex items-center gap-1.5 text-xs font-bold text-zinc-950 bg-emerald-400 hover:bg-emerald-300 px-4 py-1.5 rounded-xl transition cursor-pointer shadow-lg shadow-emerald-500/10 hover:scale-[1.01]"
              >
                <Play className="w-3.5 h-3.5 fill-zinc-950" /> RESUME ENGINE
              </button>
            ) : (
              <button
                onClick={pauseTrading}
                id="btn-pause-engine"
                className="flex items-center gap-1.5 text-xs font-bold text-white bg-rose-500/25 hover:bg-rose-500 hover:text-white border border-rose-500/20 px-4 py-1.5 rounded-xl transition cursor-pointer shadow-lg hover:scale-[1.01]"
              >
                <Pause className="w-3.5 h-3.5" /> PAUSE ALL BOTS
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Body Stage */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 flex flex-col gap-4">
        {activeTab === "LIVE" ? (
          <LiveOperationsDashboard />
        ) : activeTab === "SVOS" ? (
          <SvosResearchDashboard />
        ) : activeTab === "SUGGESTIONS" ? (
          <SuggestionsTab />
        ) : (
          <ValidationDashboard />
        )}
      </main>

      {/* Footer credits */}
      <footer className="border-t border-zinc-900 bg-zinc-950 py-6 text-center text-xs font-mono text-zinc-600">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-4">
          <span>Session SMC Algorithmic Trading Operations Control Center</span>
          <span>© 2026 Session SMC LLC. All rights reserved.</span>
        </div>
      </footer>
    </div>
  );
};

export default function App() {
  return (
    <SocketProvider>
      <DashboardContent />
    </SocketProvider>
  );
}
