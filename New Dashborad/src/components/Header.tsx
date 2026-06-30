/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
import { Strategy, ValidationStage } from "../types";
import { Shield, BookOpen, Layers, Terminal, Server, Plus, Database, Cpu } from "lucide-react";

interface HeaderProps {
  strategies: Strategy[];
  selectedStrategy: Strategy | null;
  onSelectStrategy: (id: string) => void;
  onOpenCreateModal: () => void;
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

export default function Header({
  strategies,
  selectedStrategy,
  onSelectStrategy,
  onOpenCreateModal,
  activeTab,
  setActiveTab
}: HeaderProps) {
  
  const getStageColor = (stage: ValidationStage) => {
    switch (stage) {
      case ValidationStage.INTAKE:
        return "bg-slate-100 text-slate-800 border-slate-300";
      case ValidationStage.AUDIT:
      case ValidationStage.REFINEMENT:
        return "bg-indigo-50 text-indigo-800 border-indigo-200";
      case ValidationStage.REPLAY:
      case ValidationStage.STATISTICAL:
      case ValidationStage.ROBUSTNESS:
        return "bg-blue-50 text-blue-800 border-blue-200";
      case ValidationStage.VIRTUAL_DEMO:
        return "bg-amber-50 text-amber-800 border-amber-200";
      case ValidationStage.VERIFICATION_READY:
        return "bg-emerald-50 text-emerald-800 border-emerald-200";
      case ValidationStage.EXECUTION:
      case ValidationStage.LIVE_DEMO:
        return "bg-purple-50 text-purple-800 border-purple-200";
      case ValidationStage.PRODUCTION_APPROVAL:
        return "bg-emerald-900 text-white border-emerald-950";
      default:
        return "bg-slate-100 text-slate-800 border-slate-200";
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
    <header className="border-b border-slate-200 bg-white sticky top-0 z-50 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          {/* Logo / Title */}
          <div className="flex items-center space-x-3">
            <div className="bg-slate-900 p-2 text-white rounded-lg">
              <Shield className="h-6 w-6 stroke-[1.5]" />
            </div>
            <div>
              <span className="font-display font-bold text-slate-900 tracking-tight text-lg block">
                SVOS // RESEARCH GATE
              </span>
              <span className="text-[10px] font-mono text-slate-500 tracking-wider uppercase block -mt-1">
                Institutional Strategy Validation
              </span>
            </div>
          </div>

          {/* Strategy Selector / Status */}
          <div className="flex items-center space-x-4">
            <div className="flex flex-col items-end">
              <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Active Workspace</span>
              <div className="flex items-center space-x-2 mt-1">
                <select
                  value={selectedStrategy?.id || ""}
                  onChange={(e) => onSelectStrategy(e.target.value)}
                  className="font-sans font-medium text-slate-900 bg-slate-50 border border-slate-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-slate-900 focus:border-slate-900 transition-all cursor-pointer"
                  id="strategy-workspace-select"
                >
                  <option value="" disabled>Select Strategy...</option>
                  {strategies.map((strat) => (
                    <option key={strat.id} value={strat.id}>
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

            <button
              onClick={onOpenCreateModal}
              className="flex items-center space-x-1 bg-slate-900 hover:bg-slate-800 text-white px-3 py-1.5 rounded-md text-sm font-medium transition-colors"
              id="header-create-strategy-btn"
            >
              <Plus className="h-4 w-4" />
              <span>Intake Idea</span>
            </button>
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
                className={`group flex items-center space-x-2 py-3 px-4 border-b-2 font-medium text-xs font-mono tracking-wide uppercase transition-all whitespace-nowrap outline-none ${
                  isActive
                    ? "border-slate-900 text-slate-950 font-semibold"
                    : "border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300"
                }`}
                id={`tab-${item.id}`}
              >
                <Icon className={`h-4 w-4 stroke-[1.5] ${isActive ? "text-slate-950" : "text-slate-400 group-hover:text-slate-500"}`} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
