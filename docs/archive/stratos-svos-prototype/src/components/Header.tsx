/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
import { Strategy, ValidationStage } from "../types";
import { Shield, BookOpen, Layers, Terminal, Server, Plus, Database, Cpu, Sun, Moon } from "lucide-react";

interface HeaderProps {
  strategies: Strategy[];
  selectedStrategy: Strategy | null;
  onSelectStrategy: (id: string) => void;
  onOpenCreateModal: () => void;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  isDarkMode: boolean;
  onToggleDarkMode: () => void;
}

export default function Header({
  strategies,
  selectedStrategy,
  onSelectStrategy,
  onOpenCreateModal,
  activeTab,
  setActiveTab,
  isDarkMode,
  onToggleDarkMode
}: HeaderProps) {
  
  const getStageColor = (stage: ValidationStage) => {
    switch (stage) {
      case ValidationStage.INTAKE:
        return "bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border-slate-300 dark:border-slate-700";
      case ValidationStage.AUDIT:
      case ValidationStage.REFINEMENT:
        return "bg-indigo-50 dark:bg-indigo-950/40 text-indigo-800 dark:text-indigo-300 border-indigo-200 dark:border-indigo-900/60";
      case ValidationStage.REPLAY:
      case ValidationStage.STATISTICAL:
      case ValidationStage.ROBUSTNESS:
        return "bg-blue-50 dark:bg-blue-950/40 text-blue-800 dark:text-blue-300 border-blue-200 dark:border-blue-900/60";
      case ValidationStage.VIRTUAL_DEMO:
        return "bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 border-amber-200 dark:border-amber-900/60";
      case ValidationStage.VERIFICATION_READY:
        return "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 border-emerald-200 dark:border-emerald-900/60";
      case ValidationStage.EXECUTION:
      case ValidationStage.LIVE_DEMO:
        return "bg-purple-50 dark:bg-purple-950/40 text-purple-800 dark:text-purple-300 border-purple-200 dark:border-purple-900/60";
      case ValidationStage.PRODUCTION_APPROVAL:
        return "bg-emerald-900 dark:bg-emerald-800 text-white border-emerald-950 dark:border-emerald-700";
      default:
        return "bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border-slate-200 dark:border-slate-700";
    }
  };

  const navItems = [
    { id: "registry", label: "Intake & Registry", icon: BookOpen },
    { id: "audit", label: "AI Audit & Refinement", icon: Cpu },
    { id: "replay", label: "Historical Replay & Stats", icon: Layers },
    { id: "robustness", label: "Robustness & Stress Test", icon: Shield },
    { id: "virtual", label: "Virtual Demo Simulator", icon: Terminal },
    { id: "safety", label: "Execution & Safety", icon: Server },
    { id: "governance", label: "Governance & Ledger", icon: Database }
  ];

  return (
    <header className="border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 sticky top-0 z-50 shadow-sm transition-colors duration-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          {/* Logo / Title */}
          <div className="flex items-center space-x-3">
            <div className="bg-slate-900 dark:bg-slate-100 p-2 text-white dark:text-slate-900 rounded-lg">
              <Shield className="h-6 w-6 stroke-[1.5]" />
            </div>
            <div>
              <span className="font-display font-bold text-slate-900 dark:text-slate-50 tracking-tight text-lg block">
                SVOS // RESEARCH GATE
              </span>
              <span className="text-[10px] font-mono text-slate-500 dark:text-slate-400 tracking-wider uppercase block -mt-1">
                Institutional Strategy Validation
              </span>
            </div>
          </div>

          {/* Strategy Selector / Status */}
          <div className="flex items-center space-x-4">
            <div className="flex flex-col items-end">
              <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-wider font-semibold">Active Workspace</span>
              <div className="flex items-center space-x-2 mt-1">
                <select
                  value={selectedStrategy?.id || ""}
                  onChange={(e) => onSelectStrategy(e.target.value)}
                  className="font-sans font-medium text-slate-900 dark:text-slate-100 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-slate-900 dark:focus:ring-slate-100 focus:border-slate-900 dark:focus:border-slate-100 transition-all cursor-pointer"
                  id="strategy-workspace-select"
                >
                  <option value="" disabled>Select Strategy...</option>
                  {strategies.map((strat) => (
                    <option key={strat.id} value={strat.id} className="dark:bg-slate-900 dark:text-slate-100">
                      [{strat.id}] {strat.name} (v{strat.version})
                    </option>
                  ))}
                </select>
                
                {selectedStrategy && (
                  <span className={`px-2.5 py-1 text-xs font-mono font-semibold rounded-md border ${getStageColor(selectedStrategy.status)} transition-all duration-300`}>
                    {selectedStrategy.status.toUpperCase()}
                  </span>
                )}
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <button
                onClick={onOpenCreateModal}
                className="flex items-center space-x-1 bg-slate-900 hover:bg-slate-800 dark:bg-slate-100 dark:hover:bg-slate-200 dark:text-slate-900 text-white px-3 py-1.5 rounded-md text-sm font-medium transition-colors"
                id="header-create-strategy-btn"
              >
                <Plus className="h-4 w-4" />
                <span>Intake Idea</span>
              </button>

              <button
                onClick={onToggleDarkMode}
                className="flex items-center justify-center p-2 rounded-md text-slate-500 hover:text-slate-800 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-slate-100 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-700 cursor-pointer transition-colors"
                id="header-theme-toggle-btn"
                title={isDarkMode ? "Switch to light mode" : "Switch to dark mode"}
              >
                {isDarkMode ? <Sun className="h-4 w-4 text-amber-500" /> : <Moon className="h-4 w-4 text-indigo-600" />}
              </button>
            </div>
          </div>
        </div>

        {/* Tab-based Research Section Navigation */}
        <nav className="flex space-x-1 overflow-x-auto pb-px" aria-label="Tabs">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`group flex items-center space-x-2 py-3 px-4 border-b-2 font-medium text-xs font-mono tracking-wide uppercase transition-all whitespace-nowrap outline-none cursor-pointer ${
                  isActive
                    ? "border-slate-900 dark:border-slate-100 text-slate-950 dark:text-slate-50 font-semibold"
                    : "border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 hover:border-slate-300 dark:hover:border-slate-700"
                }`}
                id={`tab-${item.id}`}
              >
                <Icon className={`h-4 w-4 stroke-[1.5] ${isActive ? "text-slate-950 dark:text-slate-50" : "text-slate-400 dark:text-slate-500 group-hover:text-slate-500 dark:group-hover:text-slate-400"}`} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
