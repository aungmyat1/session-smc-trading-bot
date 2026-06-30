/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from "react";
import { ProductionApprovalReport, GovernanceRecord, Strategy } from "../types";
import { Shield, Award, CheckCircle2, FileDown, Database, ClipboardCheck, ArrowRight, Sparkles } from "lucide-react";

interface GovernanceViewProps {
  strategy: Strategy;
}

export default function GovernanceView({ strategy }: GovernanceViewProps) {
  const [downloadingCert, setDownloadingCert] = useState(false);

  const handleDownloadCert = () => {
    setDownloadingCert(true);
    setTimeout(() => {
      setDownloadingCert(false);
      
      // Simulate file download
      const element = document.createElement("a");
      const file = new Blob([
        `=================================================================\n`,
        `         STRATEGY DEPLOYMENT VALIDATION CERTIFICATE              \n`,
        `=================================================================\n`,
        `Strategy Name : ${strategy.name}\n`,
        `Strategy ID   : ${strategy.id}\n`,
        `Version       : ${strategy.version}\n`,
        `Compiled Hash : ${strategy.evidence.productionApproval?.governanceHash || 'N/A'}\n`,
        `Certificate ID: ${strategy.evidence.productionApproval?.certificateId || 'N/A'}\n`,
        `Risk Cap Limit: $${(strategy.evidence.productionApproval?.riskCapLimitUsd || 0).toLocaleString()}\n`,
        `Date Approved : ${strategy.evidence.productionApproval?.approvedAt ? new Date(strategy.evidence.productionApproval.approvedAt).toLocaleDateString() : 'N/A'}\n`,
        `=================================================================\n`,
        `This strategy has successfully completed and passed all 11 stages\n`,
        `of the SVOS Institutional Strategy Validation Pipeline, satisfying\n`,
        `all logical audits, statistical, robustness, and execution safety\n`,
        `gate thresholds. Deploy authorized. PMG Group.\n`
      ], { type: 'text/plain' });
      element.href = URL.createObjectURL(file);
      element.download = `${strategy.name.replace(/\s+/g, '_')}_validation_certificate.txt`;
      document.body.appendChild(element);
      element.click();
      document.body.removeChild(element);
    }, 1000);
  };

  const productionApproval = strategy.evidence.productionApproval;

  return (
    <div className="space-y-6">
      {/* 1. Signed Strategy Certificate (If Approved) */}
      {productionApproval && (
        <div className="bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900 border border-slate-900 text-white rounded-lg p-6 relative overflow-hidden shadow-xl">
          {/* Background overlay accent */}
          <div className="absolute right-0 top-0 opacity-5 pointer-events-none translate-x-12 -translate-y-12 scale-150">
            <Award className="h-64 w-64" />
          </div>

          <div className="flex flex-col sm:flex-row justify-between items-start gap-4 border-b border-slate-800 pb-5 mb-5 relative">
            <div>
              <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 text-[9px] font-mono font-bold bg-emerald-950 text-emerald-400 border border-emerald-900 rounded uppercase">
                <Sparkles className="h-3 w-3 mr-1" />
                verifiable deployment certificate
              </span>
              <h3 className="font-display font-bold text-lg mt-2 tracking-tight">
                Institutional Validation Approved
              </h3>
              <p className="text-[10px] text-slate-400 font-mono mt-1">
                CERTIFICATE ID: {productionApproval.certificateId} // HASH: {productionApproval.governanceHash.slice(0, 16)}...
              </p>
            </div>

            <button
              onClick={handleDownloadCert}
              disabled={downloadingCert}
              className="bg-white hover:bg-slate-100 text-slate-950 font-mono text-xs uppercase px-4 py-2 rounded border border-white flex items-center justify-center space-x-1.5 transition-colors shrink-0 disabled:opacity-50"
              id="gov-download-cert-btn"
            >
              {downloadingCert ? (
                <>
                  <div className="h-3.5 w-3.5 border-2 border-slate-950 border-t-transparent animate-spin rounded-full" />
                  <span>Signing Ledger...</span>
                </>
              ) : (
                <>
                  <FileDown className="h-4 w-4" />
                  <span>Download Certificate</span>
                </>
              )}
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-12 gap-6 mb-6">
            <div className="md:col-span-8 grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-mono">
              <div className="bg-slate-900/40 border border-slate-800 p-3 rounded-md">
                <span className="text-slate-500 block uppercase text-[9px]">Strategy Entity</span>
                <span className="font-bold text-white block mt-0.5">{strategy.name}</span>
                <span className="text-[9px] text-slate-500 block mt-1">VERSION {strategy.version}</span>
              </div>

              <div className="bg-slate-900/40 border border-slate-800 p-3 rounded-md">
                <span className="text-slate-500 block uppercase text-[9px]">Authorized Capital Cap</span>
                <span className="font-bold text-white block mt-0.5">${productionApproval.riskCapLimitUsd.toLocaleString()} USD</span>
                <span className="text-[9px] text-emerald-500 block mt-1 uppercase font-bold">Approved on live gate</span>
              </div>
            </div>

            {/* Approver signatures */}
            <div className="md:col-span-4 space-y-3 font-mono text-[10px]">
              <span className="text-slate-500 block uppercase tracking-wider">Verifiable Board Sign-Offs</span>
              {productionApproval.signoffs.map((sig, i) => (
                <div key={i} className="bg-slate-900/60 border border-slate-800 p-3 rounded-md space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-300">{sig.role}</span>
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                  </div>
                  <div className="text-slate-400">
                    <span>Signed by: </span>
                    <span className="text-white font-semibold italic">"{sig.approver}"</span>
                  </div>
                  <span className="text-slate-500 text-[8px] block">{new Date(sig.signedAt).toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 2. Immutable Ledger Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 shadow-sm transition-colors duration-200">
        <div className="flex justify-between items-center border-b border-slate-100 dark:border-slate-800 pb-3 mb-4">
          <div>
            <h3 className="font-display font-semibold text-slate-900 dark:text-slate-100 text-sm flex items-center space-x-2">
              <Database className="h-4 w-4 text-slate-600 dark:text-slate-400" />
              <span>Immutable Strategy Validation Ledger</span>
            </h3>
            <p className="text-[10px] text-slate-500 dark:text-slate-400 font-sans mt-0.5">
              Cryptographically simulated record of all strategic promotions, audits, and safety transitions.
            </p>
          </div>
        </div>

        <div className="overflow-x-auto dark-scrollbar max-h-96">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-100 dark:border-slate-800 text-[10px] font-mono uppercase text-slate-400 dark:text-slate-500 tracking-wider">
                <th className="pb-2">TX ID</th>
                <th className="pb-2">Timestamp</th>
                <th className="pb-2">Actor</th>
                <th className="pb-2">Action</th>
                <th className="pb-2">Transition Gate</th>
                <th className="pb-2">Ledger SHA Hash</th>
                <th className="pb-2 max-w-xs">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50 dark:divide-slate-800/50 font-mono text-[10px] text-slate-700 dark:text-slate-300">
              {strategy.auditLog.map((record) => (
                <tr key={record.id} className="hover:bg-slate-50 dark:hover:bg-slate-850/30 transition-colors">
                  <td className="py-3 font-bold text-slate-900 dark:text-slate-100">{record.id}</td>
                  <td className="py-3 text-slate-400 dark:text-slate-500">{new Date(record.timestamp).toLocaleString()}</td>
                  <td className="py-3 text-slate-800 dark:text-slate-200">{record.actor}</td>
                  <td className="py-3">
                    <span className={`px-1.5 py-0.5 rounded text-[8px] font-bold ${
                      record.action.includes("Create")
                        ? "bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-700"
                        : record.action.includes("Promote")
                        ? "bg-emerald-50 dark:bg-emerald-950/20 text-emerald-800 dark:text-emerald-400 border border-emerald-100 dark:border-emerald-900/30"
                        : "bg-red-50 dark:bg-red-950/20 text-red-800 dark:text-red-400 border border-red-100 dark:border-red-900/30"
                    }`}>
                      {record.action.toUpperCase()}
                    </span>
                  </td>
                  <td className="py-3">
                    <div className="flex items-center space-x-1">
                      <span className="text-slate-400 dark:text-slate-500 truncate max-w-[80px]" title={record.fromStage}>{record.fromStage}</span>
                      {record.fromStage !== "NONE" && <ArrowRight className="h-3 w-3 text-slate-400 shrink-0" />}
                      <span className="font-bold text-slate-900 dark:text-slate-100 truncate max-w-[80px]" title={record.toStage}>{record.toStage}</span>
                    </div>
                  </td>
                  <td className="py-3 text-slate-500 dark:text-slate-450 text-[9px]" title={record.hash}>
                    {record.hash.slice(0, 10)}...
                  </td>
                  <td className="py-3 max-w-xs text-slate-600 dark:text-slate-400 font-sans leading-relaxed">
                    <p className="font-bold text-slate-800 dark:text-slate-200 font-mono text-[9px]">{record.evidenceSummary}</p>
                    <p className="mt-0.5 text-[10px]">{record.details}</p>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
