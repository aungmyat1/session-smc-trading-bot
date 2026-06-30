/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
import { AuditReport, StrategyRules, LogicalDefect } from "../types";
import { AlertTriangle, CheckCircle, Shield, List, Cpu, Settings, RefreshCw } from "lucide-react";

interface AuditReportViewProps {
  auditReport?: AuditReport;
  rules: StrategyRules;
  onApplyFix?: (defectId: string) => Promise<void>;
}

export default function AuditReportView({ auditReport, rules, onApplyFix }: AuditReportViewProps) {
  if (!auditReport) {
    return (
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-8 text-center text-slate-500 dark:text-slate-400 transition-colors duration-200">
        <Shield className="h-10 w-10 text-slate-400 dark:text-slate-500 mx-auto mb-3" />
        <p className="font-semibold text-sm text-slate-850 dark:text-slate-200">No Audit Evidence Generated</p>
        <p className="text-xs text-slate-500 dark:text-slate-450 mt-1">Please promote your strategy to the Strategy Audit stage to invoke the logical verifier.</p>
      </div>
    );
  }

  const getSeverityStyles = (severity: string) => {
    switch (severity) {
      case "high":
        return "bg-red-50 dark:bg-red-950/20 border-red-200 dark:border-red-900/40 text-red-900 dark:text-red-400 icon-red";
      case "medium":
        return "bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-900/40 text-amber-900 dark:text-amber-400 icon-amber";
      case "low":
      default:
        return "bg-blue-50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-900/40 text-blue-900 dark:text-blue-400 icon-blue";
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      {/* Rules Spec Panel */}
      <div className="lg:col-span-4 space-y-6">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm transition-colors duration-200">
          <h3 className="font-display font-semibold text-slate-900 dark:text-slate-100 text-sm mb-3 flex items-center space-x-2">
            <List className="h-4 w-4 text-slate-600 dark:text-slate-400" />
            <span>Active Strategy Spec</span>
          </h3>

          <div className="space-y-4 text-xs font-sans">
            <div>
              <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-wider block mb-1">Target Asset</span>
              <span className="font-bold text-slate-800 dark:text-slate-200">{rules.assetClass} — {rules.symbol} ({rules.timeframe})</span>
            </div>

            <div>
              <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-wider block mb-1.5">Parameters Binding</span>
              <div className="bg-slate-50 dark:bg-slate-950 border border-slate-100 dark:border-slate-850 rounded p-3 font-mono text-[10px] space-y-1.5 text-slate-700 dark:text-slate-300 transition-colors">
                {Object.entries(rules.parameters).map(([key, val]) => (
                  <div key={key} className="flex justify-between border-b border-slate-100 dark:border-slate-850 pb-1 last:border-0 last:pb-0">
                    <span className="text-slate-500 dark:text-slate-450">{key}:</span>
                    <span className="font-semibold text-slate-900 dark:text-slate-100">{String(val)}</span>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-wider block mb-1.5">Risk Controls</span>
              <div className="bg-slate-50 dark:bg-slate-950 border border-slate-100 dark:border-slate-850 rounded p-3 font-mono text-[10px] space-y-1.5 text-slate-700 dark:text-slate-300 transition-colors">
                <div className="flex justify-between border-b border-slate-100 dark:border-slate-850 pb-1">
                  <span>Stop Loss:</span>
                  <span className="font-semibold text-red-600 dark:text-red-400">{rules.riskRules.stopLossPct}%</span>
                </div>
                <div className="flex justify-between border-b border-slate-100 dark:border-slate-850 pb-1">
                  <span>Take Profit:</span>
                  <span className="font-semibold text-emerald-600 dark:text-emerald-400">{rules.riskRules.takeProfitPct}%</span>
                </div>
                <div className="flex justify-between border-b border-slate-100 dark:border-slate-850 pb-1">
                  <span>Max Position Size:</span>
                  <span className="font-semibold text-slate-900 dark:text-slate-100">{rules.riskRules.maxPositionSizePct}%</span>
                </div>
                <div className="flex justify-between">
                  <span>Daily Loss Limit:</span>
                  <span className="font-semibold text-red-700 dark:text-red-400">{rules.riskRules.dailyLossLimitPct}%</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Audit Findings Panel */}
      <div className="lg:col-span-8 space-y-6">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm transition-colors duration-200">
          <div className="flex justify-between items-center border-b border-slate-100 dark:border-slate-850 pb-3 mb-4">
            <div>
              <h3 className="font-display font-semibold text-slate-900 dark:text-slate-100 text-sm flex items-center space-x-2">
                <Cpu className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                <span>Compiler Logical Defects & Diagnostics</span>
              </h3>
              <p className="text-[10px] text-slate-500 dark:text-slate-400 font-sans mt-0.5">Audited at {new Date(auditReport.checkedAt).toLocaleString()}</p>
            </div>
            <div className="text-right">
              <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500 block uppercase">Completeness Rating</span>
              <span className={`text-base font-mono font-bold ${auditReport.score >= 80 ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"}`}>
                {auditReport.score}/100
              </span>
            </div>
          </div>

          {auditReport.logicalDefects.length === 0 ? (
            <div className="bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-100 dark:border-emerald-900/30 rounded-lg p-5 text-emerald-900 dark:text-emerald-300 transition-colors">
              <div className="flex items-start space-x-3">
                <CheckCircle className="h-5 w-5 text-emerald-600 dark:text-emerald-400 mt-0.5 shrink-0" />
                <div>
                  <p className="font-semibold text-xs font-mono uppercase tracking-wider text-emerald-800 dark:text-emerald-350">Verification Succeeded</p>
                  <p className="text-xs text-slate-600 dark:text-slate-350 mt-1 font-sans">
                    Zero logical deficits, ambiguities, or rule contradictions were identified in the strategy's specifications. The rules are fully closed, internally consistent, and safe to execute in simulation.
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {auditReport.logicalDefects.map((defect) => (
                <div
                  key={defect.id}
                  className={`border rounded-lg p-4 text-xs transition-colors ${getSeverityStyles(defect.severity)}`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start space-x-3">
                      <AlertTriangle className="h-4.5 w-4.5 mt-0.5 shrink-0" />
                      <div>
                        <p className="font-bold flex items-center space-x-1.5">
                          <span className="font-mono text-[10px] bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 px-1 py-0.5 uppercase rounded text-slate-800 dark:text-slate-200">
                            {defect.type.replace("_", " ")}
                          </span>
                          <span className="font-display text-sm text-slate-900 dark:text-slate-100">{defect.title}</span>
                        </p>
                        <p className="mt-1 text-slate-700 dark:text-slate-300 leading-relaxed font-sans">{defect.description}</p>
                        <p className="mt-1.5 text-[10px] text-slate-500 dark:text-slate-400 font-mono italic">Affected Segment: "{defect.affectedRule}"</p>
                      </div>
                    </div>

                    {onApplyFix && (
                      <button
                        onClick={() => onApplyFix(defect.id)}
                        className="text-[9px] font-mono uppercase bg-slate-900 dark:bg-slate-100 hover:bg-slate-800 dark:hover:bg-slate-200 text-white dark:text-slate-900 px-2.5 py-1 rounded border border-slate-950 dark:border-slate-50 flex items-center space-x-1 shrink-0 cursor-pointer"
                        id={`apply-fix-${defect.id}`}
                      >
                        <RefreshCw className="h-3 w-3 animate-pulse" />
                        <span>AI Fix</span>
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Auditor Recommendations */}
        {auditReport.recommendations && auditReport.recommendations.length > 0 && (
          <div className="bg-slate-950 text-slate-100 rounded-lg p-5 shadow-inner border border-slate-900">
            <h4 className="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider mb-2.5 flex items-center space-x-1.5">
              <Settings className="h-3.5 w-3.5 text-slate-400 animate-spin" style={{ animationDuration: "12s" }} />
              <span>Auditor Recommendations</span>
            </h4>
            <ul className="space-y-1.5 text-xs text-slate-300 font-sans list-decimal list-inside leading-relaxed">
              {auditReport.recommendations.map((rec, idx) => (
                <li key={idx} className="marker:text-slate-500">{rec}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
