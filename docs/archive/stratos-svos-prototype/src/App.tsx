/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect } from "react";
import Header from "./components/Header";
import StrategyIntake from "./components/StrategyIntake";
import PipelineStageView from "./components/PipelineStageView";
import AuditReportView from "./components/AuditReportView";
import ReplayView from "./components/ReplayView";
import StatisticalView from "./components/StatisticalView";
import RobustnessView from "./components/RobustnessView";
import VirtualDemoView from "./components/VirtualDemoView";
import ExecutionSafetyView from "./components/ExecutionSafetyView";
import GovernanceView from "./components/GovernanceView";
import VersionHistoryChart from "./components/VersionHistoryChart";
import { Strategy, ValidationStage, StrategyRules } from "./types";
import { BookOpen, AlertTriangle, Shield, Layers, HelpCircle, Activity, Sparkles, FolderKanban } from "lucide-react";

export default function App() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [selectedStrategyId, setSelectedStrategyId] = useState<string>("");
  const [activeTab, setActiveTab] = useState<string>("registry");
  const [isCreateOpen, setIsCreateOpen] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [compareStrategyIds, setCompareStrategyIds] = useState<string[]>([]);
  const [isComparing, setIsComparing] = useState(false);

  const [isDarkMode, setIsDarkMode] = useState<boolean>(() => {
    const saved = localStorage.getItem("theme");
    if (saved) return saved === "dark";
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add("dark");
      localStorage.setItem("theme", "dark");
    } else {
      document.documentElement.classList.remove("dark");
      localStorage.setItem("theme", "light");
    }
  }, [isDarkMode]);

  const toggleDarkMode = () => {
    setIsDarkMode(prev => !prev);
  };

  const handleToggleCompare = (id: string) => {
    setCompareStrategyIds(prev => {
      if (prev.includes(id)) {
        const next = prev.filter(item => item !== id);
        if (next.length < 2) {
          setIsComparing(false);
        }
        return next;
      } else {
        if (prev.length >= 2) {
          return [prev[1], id];
        }
        return [...prev, id];
      }
    });
  };

  // Load all strategies from backend on mount
  const fetchStrategies = async () => {
    try {
      const response = await fetch("/api/strategies");
      if (!response.ok) {
        throw new Error("Failed to load strategies database.");
      }
      const data = await response.json();
      setStrategies(data);
      if (data.length > 0 && !selectedStrategyId) {
        setSelectedStrategyId(data[0].id);
      }
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Failed to establish database connection.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStrategies();
  }, []);

  const handleSelectStrategy = (id: string) => {
    setSelectedStrategyId(id);
    // Automatically switch tabs depending on the stage of the strategy to maximize usability
    const strat = strategies.find(s => s.id === id);
    if (strat) {
      if (strat.status === ValidationStage.INTAKE) {
        setActiveTab("registry");
      } else if (strat.status === ValidationStage.AUDIT || strat.status === ValidationStage.REFINEMENT) {
        setActiveTab("audit");
      }
    }
  };

  // POST new strategy intake
  const handleAddStrategy = async (name: string, description: string, rules: StrategyRules) => {
    try {
      const response = await fetch("/api/strategies", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          name,
          description,
          rules,
          author: "Alpha Group PM"
        })
      });

      if (!response.ok) {
        throw new Error("Failed to create strategy.");
      }

      const newStrat = await response.json();
      setStrategies(prev => [...prev, newStrat]);
      setSelectedStrategyId(newStrat.id);
      setActiveTab("registry");
    } catch (err: any) {
      console.error(err);
      alert(err.message || "Failed to submit strategy.");
    }
  };

  // POST promote strategy stage
  const handlePromoteStrategy = async () => {
    if (!selectedStrategyId) return;
    try {
      const response = await fetch(`/api/strategies/${selectedStrategyId}/promote`, {
        method: "POST"
      });

      if (!response.ok) {
        throw new Error("Failed to promote strategy.");
      }

      const updatedStrat = await response.json();
      setStrategies(prev => prev.map(s => s.id === selectedStrategyId ? updatedStrat : s));
      
      // Auto-route tabs for optimal UX
      if (updatedStrat.status === ValidationStage.AUDIT) {
        setActiveTab("audit");
      } else if (updatedStrat.status === ValidationStage.REPLAY) {
        setActiveTab("replay");
      } else if (updatedStrat.status === ValidationStage.STATISTICAL) {
        setActiveTab("replay");
      } else if (updatedStrat.status === ValidationStage.ROBUSTNESS) {
        setActiveTab("robustness");
      } else if (updatedStrat.status === ValidationStage.VIRTUAL_DEMO) {
        setActiveTab("virtual");
      } else if (updatedStrat.status === ValidationStage.EXECUTION) {
        setActiveTab("safety");
      } else if (updatedStrat.status === ValidationStage.PRODUCTION_APPROVAL) {
        setActiveTab("governance");
      }
    } catch (err: any) {
      console.error(err);
      alert(err.message || "Failed to promote strategy gate.");
    }
  };

  // POST demote strategy stage
  const handleDemoteStrategy = async (targetStage: ValidationStage, comments: string) => {
    if (!selectedStrategyId) return;
    try {
      const response = await fetch(`/api/strategies/${selectedStrategyId}/demote`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          targetStage,
          comments,
          actor: "Continuous Risk Watcher"
        })
      });

      if (!response.ok) {
        throw new Error("Failed to demote strategy.");
      }

      const updatedStrat = await response.json();
      setStrategies(prev => prev.map(s => s.id === selectedStrategyId ? updatedStrat : s));
      
      if (targetStage === ValidationStage.INTAKE) {
        setActiveTab("registry");
      } else if (targetStage === ValidationStage.AUDIT) {
        setActiveTab("audit");
      }
    } catch (err: any) {
      console.error(err);
      alert(err.message || "Failed to demote strategy.");
    }
  };

  // Apply an AI fix to a specific logical defect
  const handleApplyDefectFix = async (defectId: string) => {
    if (!selectedStrategyId) return;
    const strat = strategies.find(s => s.id === selectedStrategyId);
    if (!strat) return;

    // Simulate modifying strategy specifications on the backend, resolving this defect
    try {
      const defects = strat.evidence.audit?.logicalDefects.filter(d => d.id !== defectId) || [];
      const score = Math.min(100, (strat.evidence.audit?.score || 80) + 10);
      
      const updatedAudit = {
        ...strat.evidence.audit!,
        score,
        logicalDefects: defects
      };

      const response = await fetch(`/api/strategies/${selectedStrategyId}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          evidence: {
            ...strat.evidence,
            audit: updatedAudit
          }
        })
      });

      if (!response.ok) {
        throw new Error("Failed to update strategy rules.");
      }

      const updatedStrat = await response.json();
      setStrategies(prev => prev.map(s => s.id === selectedStrategyId ? updatedStrat : s));
    } catch (err: any) {
      console.error(err);
    }
  };

  const selectedStrategy = strategies.find(s => s.id === selectedStrategyId) || null;
  const comparedStrategies = strategies.filter(s => compareStrategyIds.includes(s.id));

  const getStageBadgeStyles = (status: ValidationStage, isSelected: boolean) => {
    switch (status) {
      case ValidationStage.PRODUCTION_APPROVAL:
        return isSelected
          ? "bg-emerald-950/80 text-emerald-300 border-emerald-800"
          : "bg-emerald-50 text-emerald-700 border-emerald-200";
      case ValidationStage.EXECUTION:
      case ValidationStage.LIVE_DEMO:
      case ValidationStage.VERIFICATION_READY:
        return isSelected
          ? "bg-blue-950/80 text-blue-300 border-blue-800"
          : "bg-blue-50 text-blue-700 border-blue-200";
      case ValidationStage.ROBUSTNESS:
      case ValidationStage.VIRTUAL_DEMO:
      case ValidationStage.STATISTICAL:
        return isSelected
          ? "bg-purple-950/80 text-purple-300 border-purple-800"
          : "bg-purple-50 text-purple-700 border-purple-200";
      case ValidationStage.AUDIT:
      case ValidationStage.REFINEMENT:
      case ValidationStage.REPLAY:
        return isSelected
          ? "bg-amber-950/80 text-amber-300 border-amber-800"
          : "bg-amber-50 text-amber-700 border-amber-200";
      default:
        return isSelected
          ? "bg-slate-800 text-slate-300 border-slate-700"
          : "bg-slate-100 text-slate-700 border-slate-200";
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex flex-col font-sans text-slate-800 dark:text-slate-100 antialiased selection:bg-slate-900 dark:selection:bg-slate-100 selection:text-white dark:selection:text-slate-950 transition-colors duration-200">
      {/* 1. Header Bar */}
      <Header
        strategies={strategies}
        selectedStrategy={selectedStrategy}
        onSelectStrategy={handleSelectStrategy}
        onOpenCreateModal={() => setIsCreateOpen(true)}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        isDarkMode={isDarkMode}
        onToggleDarkMode={toggleDarkMode}
      />

      {/* 2. Main Workstation Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {loading && (
          <div className="flex flex-col justify-center items-center h-[50vh] space-y-3">
            <div className="h-6 w-6 border-2 border-slate-900 border-t-transparent animate-spin rounded-full" />
            <p className="text-xs font-mono text-slate-500 uppercase tracking-widest animate-pulse">
              Syncing Ledger Systems...
            </p>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-5 text-center text-red-700 max-w-md mx-auto my-12">
            <AlertTriangle className="h-8 w-8 text-red-600 mx-auto mb-2" />
            <p className="font-bold">System Connection Interrupted</p>
            <p className="text-xs text-red-600 mt-1">{error}</p>
          </div>
        )}

        {!loading && !error && (
          <div className="space-y-6">
            {/* Create strategy panel */}
            {isCreateOpen && (
              <StrategyIntake
                onAddStrategy={handleAddStrategy}
                onClose={() => setIsCreateOpen(false)}
              />
            )}

            {/* Strategy Context Stepper banner */}
            {selectedStrategy && (
              <PipelineStageView
                strategy={selectedStrategy}
                onPromote={handlePromoteStrategy}
                onDemote={handleDemoteStrategy}
              />
            )}

            {/* Tab panel dispatcher */}
            {selectedStrategy ? (
              <div className="transition-all duration-300">
                {activeTab === "registry" && (
                  <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
                    {/* Overview Card & Trend Visualization */}
                    <div className="md:col-span-8 space-y-6">
                      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-6 shadow-sm space-y-4 transition-colors duration-200">
                        <div className="flex justify-between items-start border-b border-slate-100 dark:border-slate-800 pb-3">
                          <div>
                            <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-widest block">Strategy Overview</span>
                            <h2 className="font-display font-bold text-slate-950 dark:text-slate-50 text-xl mt-0.5">{selectedStrategy.name}</h2>
                            <p className="text-[10px] font-mono text-slate-500 dark:text-slate-400 mt-0.5">ID: {selectedStrategy.id} // Author: {selectedStrategy.author}</p>
                          </div>
                          <span className="text-xs font-mono font-semibold bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 px-2 py-1 rounded">
                            v{selectedStrategy.version}
                          </span>
                        </div>

                        <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed font-sans">{selectedStrategy.description}</p>

                        <div className="border-t border-slate-100 dark:border-slate-800 pt-4 grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs font-mono">
                          <div>
                            <span className="text-slate-400 dark:text-slate-500 uppercase tracking-wider block text-[10px]">Symbol Block</span>
                            <span className="font-bold text-slate-900 dark:text-slate-100 block mt-0.5">{selectedStrategy.rules.symbol}</span>
                          </div>
                          <div>
                            <span className="text-slate-400 dark:text-slate-500 uppercase tracking-wider block text-[10px]">Base Interval</span>
                            <span className="font-bold text-slate-900 dark:text-slate-100 block mt-0.5">{selectedStrategy.rules.timeframe}</span>
                          </div>
                          <div>
                            <span className="text-slate-400 dark:text-slate-500 uppercase tracking-wider block text-[10px]">Registry Date</span>
                            <span className="font-bold text-slate-900 dark:text-slate-100 block mt-0.5">{new Date(selectedStrategy.createdAt).toLocaleDateString()}</span>
                          </div>
                        </div>
                      </div>

                      {/* Performance Trend Visualization (Recharts) */}
                      <VersionHistoryChart 
                        strategy={isComparing && comparedStrategies.length === 2 ? comparedStrategies[0] : selectedStrategy}
                        compareStrategy={isComparing && comparedStrategies.length === 2 ? comparedStrategies[1] : null}
                      />
                    </div>

                    {/* Registry List / Stats Sidebar with Checkboxes and Compare Controls */}
                    <div className="md:col-span-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm flex flex-col justify-between space-y-4 transition-colors duration-200">
                      <div className="space-y-4 w-full">
                        <h3 className="font-display font-semibold text-slate-900 dark:text-slate-100 text-sm flex items-center space-x-1.5 border-b border-slate-100 dark:border-slate-800 pb-2">
                          <FolderKanban className="h-4 w-4 text-slate-600 dark:text-slate-400" />
                          <span>Strategy Workspace Index</span>
                        </h3>

                        <div className="space-y-2 max-h-56 overflow-y-auto dark-scrollbar pr-1">
                          {strategies.map(s => {
                            const isChecked = compareStrategyIds.includes(s.id);
                            return (
                              <div key={s.id} className="flex items-center space-x-2 w-full">
                                <input
                                  type="checkbox"
                                  checked={isChecked}
                                  onChange={() => handleToggleCompare(s.id)}
                                  className="rounded border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 text-indigo-600 focus:ring-indigo-500 h-4 w-4 cursor-pointer flex-shrink-0 transition-colors"
                                  id={`compare-checkbox-${s.id}`}
                                  title="Select to compare performance trends"
                                />
                                <button
                                  onClick={() => handleSelectStrategy(s.id)}
                                  className={`flex-1 text-left p-2.5 border rounded-md transition-all flex justify-between items-center truncate cursor-pointer ${
                                    s.id === selectedStrategyId
                                      ? "bg-slate-950 dark:bg-slate-100 border-slate-950 dark:border-slate-100 text-white dark:text-slate-950"
                                      : "bg-slate-50 dark:bg-slate-950 border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-850"
                                  }`}
                                  id={`index-select-${s.id}`}
                                >
                                  <div className="truncate pr-1 text-left">
                                    <span className="font-semibold block text-xs truncate max-w-[110px]">{s.name}</span>
                                    <span className={`font-mono text-[9px] block ${s.id === selectedStrategyId ? "text-slate-400 dark:text-slate-600" : "text-slate-500 dark:text-slate-400"}`}>
                                      ID: {s.id} // v{s.version}
                                    </span>
                                  </div>
                                  <span className={`font-mono text-[8px] px-1 py-0.5 rounded uppercase font-bold border flex-shrink-0 transition-colors ${
                                    getStageBadgeStyles(s.status, s.id === selectedStrategyId)
                                  }`}>
                                    {s.status.replace(" Validation", "").replace(" Strategy", "")}
                                  </span>
                                </button>
                              </div>
                            );
                          })}
                        </div>
                      </div>

                      {/* Compare Activation Panel */}
                      <div className="pt-3 border-t border-slate-100 flex flex-col space-y-2 w-full">
                        <button
                          onClick={() => {
                            if (compareStrategyIds.length === 2) {
                              setIsComparing(!isComparing);
                            }
                          }}
                          disabled={compareStrategyIds.length !== 2}
                          className={`w-full py-2 px-3 rounded text-xs font-mono font-semibold flex items-center justify-center space-x-2 transition-all ${
                            compareStrategyIds.length === 2
                              ? isComparing
                                ? "bg-rose-50 border border-rose-200 text-rose-700 hover:bg-rose-100 cursor-pointer"
                                : "bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm cursor-pointer"
                              : "bg-slate-100 text-slate-400 border border-slate-200 cursor-not-allowed"
                          }`}
                          id="compare-strategies-btn"
                        >
                          <span>{isComparing ? "Clear Comparison Overlay" : "Compare Selected (2)"}</span>
                        </button>
                        {compareStrategyIds.length < 2 ? (
                          <p className="text-[10px] text-slate-400 text-center font-mono">
                            Check exactly 2 strategy checkboxes above to enable benchmarking.
                          </p>
                        ) : (
                          <p className="text-[10px] text-indigo-600 text-center font-mono animate-pulse font-medium">
                            {isComparing 
                              ? "Comparison overlay active on chart!" 
                              : "Ready to compare! Click button above."}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {activeTab === "audit" && (
                  <AuditReportView
                    auditReport={selectedStrategy.evidence.audit}
                    rules={selectedStrategy.rules}
                    onApplyFix={handleApplyDefectFix}
                  />
                )}

                {activeTab === "replay" && (
                  <div className="space-y-6">
                    <ReplayView
                      replayReport={selectedStrategy.evidence.replay}
                      strategyName={selectedStrategy.name}
                    />
                    <div className="border-t border-slate-200/50 pt-2">
                      <StatisticalView statistics={selectedStrategy.evidence.statistics} />
                    </div>
                  </div>
                )}

                {activeTab === "robustness" && (
                  <RobustnessView robustnessReport={selectedStrategy.evidence.robustness} />
                )}

                {activeTab === "virtual" && (
                  <VirtualDemoView
                    virtualDemo={selectedStrategy.evidence.virtualDemo}
                    symbol={selectedStrategy.rules.symbol}
                  />
                )}

                {activeTab === "safety" && (
                  <ExecutionSafetyView safetyReport={selectedStrategy.evidence.executionSafety} />
                )}

                {activeTab === "governance" && (
                  <GovernanceView strategy={selectedStrategy} />
                )}
              </div>
            ) : (
              <div className="bg-white border border-slate-200 rounded-lg p-16 text-center text-slate-500">
                <HelpCircle className="h-12 w-12 text-slate-400 mx-auto mb-3" />
                <p className="font-semibold text-sm">Awaiting Strategic Workspace Indexing</p>
                <p className="text-xs text-slate-500 mt-1">Please create a new strategy idea or load sample template strategies to begin.</p>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
