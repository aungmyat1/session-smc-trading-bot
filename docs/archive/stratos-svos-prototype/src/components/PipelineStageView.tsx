/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from "react";
import { Strategy, ValidationStage } from "../types";
import { ChevronRight, ArrowRight, CheckCircle2, Shield, Lock, AlertTriangle, Play, RefreshCw } from "lucide-react";

interface PipelineStageViewProps {
  strategy: Strategy;
  onPromote: () => Promise<void>;
  onDemote: (targetStage: ValidationStage, comments: string) => Promise<void>;
}

export default function PipelineStageView({ strategy, onPromote, onDemote }: PipelineStageViewProps) {
  const [isPromoting, setIsPromoting] = useState(false);
  const [isDemoting, setIsDemoting] = useState(false);
  const [demoteTarget, setDemoteTarget] = useState<ValidationStage>(ValidationStage.INTAKE);
  const [demoteComments, setDemoteComments] = useState("");

  const stages = [
    { stage: ValidationStage.INTAKE, code: "INTK", desc: "Strategy Intake & Schema Compilation" },
    { stage: ValidationStage.AUDIT, code: "AUDT", desc: "Logical Completeness & Defect Audit" },
    { stage: ValidationStage.REFINEMENT, code: "REFN", desc: "AI Optimization & Parameter Mapping" },
    { stage: ValidationStage.REPLAY, code: "RPLY", desc: "Historical Replay & Trade Engine" },
    { stage: ValidationStage.STATISTICAL, code: "STAT", desc: "Statistical Significance & MC Analysis" },
    { stage: ValidationStage.ROBUSTNESS, code: "ROBS", desc: "Parameter Sweep & Stress Testing" },
    { stage: ValidationStage.VIRTUAL_DEMO, code: "VDEM", desc: "Virtual Broker Latency Simulation" },
    { stage: ValidationStage.VERIFICATION_READY, code: "VRDY", desc: "Research Sign-Off & Verification Gate" },
    { stage: ValidationStage.EXECUTION, code: "EXEC", desc: "Operational Safety & Risk Verification" },
    { stage: ValidationStage.LIVE_DEMO, code: "LDEM", desc: "Live Paper Channel Synchronization" },
    { stage: ValidationStage.PRODUCTION_APPROVAL, code: "PROD", desc: "Immutable Sign-Off & Risk Cap Approval" }
  ];

  const currentIdx = stages.findIndex(s => s.stage === strategy.status);

  // Describe entry conditions/criteria for current active stage
  const getStageCriteria = (stage: ValidationStage) => {
    switch (stage) {
      case ValidationStage.INTAKE:
        return {
          requirements: ["Qualitative description provided", "Parameters defined"],
          objective: "Standardize research spec into a structured, JSON strategy blueprint."
        };
      case ValidationStage.AUDIT:
        return {
          requirements: ["Zero high-severity logical defects", "Auditor pass confirmation"],
          objective: "Identify ambiguities and contradictions before historical simulation."
        };
      case ValidationStage.REFINEMENT:
        return {
          requirements: ["Parameters compiled", "Logic bounds mapped"],
          objective: "Apply AI-assisted adjustments and compile machine-readable parameters."
        };
      case ValidationStage.REPLAY:
        return {
          requirements: ["Historical database linked", "Symbol and timeframe declared"],
          objective: "Execute trades chronologically to verify market capture."
        };
      case ValidationStage.STATISTICAL:
        return {
          requirements: ["Minimum 15 historical trades simulated", "Annualized returns compiled"],
          objective: "Assert edge significance with Sharpe Ratio, Sortino Ratio, and t-stats."
        };
      case ValidationStage.ROBUSTNESS:
        return {
          requirements: ["Monte Carlo percentile validation passed", "Baseline Sharpe > 1.0"],
          objective: "Vary parameters to detect overfitting and stress-test during high volatility."
        };
      case ValidationStage.VIRTUAL_DEMO:
        return {
          requirements: ["Noise test passed", "No parameters overfitted"],
          objective: "Replay trades through broker emulation simulating latency, spreads, and slippage."
        };
      case ValidationStage.VERIFICATION_READY:
        return {
          requirements: ["Average simulated slippage cost calculated", "Virtual Demo successfully closed"],
          objective: "Consolidate and review complete quantitative research evidence package."
        };
      case ValidationStage.EXECUTION:
        return {
          requirements: ["Research Committee approval sign-off", "Evidence package locked"],
          objective: "Verify operational safety guards (maximum sizes, circuit breakers)."
        };
      case ValidationStage.LIVE_DEMO:
        return {
          requirements: ["Execution Safety Score > 80", "Emergency bypass trigger verified"],
          objective: "Deploy to a real-time paper broker to monitor telemetry and latency drift."
        };
      case ValidationStage.PRODUCTION_APPROVAL:
        return {
          requirements: ["Minimum 48 hours active paper performance", "Operational stability verified"],
          objective: "Final risk board review, immutable hashing, and capital allocation."
        };
    }
  };

  const activeCriteria = getStageCriteria(strategy.status);

  const handlePromoteClick = async () => {
    setIsPromoting(true);
    try {
      await onPromote();
    } finally {
      setIsPromoting(false);
    }
  };

  const handleDemoteClick = async () => {
    if (!demoteComments.trim()) return;
    setIsPromoting(true); // show general loading
    try {
      await onDemote(demoteTarget, demoteComments);
      setIsDemoting(false);
      setDemoteComments("");
    } finally {
      setIsPromoting(false);
    }
  };

  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm mb-6 transition-colors duration-200">
      {/* 11 Stage Stepper Indicator */}
      <div className="mb-6 overflow-x-auto pb-4 dark-scrollbar">
        <div className="flex items-center min-w-[1000px] px-1">
          {stages.map((st, idx) => {
            const isCompleted = idx < currentIdx;
            const isActive = idx === currentIdx;
            const isFuture = idx > currentIdx;

            return (
              <React.Fragment key={st.stage}>
                <div className="flex flex-col items-center flex-1 relative">
                  {/* Step bubble */}
                  <div
                    className={`h-8 w-8 rounded-full border-2 flex items-center justify-center font-mono text-[10px] font-semibold transition-all duration-300 z-10 ${
                      isActive
                        ? "bg-slate-900 border-slate-900 text-white dark:bg-slate-100 dark:border-slate-100 dark:text-slate-900 shadow-md scale-110"
                        : isCompleted
                        ? "bg-emerald-50 dark:bg-emerald-950/20 border-emerald-500 text-emerald-700 dark:text-emerald-400"
                        : "bg-slate-50 dark:bg-slate-950 border-slate-200 dark:border-slate-800 text-slate-400 dark:text-slate-500"
                    }`}
                    title={st.desc}
                  >
                    {isCompleted ? <CheckCircle2 className="h-4 w-4" /> : st.code}
                  </div>
                  
                  {/* Step label */}
                  <span className={`text-[10px] font-mono tracking-wider font-semibold uppercase mt-2 text-center whitespace-nowrap block max-w-[90px] truncate ${
                    isActive ? "text-slate-900 dark:text-slate-50 font-bold" : "text-slate-400 dark:text-slate-500"
                  }`}>
                    {st.stage.replace(" Validation", "").replace(" Strategy", "")}
                  </span>
                </div>

                {idx < stages.length - 1 && (
                  <div className="flex-1 h-0.5 relative -mt-5 mx-2 min-w-[30px]">
                    <div className="absolute inset-0 bg-slate-100 dark:bg-slate-800" />
                    <div
                      className="absolute inset-0 bg-emerald-500 transition-all duration-500"
                      style={{ width: isCompleted ? "100%" : "0%" }}
                    />
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* Control Board & Gate Rules */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 border-t border-slate-100 dark:border-slate-800 pt-5">
        {/* Gate Objectives */}
        <div className="md:col-span-8 flex flex-col justify-between">
          <div className="space-y-4">
            <div>
              <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-widest block">Active Phase</span>
              <h3 className="font-display font-bold text-slate-900 dark:text-slate-50 text-lg flex items-center space-x-2 mt-0.5">
                <span className="text-slate-400 dark:text-slate-500 font-mono">Stage {currentIdx + 1}:</span>
                <span>{strategy.status}</span>
              </h3>
              <p className="text-xs text-slate-600 dark:text-slate-300 mt-1 max-w-2xl font-sans">
                {stages[currentIdx].desc}. {activeCriteria.objective}
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-wider block mb-2">
                  Quality Gate Exit Standards
                </span>

                <ul className="space-y-1.5">
                  {activeCriteria.requirements.map((req, i) => (
                    <li key={i} className="flex items-center space-x-2 text-xs text-slate-700 dark:text-slate-300">
                      <Lock className="h-3.5 w-3.5 text-slate-400 dark:text-slate-500" />
                      <span>{req}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="bg-slate-50 dark:bg-slate-950 border border-slate-100 dark:border-slate-800/60 p-3 rounded-md">
                <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-wider block mb-1">
                  Active Security Segment
                </span>
                <span className="text-xs font-semibold text-slate-800 dark:text-slate-200 flex items-center space-x-1.5 mt-1">
                  <Shield className="h-3.5 w-3.5 text-slate-600 dark:text-slate-400 animate-pulse" />
                  <span>
                    {currentIdx < 7 ? "RESEARCH VALIDATION LAYER" : "EXECUTION VALIDATION LAYER"}
                  </span>
                </span>
                <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-1.5 leading-relaxed">
                  {currentIdx < 7
                    ? "Strictly client-side or sandboxed trade simulators assessing pure statistical alpha."
                    : "Real-time broker checks, position limits, latency audits, and execution safety rules."}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="md:col-span-4 flex flex-col justify-center border-l border-slate-100 dark:border-slate-800 pl-6 space-y-3">
          {currentIdx < stages.length - 1 ? (
            <button
              onClick={handlePromoteClick}
              disabled={isPromoting}
              className="flex items-center justify-center space-x-2 w-full bg-slate-900 hover:bg-slate-800 dark:bg-slate-100 dark:hover:bg-slate-200 dark:text-slate-900 text-white py-3 px-4 rounded-md text-xs font-mono uppercase tracking-wider transition-colors disabled:opacity-50 shadow cursor-pointer"
              id="pipeline-promote-btn"
            >
              {isPromoting ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  <span>Processing Stage Evidence...</span>
                </>
              ) : (
                <>
                  <Play className="h-4 w-4 text-emerald-400 fill-emerald-400 dark:text-emerald-500 dark:fill-emerald-500" />
                  <span>Promote Strategy Gate</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </>
              )}
            </button>
          ) : (
            <div className="bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800/60 text-emerald-800 dark:text-emerald-300 rounded-md p-3.5 text-center text-xs">
              <CheckCircle2 className="h-6 w-6 text-emerald-600 dark:text-emerald-400 mx-auto mb-1.5" />
              <p className="font-bold">PRODUCTION APPROVED</p>
              <p className="text-[10px] text-emerald-700 dark:text-emerald-400 mt-0.5">Strategy deployed on enterprise execution servers.</p>
            </div>
          )}

          {currentIdx > 0 && (
            <div className="pt-2">
              {!isDemoting ? (
                <button
                  onClick={() => {
                    setDemoteTarget(stages[currentIdx - 1].stage);
                    setIsDemoting(true);
                  }}
                  className="w-full text-center text-xs font-mono text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 py-1.5 border border-transparent hover:border-red-200 dark:hover:border-red-900/30 rounded transition-colors cursor-pointer"
                  id="pipeline-show-demote-btn"
                >
                  [ Trigger Demotion / Revalidation ]
                </button>
              ) : (
                <div className="bg-red-50 dark:bg-red-950/20 border border-red-100 dark:border-red-900/40 rounded-md p-3 space-y-2 text-left">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-mono text-red-600 dark:text-red-400 font-bold uppercase">Demote Strategy</span>
                    <button
                      onClick={() => setIsDemoting(false)}
                      className="text-[9px] font-mono text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 cursor-pointer"
                      id="pipeline-cancel-demote"
                    >
                      Cancel
                    </button>
                  </div>
                  <div>
                    <label className="block text-[9px] font-mono text-slate-500 dark:text-slate-400 uppercase mb-1">Target Stage</label>
                    <select
                      value={demoteTarget}
                      onChange={(e) => setDemoteTarget(e.target.value as ValidationStage)}
                      className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded px-2 py-1 text-xs font-sans text-slate-900 dark:text-slate-100 outline-none cursor-pointer"
                      id="pipeline-demote-stage-select"
                    >
                      {stages.slice(0, currentIdx).map(st => (
                        <option key={st.stage} value={st.stage} className="dark:bg-slate-900 dark:text-slate-100">
                          {st.stage}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-[9px] font-mono text-slate-500 dark:text-slate-400 uppercase mb-1">Audit/Risk Comments</label>
                    <input
                      type="text"
                      placeholder="E.g. Volatility slip threshold exceeded..."
                      value={demoteComments}
                      onChange={(e) => setDemoteComments(e.target.value)}
                      className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded px-2 py-1 text-xs font-sans text-slate-900 dark:text-slate-100 outline-none"
                      id="pipeline-demote-comment-input"
                    />
                  </div>
                  <button
                    onClick={handleDemoteClick}
                    disabled={!demoteComments.trim() || isPromoting}
                    className="w-full bg-red-600 hover:bg-red-700 text-white py-1.5 rounded text-[10px] font-mono uppercase tracking-wider disabled:opacity-50 cursor-pointer"
                    id="pipeline-confirm-demote-btn"
                  >
                    Confirm Demotion
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
