/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
import { LivePipeline, SMCStatus } from "../types.js";
import { CheckCircle2, XCircle, AlertCircle, Play, Sparkles } from "lucide-react";

interface Props {
  pipeline: LivePipeline;
}

export const PipelineGrid: React.FC<Props> = ({ pipeline }) => {
  const getStatusStyle = (status: SMCStatus) => {
    switch (status) {
      case SMCStatus.PASSED:
        return "bg-emerald-500/10 border-emerald-500/30 text-emerald-400 shadow-md shadow-emerald-500/5";
      case SMCStatus.WAITING:
        return "bg-zinc-950/40 border-zinc-800/80 text-zinc-500 hover:border-zinc-700/60";
      case SMCStatus.FAILED:
        return "bg-rose-500/10 border-rose-500/30 text-rose-400";
      case SMCStatus.BLOCKED:
        return "bg-amber-500/10 border-amber-500/30 text-amber-400";
      default:
        return "bg-zinc-900 border-zinc-800 text-zinc-500";
    }
  };

  const getStatusIcon = (status: SMCStatus) => {
    switch (status) {
      case SMCStatus.PASSED:
        return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />;
      case SMCStatus.WAITING:
        return (
          <span className="relative flex h-2 w-2 shrink-0">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-zinc-500 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-zinc-500"></span>
          </span>
        );
      case SMCStatus.FAILED:
        return <XCircle className="w-3.5 h-3.5 text-rose-400 shrink-0" />;
      case SMCStatus.BLOCKED:
        return <AlertCircle className="w-3.5 h-3.5 text-amber-400 shrink-0" />;
      default:
        return null;
    }
  };

  const stagesList = [
    { key: "htfBias", label: "HTF Bias" },
    { key: "liquiditySweep", label: "Liquidity Sweep" },
    { key: "choch", label: "CHoCH Breaker" },
    { key: "bos", label: "BOS Close" },
    { key: "orderBlock", label: "Order Block" },
    { key: "fvg", label: "Fair Value Gap" },
    { key: "confluence", label: "Confluence Zone" },
    { key: "killZone", label: "Kill Zone Limit" },
    { key: "spread", label: "Spread Check" },
    { key: "riskCheck", label: "Risk check" },
    { key: "positionSize", label: "Position Size" },
    { key: "ready", label: "READY SIGNAL" }
  ];

  // Calculate Overall Signal Quality Score based on how many have passed
  const passedCount = (Object.values(pipeline) as any[]).filter((p) => p?.status === SMCStatus.PASSED).length;
  const totalCount = Object.keys(pipeline).length;
  const qualityScore = Math.min(100, Math.floor((passedCount / totalCount) * 100));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
      {/* Live Pipeline Flow Card (Takes 3 columns on large layout) */}
      <div className="lg:col-span-3 bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-lg flex flex-col gap-3">
        <div className="flex items-center justify-between border-b border-zinc-800/60 pb-2.5">
          <div className="flex items-center gap-2">
            <Play className="w-4 h-4 text-emerald-400" />
            <h3 className="font-sans font-semibold text-zinc-200 text-sm">Live Strategy Pipeline Sequence</h3>
          </div>
          <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest font-bold">Execution Pipeline Flow</span>
        </div>

        {/* Chevron Grid Map */}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2.5">
          {stagesList.map((stage, idx) => {
            const stateData = pipeline[stage.key as keyof LivePipeline];
            const status = stateData ? stateData.status : SMCStatus.WAITING;
            const reason = stateData ? stateData.reason : "Syncing...";

            return (
              <div
                key={stage.key}
                className={`relative flex flex-col p-3 rounded-xl border transition-all duration-300 ${getStatusStyle(status)}`}
              >
                {/* Numeric Index Badge */}
                <span className="absolute top-1.5 right-2 font-mono text-[9px] text-zinc-600 font-extrabold">
                  {(idx + 1).toString().padStart(2, "0")}
                </span>

                <div className="flex items-center gap-2 mb-1.5">
                  {getStatusIcon(status)}
                  <span className="font-sans font-bold text-xs text-zinc-200 tracking-tight">{stage.label}</span>
                </div>

                <p className="font-sans text-[10px] text-zinc-400 leading-tight line-clamp-2" title={reason}>
                  {reason}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Checklist Card & Signal Confidence Meter (Takes 1 column) */}
      <div className="bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-lg flex flex-col justify-between gap-3">
        <div className="flex items-center justify-between border-b border-zinc-800/60 pb-2.5">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-emerald-400" />
            <h3 className="font-sans font-semibold text-zinc-200 text-sm">Signal Checklist</h3>
          </div>
        </div>

        {/* List items with ticks/crosses */}
        <div className="space-y-1.5 font-mono text-[11px] text-zinc-400 flex-1 py-1">
          {stagesList.slice(0, 9).map((stage) => {
            const stateData = pipeline[stage.key as keyof LivePipeline];
            const isPassed = stateData?.status === SMCStatus.PASSED;
            return (
              <div key={stage.key} className="flex items-center justify-between">
                <span className="text-zinc-500">{stage.label}</span>
                <span className={isPassed ? "text-emerald-400 font-bold" : "text-zinc-600"}>
                  {isPassed ? "[✓ PASSED]" : "[WAITING]"}
                </span>
              </div>
            );
          })}
        </div>

        {/* Quality Score Progress meter */}
        <div className="border-t border-zinc-800/60 pt-3 mt-1.5 flex flex-col items-center">
          <div className="relative flex items-center justify-center w-20 h-20">
            {/* Round radial gauge using SVG */}
            <svg className="w-full h-full transform -rotate-90">
              <circle
                cx="40"
                cy="40"
                r="34"
                stroke="#1f1f22"
                strokeWidth="5"
                fill="transparent"
              />
              <circle
                cx="40"
                cy="40"
                r="34"
                stroke={qualityScore > 75 ? "#10b981" : qualityScore > 35 ? "#f59e0b" : "#64748b"}
                strokeWidth="5"
                fill="transparent"
                strokeDasharray={`${2 * Math.PI * 34}`}
                strokeDashoffset={`${2 * Math.PI * 34 * (1 - qualityScore / 100)}`}
                className="transition-all duration-500"
              />
            </svg>
            <div className="absolute flex flex-col items-center">
              <span className="font-mono text-base font-bold text-white">{qualityScore}%</span>
              <span className="font-sans text-[8px] text-zinc-500 font-bold uppercase tracking-widest">Quality</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
