/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from "react";
import { ExecutionSafetyReport } from "../types";
import { ShieldAlert, CheckCircle2, AlertTriangle, AlertOctagon, HelpCircle, HardDrive, RefreshCw } from "lucide-react";

interface ExecutionSafetyViewProps {
  safetyReport?: ExecutionSafetyReport;
}

export default function ExecutionSafetyView({ safetyReport }: ExecutionSafetyViewProps) {
  const [killSwitchActive, setKillSwitchActive] = useState(false);
  const [bypassing, setBypassing] = useState(false);

  if (!safetyReport) {
    return (
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-8 text-center text-slate-500 dark:text-slate-400 transition-colors duration-200">
        <ShieldAlert className="h-10 w-10 text-slate-400 dark:text-slate-500 mx-auto mb-3" />
        <p className="font-semibold text-sm text-slate-800 dark:text-slate-200">No Operational Safety Evidence</p>
        <p className="text-xs text-slate-500 dark:text-slate-450 mt-1">Please promote your strategy to the Execution Validation stage to audit infrastructure safety boundaries.</p>
      </div>
    );
  }

  const triggerKillSwitch = () => {
    setBypassing(true);
    setTimeout(() => {
      setKillSwitchActive(prev => !prev);
      setBypassing(false);
    }, 1200);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "PASSED":
        return <CheckCircle2 className="h-5 w-5 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />;
      case "WARNING":
        return <AlertTriangle className="h-5 w-5 text-amber-500 dark:text-amber-400 shrink-0 mt-0.5" />;
      case "FAILED":
      default:
        return <AlertOctagon className="h-5 w-5 text-red-600 dark:text-red-400 shrink-0 mt-0.5" />;
    }
  };

  const getStatusStyles = (status: string) => {
    switch (status) {
      case "PASSED":
        return "bg-emerald-50/50 dark:bg-emerald-950/10 border-emerald-100 dark:border-emerald-900/30 text-slate-800 dark:text-slate-200";
      case "WARNING":
        return "bg-amber-50/50 dark:bg-amber-950/10 border-amber-100 dark:border-amber-900/30 text-slate-800 dark:text-slate-200";
      case "FAILED":
      default:
        return "bg-red-50/50 dark:bg-red-950/10 border-red-100 dark:border-red-900/30 text-slate-900 dark:text-slate-100";
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      {/* Safety Checks List */}
      <div className="lg:col-span-8 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm space-y-4 transition-colors duration-200">
        <div>
          <h3 className="font-display font-semibold text-slate-900 dark:text-slate-100 text-sm flex items-center space-x-1.5">
            <HardDrive className="h-4.5 w-4.5 text-slate-600 dark:text-slate-400" />
            <span>Infrastructure Integrity & Risk Audits</span>
          </h3>
          <p className="text-[10px] text-slate-500 dark:text-slate-400 font-sans mt-0.5">
            Verified risk circuit breakers on the hardware & broker connection layer (EVF)
          </p>
        </div>

        <div className="space-y-3 font-sans">
          {safetyReport.safetyChecks.map((check, idx) => (
            <div
              key={idx}
              className={`border rounded-lg p-4 flex items-start justify-between gap-4 transition-all ${getStatusStyles(check.status)}`}
            >
              <div className="flex items-start space-x-3">
                {getStatusIcon(check.status)}
                <div>
                  <h4 className="font-bold text-xs text-slate-900 dark:text-slate-100 leading-tight">{check.ruleName}</h4>
                  <p className="text-[11px] text-slate-600 dark:text-slate-350 mt-1 leading-relaxed">{check.description}</p>
                </div>
              </div>

              <div className="text-right font-mono text-[10px] shrink-0">
                <span className="text-slate-400 dark:text-slate-500 block uppercase">Observed</span>
                <span className="font-bold text-slate-900 dark:text-slate-100 block">{check.actualValue}</span>
                <span className="text-[9px] text-slate-400 dark:text-slate-500 block mt-1 uppercase">Threshold {check.thresholdValue}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Operational Controls Sidebar */}
      <div className="lg:col-span-4 space-y-6">
        {/* Risk Score */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm text-center transition-colors duration-200">
          <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-wider block">Operational Safety Score</span>
          <span className="text-4xl font-mono font-bold block text-slate-900 dark:text-slate-100 tracking-tight mt-1.5">
            {safetyReport.signalIntegrityScore}/100
          </span>
          <div className="mt-3 inline-flex items-center space-x-1.5 px-2.5 py-1 text-[10px] font-mono font-bold bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-900/30 text-emerald-800 dark:text-emerald-450 rounded">
            <CheckCircle2 className="h-3 w-3 text-emerald-600 dark:text-emerald-400" />
            <span>EXCEEDS COMPLIANCE BASELINE</span>
          </div>
          <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-3 font-sans leading-relaxed">
            Measures connection stability, latency overhead, and order-queue verification against SEC/FINRA market access guidelines.
          </p>
        </div>

        {/* Emergency Kill Switch */}
        <div className={`border rounded-lg p-5 shadow-lg transition-all duration-500 ${
          killSwitchActive
            ? "bg-red-950 border-red-800 text-red-200"
            : "bg-slate-950 border-slate-900 text-slate-200"
        }`}>
          <div className="flex justify-between items-center mb-4 border-b pb-2.5 border-slate-800/60">
            <h3 className="font-display font-bold text-xs uppercase tracking-wider text-white">Emergency Circuit Breaker</h3>
            <span className={`h-2 w-2 rounded-full ${killSwitchActive ? "bg-red-500 animate-ping" : "bg-emerald-500"}`} />
          </div>

          <p className="text-[11px] font-sans leading-relaxed text-slate-400">
            {killSwitchActive
              ? "CIRCUIT BREAKER ENGAGED. All active trading orders purged immediately. Broker gateway connection severed. Emergency hold in effect."
              : "Active guard ready. Pressing this button will simulate immediate capital containment procedures, canceling all orders and severing connection buffers."}
          </p>

          <button
            onClick={triggerKillSwitch}
            disabled={bypassing}
            className={`w-full py-3 rounded-md text-xs font-mono uppercase tracking-wider flex items-center justify-center space-x-2 transition-all mt-4 border ${
              killSwitchActive
                ? "bg-white border-white text-red-950 font-bold hover:bg-slate-100"
                : "bg-red-600 border-red-700 text-white font-bold hover:bg-red-500 hover:scale-[1.01] shadow-lg shadow-red-950/20"
            }`}
            id="safety-kill-switch-btn"
          >
            {bypassing ? (
              <>
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                <span>Transmitting Override Signals...</span>
              </>
            ) : killSwitchActive ? (
              <span>Restore Broker Buffer Connectivity</span>
            ) : (
              <span>Trigger Manual Kill Switch</span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
