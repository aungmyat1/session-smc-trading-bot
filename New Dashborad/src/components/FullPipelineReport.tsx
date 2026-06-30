/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useCallback, useEffect, useState } from "react";
import { Strategy } from "../types";
import {
  CheckCircle, XCircle, Clock, AlertTriangle, Info,
  ChevronDown, ChevronRight, Loader2, Play, RefreshCw, FileCode
} from "lucide-react";

// ─── Types returned by /pipeline-report ──────────────────────────────────────

interface HardGate {
  name: string;
  passed: boolean;
  message: string;
  hard_gate?: boolean;
  details?: Record<string, unknown>;
}

interface Finding {
  name?: string;
  message?: string;
  type?: string;
  detail?: string;
  blocker?: boolean;
}

interface StageReport {
  stage_num: number;
  stage: string;
  stage_label: string;
  status: "PASS" | "FAIL" | "PENDING";
  score: number;
  promotion_allowed: boolean;
  generated_at: string;
  metrics: Record<string, unknown>;
  findings: Finding[];
  hard_gate_results: HardGate[];
  warnings: string[];
  remediation: string[];
}

interface PipelineReport {
  strategy_id: string;
  strategy_name: string;
  strategy_version: string;
  run_id: string;
  generated_at: string;
  overall_status: string;
  latest_passed_stage: string;
  stages: StageReport[];
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmt(val: unknown): string {
  if (val === null || val === undefined) return "—";
  if (typeof val === "boolean") return val ? "Yes" : "No";
  if (typeof val === "number") {
    return Number.isInteger(val) ? String(val) : val.toFixed(4);
  }
  if (typeof val === "string") return val || "—";
  if (Array.isArray(val)) return val.length === 0 ? "None" : `[${val.length} items]`;
  if (typeof val === "object") return JSON.stringify(val);
  return String(val);
}

function flattenMetrics(
  metrics: Record<string, unknown>,
  prefix = ""
): [string, unknown][] {
  const out: [string, unknown][] = [];
  for (const [k, v] of Object.entries(metrics)) {
    const label = prefix ? `${prefix} → ${k}` : k;
    if (
      v !== null &&
      typeof v === "object" &&
      !Array.isArray(v) &&
      Object.keys(v).length <= 8
    ) {
      // recurse one level
      out.push(...flattenMetrics(v as Record<string, unknown>, label));
    } else if (Array.isArray(v) && v.length === 0) {
      // empty arrays from replay (duplicates, exceptions…) — skip
    } else {
      out.push([label, v]);
    }
  }
  return out;
}

// ─── Status chip ─────────────────────────────────────────────────────────────

function StatusChip({ status }: { status: string }) {
  if (status === "PASS")
    return (
      <span className="flex items-center gap-1 bg-emerald-500 text-white px-2.5 py-0.5 rounded text-[11px] font-mono font-bold">
        <CheckCircle className="h-3 w-3" /> PASS
      </span>
    );
  if (status === "FAIL")
    return (
      <span className="flex items-center gap-1 bg-red-500 text-white px-2.5 py-0.5 rounded text-[11px] font-mono font-bold">
        <XCircle className="h-3 w-3" /> FAIL
      </span>
    );
  return (
    <span className="flex items-center gap-1 bg-slate-400 text-white px-2.5 py-0.5 rounded text-[11px] font-mono font-bold">
      <Clock className="h-3 w-3" /> PENDING
    </span>
  );
}

// ─── Section header ───────────────────────────────────────────────────────────

function SectionHeader({
  num,
  label,
  status,
  score,
  generatedAt,
}: {
  num: number;
  label: string;
  status: string;
  score: number;
  generatedAt: string;
}) {
  const bg =
    status === "PASS"
      ? "bg-slate-800 dark:bg-slate-900"
      : status === "FAIL"
      ? "bg-red-900 dark:bg-red-950"
      : "bg-slate-700 dark:bg-slate-800";

  return (
    <div
      className={`${bg} text-white rounded-t-lg px-5 py-3 flex items-center justify-between border border-slate-700 dark:border-slate-800`}
    >
      <span className="font-mono font-bold text-sm tracking-widest uppercase">
        {num}. {label.toUpperCase()}
      </span>
      <div className="flex items-center gap-3">
        {score > 0 && (
          <span className="font-mono text-xs text-slate-300 dark:text-slate-400">
            Score: <strong className="text-white">{score.toFixed(1)}</strong>
          </span>
        )}
        {generatedAt && (
          <span className="font-mono text-[10px] text-slate-400 hidden sm:block">
            {new Date(generatedAt).toLocaleDateString()}
          </span>
        )}
        <StatusChip status={status} />
      </div>
    </div>
  );
}

// ─── Collapsible section wrapper ──────────────────────────────────────────────

function Collapsible({
  title,
  defaultOpen = true,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-slate-100 dark:border-slate-800 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-2 bg-slate-50 dark:bg-slate-800/60 text-left text-[11px] font-mono font-semibold uppercase tracking-widest text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
      >
        {title}
        {open ? (
          <ChevronDown className="h-3.5 w-3.5" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5" />
        )}
      </button>
      {open && <div className="p-4">{children}</div>}
    </div>
  );
}

// ─── Metrics table ────────────────────────────────────────────────────────────

function MetricsTable({ metrics }: { metrics: Record<string, unknown> }) {
  const flat = flattenMetrics(metrics);
  if (flat.length === 0)
    return (
      <p className="text-xs text-slate-400 dark:text-slate-500 font-mono">
        No metrics recorded.
      </p>
    );
  return (
    <table className="w-full text-xs font-mono">
      <tbody>
        {flat.map(([key, val]) => (
          <tr
            key={key}
            className="border-b border-slate-100 dark:border-slate-800 last:border-0"
          >
            <td className="py-1.5 pr-4 text-slate-500 dark:text-slate-400 capitalize whitespace-nowrap">
              {key.replace(/_/g, " ")}
            </td>
            <td className="py-1.5 font-semibold text-slate-900 dark:text-slate-100 text-right">
              {typeof val === "boolean" ? (
                val ? (
                  <span className="text-emerald-600 dark:text-emerald-400">Yes</span>
                ) : (
                  <span className="text-red-600 dark:text-red-400">No</span>
                )
              ) : (
                fmt(val)
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ─── Hard gate checklist ──────────────────────────────────────────────────────

function HardGates({ gates }: { gates: HardGate[] }) {
  if (gates.length === 0)
    return (
      <p className="text-xs text-slate-400 dark:text-slate-500 font-mono">
        No gate checks recorded.
      </p>
    );
  return (
    <ul className="space-y-2">
      {gates.map((g, i) => (
        <li key={i} className="flex items-start gap-2 text-xs font-mono">
          {g.passed ? (
            <CheckCircle className="h-3.5 w-3.5 text-emerald-500 flex-shrink-0 mt-0.5" />
          ) : (
            <XCircle className="h-3.5 w-3.5 text-red-500 flex-shrink-0 mt-0.5" />
          )}
          <div>
            <span
              className={`font-semibold ${
                g.passed
                  ? "text-slate-800 dark:text-slate-200"
                  : "text-red-700 dark:text-red-400"
              }`}
            >
              {g.name.replace(/_/g, " ")}
            </span>
            {g.message && (
              <span className="text-slate-500 dark:text-slate-400 ml-2">
                — {g.message}
              </span>
            )}
            {g.details && Object.keys(g.details).length > 0 && (
              <div className="mt-0.5 text-[10px] text-slate-400 dark:text-slate-500">
                {Object.entries(g.details)
                  .map(([k, v]) => `${k}: ${fmt(v)}`)
                  .join("  ·  ")}
              </div>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}

// ─── Findings list ────────────────────────────────────────────────────────────

function Findings({ findings }: { findings: Finding[] }) {
  if (findings.length === 0)
    return (
      <p className="text-xs text-slate-400 dark:text-slate-500 font-mono">
        No findings — all checks clean.
      </p>
    );
  return (
    <ul className="space-y-2">
      {findings.map((f, i) => (
        <li
          key={i}
          className={`flex items-start gap-2 text-xs font-mono p-2 rounded border ${
            f.blocker
              ? "bg-red-50 dark:bg-red-950/20 border-red-200 dark:border-red-900/40 text-red-800 dark:text-red-300"
              : "bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-900/40 text-amber-800 dark:text-amber-300"
          }`}
        >
          <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold">
              {f.name ?? f.type ?? "Issue"}
            </span>
            {(f.message ?? f.detail) && (
              <span className="ml-1 font-normal opacity-80">
                — {f.message ?? f.detail}
              </span>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}

// ─── Strategy summary (section 0) ────────────────────────────────────────────

function StrategySummarySection({ strategy, report }: { strategy: Strategy; report: PipelineReport }) {
  const headerBg =
    report.overall_status === "PASS"
      ? "bg-slate-800 dark:bg-slate-900"
      : "bg-slate-700 dark:bg-slate-800";

  return (
    <div>
      <div
        className={`${headerBg} text-white rounded-t-lg px-5 py-3 flex items-center justify-between border border-slate-700 dark:border-slate-800`}
      >
        <span className="font-mono font-bold text-sm tracking-widest uppercase">
          0. New Strategy — Summary
        </span>
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs text-slate-300">
            v{report.strategy_version}
          </span>
          <StatusChip status={report.overall_status || "PENDING"} />
        </div>
      </div>

      <div className="border border-t-0 border-slate-200 dark:border-slate-700 rounded-b-lg bg-white dark:bg-slate-900 p-5 grid grid-cols-1 sm:grid-cols-2 gap-6">
        {/* Left: metadata */}
        <div>
          <p className="text-[10px] font-mono uppercase tracking-widest text-slate-400 dark:text-slate-500 mb-3">
            Strategy Metadata
          </p>
          <table className="w-full text-xs font-mono">
            <tbody>
              {(
                [
                  ["Strategy ID",   strategy.id],
                  ["Strategy Name", strategy.name],
                  ["Version",       strategy.version],
                  ["Run ID",        report.run_id.split("-")[0] + "…"],
                  ["Author",        strategy.author],
                  ["Market",        `${strategy.rules.assetClass} — ${strategy.rules.symbol}`],
                  ["Timeframes",    strategy.rules.timeframe],
                  ["Description",   strategy.description?.slice(0, 80) || "—"],
                ] as [string, string][]
              ).map(([k, v]) => (
                <tr key={k} className="border-b border-slate-100 dark:border-slate-800 last:border-0">
                  <td className="py-1.5 text-slate-500 dark:text-slate-400 pr-3 whitespace-nowrap">{k}</td>
                  <td className="py-1.5 font-semibold text-slate-900 dark:text-slate-100 break-all">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Right: stage overview */}
        <div>
          <p className="text-[10px] font-mono uppercase tracking-widest text-slate-400 dark:text-slate-500 mb-3">
            Stage Overview
          </p>
          <div className="space-y-2">
            {report.stages.map((s) => (
              <div key={s.stage} className="flex items-center gap-3 text-xs font-mono">
                {s.status === "PASS" && <CheckCircle className="h-4 w-4 text-emerald-500 flex-shrink-0" />}
                {s.status === "FAIL" && <XCircle className="h-4 w-4 text-red-500 flex-shrink-0" />}
                {s.status !== "PASS" && s.status !== "FAIL" && (
                  <Clock className="h-4 w-4 text-slate-400 flex-shrink-0" />
                )}
                <span
                  className={`font-semibold ${
                    s.status === "PASS"
                      ? "text-slate-700 dark:text-slate-300"
                      : s.status === "FAIL"
                      ? "text-red-700 dark:text-red-400"
                      : "text-slate-400 dark:text-slate-600"
                  }`}
                >
                  {s.stage_num}. {s.stage_label}
                </span>
                <span className="text-slate-400 dark:text-slate-600 ml-auto">
                  {s.score > 0 ? `${s.score.toFixed(1)}` : "—"}
                </span>
              </div>
            ))}
          </div>

          <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800 flex items-center gap-2 text-[10px] font-mono">
            <span className="text-slate-400 dark:text-slate-500 uppercase tracking-widest">Current Stage:</span>
            <span className="bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800 px-2 py-0.5 rounded font-semibold">
              {strategy.status}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Individual stage section ─────────────────────────────────────────────────

function StageSection({ stage }: { stage: StageReport }) {
  const hasFindings = stage.findings.length > 0;
  const hasWarnings = stage.warnings.length > 0;
  const hasRemediation = stage.remediation.length > 0;

  return (
    <div>
      <SectionHeader
        num={stage.stage_num}
        label={stage.stage_label}
        status={stage.status}
        score={stage.score}
        generatedAt={stage.generated_at}
      />
      <div className="border border-t-0 border-slate-200 dark:border-slate-700 rounded-b-lg bg-white dark:bg-slate-900 p-4 space-y-4">

        {/* Metrics */}
        <Collapsible title={`${stage.stage_label} Metrics`} defaultOpen>
          <MetricsTable metrics={stage.metrics} />
        </Collapsible>

        {/* Hard gates */}
        {stage.hard_gate_results.length > 0 && (
          <Collapsible title="Validation Gates" defaultOpen>
            <HardGates gates={stage.hard_gate_results} />
          </Collapsible>
        )}

        {/* Findings */}
        <Collapsible title={`Findings (${stage.findings.length})`} defaultOpen={hasFindings}>
          <Findings findings={stage.findings} />
        </Collapsible>

        {/* Warnings */}
        {hasWarnings && (
          <Collapsible title={`Warnings (${stage.warnings.length})`} defaultOpen={false}>
            <ul className="space-y-1">
              {stage.warnings.map((w, i) => (
                <li key={i} className="flex items-start gap-2 text-xs font-mono text-amber-700 dark:text-amber-400">
                  <Info className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
                  {typeof w === "string" ? w : JSON.stringify(w)}
                </li>
              ))}
            </ul>
          </Collapsible>
        )}

        {/* Remediation */}
        {hasRemediation && (
          <Collapsible title={`Remediation Actions (${stage.remediation.length})`} defaultOpen={false}>
            <ul className="space-y-1">
              {stage.remediation.map((r, i) => (
                <li key={i} className="flex items-start gap-2 text-xs font-mono text-slate-600 dark:text-slate-400">
                  <ChevronRight className="h-3.5 w-3.5 flex-shrink-0 mt-0.5 text-slate-400" />
                  {typeof r === "string" ? r : JSON.stringify(r)}
                </li>
              ))}
            </ul>
          </Collapsible>
        )}

        {/* Promotion allowed */}
        <div className="flex items-center gap-2 pt-1 text-[10px] font-mono text-slate-400 dark:text-slate-500">
          {stage.promotion_allowed ? (
            <CheckCircle className="h-3 w-3 text-emerald-500" />
          ) : (
            <XCircle className="h-3 w-3 text-red-500" />
          )}
          <span>
            Promotion to next stage:{" "}
            <strong className={stage.promotion_allowed ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}>
              {stage.promotion_allowed ? "ALLOWED" : "BLOCKED"}
            </strong>
          </span>
        </div>
      </div>
    </div>
  );
}

// ─── Final summary table (section last) ──────────────────────────────────────

function FinalSummary({ report, strategy }: { report: PipelineReport; strategy: Strategy }) {
  return (
    <div>
      <div className="bg-slate-900 dark:bg-black text-white rounded-t-lg px-5 py-3 flex items-center justify-between border border-slate-700">
        <span className="font-mono font-bold text-sm tracking-widest uppercase">
          Final Summary — Lifecycle
        </span>
        <StatusChip status={report.overall_status || "PENDING"} />
      </div>
      <div className="border border-t-0 border-slate-200 dark:border-slate-700 rounded-b-lg bg-white dark:bg-slate-900 overflow-x-auto">
        <table className="w-full text-xs font-mono">
          <thead>
            <tr className="bg-slate-50 dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700">
              <th className="text-left px-4 py-2.5 text-slate-500 dark:text-slate-400 font-semibold uppercase tracking-wider">Stage</th>
              <th className="text-center px-4 py-2.5 text-slate-500 dark:text-slate-400 font-semibold uppercase tracking-wider">Score</th>
              <th className="text-center px-4 py-2.5 text-slate-500 dark:text-slate-400 font-semibold uppercase tracking-wider">Status</th>
              <th className="text-center px-4 py-2.5 text-slate-500 dark:text-slate-400 font-semibold uppercase tracking-wider">Promotion</th>
              <th className="text-right px-4 py-2.5 text-slate-500 dark:text-slate-400 font-semibold uppercase tracking-wider">Run Date</th>
            </tr>
          </thead>
          <tbody>
            {report.stages.map((s) => (
              <tr key={s.stage} className="border-b border-slate-100 dark:border-slate-800 last:border-0 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                <td className="px-4 py-2.5 text-slate-700 dark:text-slate-300">
                  <span className="text-slate-400 dark:text-slate-600 mr-2">{s.stage_num}.</span>
                  {s.stage_label}
                </td>
                <td className="px-4 py-2.5 text-center font-semibold text-slate-700 dark:text-slate-300">
                  {s.score > 0 ? s.score.toFixed(1) : "—"}
                </td>
                <td className="px-4 py-2.5 text-center">
                  {s.status === "PASS" && (
                    <span className="text-emerald-600 dark:text-emerald-400 font-bold">PASS</span>
                  )}
                  {s.status === "FAIL" && (
                    <span className="text-red-600 dark:text-red-400 font-bold">FAIL</span>
                  )}
                  {s.status !== "PASS" && s.status !== "FAIL" && (
                    <span className="text-slate-400 dark:text-slate-600">—</span>
                  )}
                </td>
                <td className="px-4 py-2.5 text-center">
                  {s.promotion_allowed ? (
                    <span className="text-emerald-600 dark:text-emerald-400">✓ Allowed</span>
                  ) : (
                    <span className="text-red-500 dark:text-red-400">✗ Blocked</span>
                  )}
                </td>
                <td className="px-4 py-2.5 text-right text-slate-500 dark:text-slate-400">
                  {s.generated_at ? new Date(s.generated_at).toLocaleDateString() : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="px-4 py-4 border-t border-slate-100 dark:border-slate-800 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <span className="text-[10px] font-mono uppercase tracking-widest text-slate-400 dark:text-slate-500">
            Overall Lifecycle Status
          </span>
          <span
            className={`text-sm font-mono font-bold tracking-wide uppercase ${
              report.overall_status === "PASS"
                ? "text-emerald-600 dark:text-emerald-400"
                : report.overall_status === "FAIL"
                ? "text-red-600 dark:text-red-400"
                : "text-amber-600 dark:text-amber-400"
            }`}
          >
            {report.overall_status === "PASS"
              ? "Strategy Pipeline Fully Validated"
              : `Current Stage: ${strategy.status}`}
          </span>
        </div>
      </div>
    </div>
  );
}

// ─── Run Pipeline Panel ───────────────────────────────────────────────────────

function buildDefaultSpec(strategy: Strategy): string {
  const r = strategy.rules;
  const risk = r.riskRules || {};
  const entry = r.entryConditions?.join(" | ") || "Enter on confirmed momentum setup during active killzone";
  const exit = r.exitConditions?.join(" | ") || "Close at take profit or stop loss";
  return [
    `# ${strategy.name}`,
    "",
    `Market: ${r.assetClass || "Forex"}`,
    `Instruments: ${r.symbol || "EURUSD"}`,
    `Timeframe: ${r.timeframe || "M15"}`,
    "Session: London and New York killzones only",
    "Bias: Long only when H1 market structure is bullish with BOS confirmation",
    `Entry Trigger: ${entry}`,
    "Confirmation: Require displacement and FVG or order block retest",
    "Invalidation: Cancel if setup fails within 3 candles or price closes below swept low",
    `Stop Loss: ${risk.stopLossPct ?? 1.0}% from entry`,
    `Take Profit: ${risk.takeProfitPct ?? 2.0}R target`,
    `Risk: ${risk.maxPositionSizePct ?? 0.5}% fixed fractional per trade`,
    `Maximum Daily Loss: ${risk.dailyLossLimitPct ?? 2.0}%`,
    "Maximum Open Positions: 1",
    "Maximum Drawdown: 8%",
    "News Rules: Do not open within 15 minutes of high-impact news",
    "Filters: Require HTF bias, session filter, spread below 1.5 pips",
    `Exit Rules: ${exit}`,
    strategy.description ? `\n# ${strategy.description}` : "",
  ].join("\n").trim();
}

interface RunResult {
  strategy_id: string;
  overall_status: string;
  stages: Array<{ stage: string; status: string; score: number }>;
  report_dir?: string;
  error?: string;
}

function RunPipelinePanel({
  strategy,
  onComplete,
}: {
  strategy: Strategy;
  onComplete: () => void;
}) {
  const [spec, setSpec] = useState(() => buildDefaultSpec(strategy));
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<RunResult | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [showSpec, setShowSpec] = useState(false);

  const handleRun = async () => {
    setRunning(true);
    setRunResult(null);
    setRunError(null);
    try {
      const res = await fetch(
        `/api/new-dashboard/strategies/${strategy.id}/run-pipeline`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ spec }),
        }
      );
      const data = await res.json();
      if (!res.ok) {
        setRunError(data.error || "Pipeline run failed");
      } else {
        setRunResult(data);
        if (data.overall_status === "PASS" || data.stages?.length > 0) {
          setTimeout(onComplete, 800);
        }
      }
    } catch (e: unknown) {
      setRunError(e instanceof Error ? e.message : "Network error");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="bg-indigo-700 dark:bg-indigo-900 text-white px-5 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileCode className="h-4 w-4" />
          <span className="font-mono font-bold text-sm tracking-widest uppercase">
            Run SVOS Pipeline Validation
          </span>
        </div>
        <span className="text-indigo-300 text-[10px] font-mono">
          Synthetic data used for unconfirmed stages
        </span>
      </div>

      <div className="p-5 space-y-4">
        {/* Strategy spec */}
        <div>
          <button
            onClick={() => setShowSpec(!showSpec)}
            className="flex items-center gap-2 text-[11px] font-mono uppercase tracking-widest text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors mb-2"
          >
            {showSpec ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
            Strategy Specification Text (auto-generated from rules — edit if needed)
          </button>
          {showSpec && (
            <textarea
              value={spec}
              onChange={(e) => setSpec(e.target.value)}
              rows={14}
              className="w-full text-[11px] font-mono bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-700 rounded p-3 text-slate-800 dark:text-slate-200 resize-y focus:outline-none focus:ring-1 focus:ring-indigo-500"
              placeholder="Paste or edit strategy specification here…"
            />
          )}
        </div>

        {/* Run result */}
        {runResult && (
          <div
            className={`rounded border p-3 text-xs font-mono space-y-2 ${
              runResult.overall_status === "PASS"
                ? "bg-emerald-50 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300"
                : "bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300"
            }`}
          >
            <div className="flex items-center gap-2 font-semibold">
              {runResult.overall_status === "PASS" ? (
                <CheckCircle className="h-4 w-4" />
              ) : (
                <AlertTriangle className="h-4 w-4" />
              )}
              Pipeline {runResult.overall_status} — loading report…
            </div>
            <div className="flex flex-wrap gap-2 mt-1">
              {runResult.stages.map((s) => (
                <span
                  key={s.stage}
                  className={`px-2 py-0.5 rounded border text-[10px] font-bold ${
                    s.status === "PASS"
                      ? "bg-emerald-100 border-emerald-300 text-emerald-700"
                      : "bg-red-100 border-red-300 text-red-700"
                  }`}
                >
                  {s.stage}: {s.status}
                </span>
              ))}
            </div>
          </div>
        )}

        {runError && (
          <div className="bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800 rounded p-3 text-xs font-mono text-red-800 dark:text-red-300">
            <div className="flex items-center gap-2 font-semibold mb-1">
              <XCircle className="h-4 w-4" /> Pipeline Error
            </div>
            {runError}
          </div>
        )}

        {/* Action buttons */}
        <div className="flex items-center gap-3 pt-1">
          <button
            onClick={handleRun}
            disabled={running || !spec.trim()}
            className={`flex items-center gap-2 px-4 py-2 rounded text-sm font-semibold font-mono transition-colors ${
              running || !spec.trim()
                ? "bg-slate-200 dark:bg-slate-800 text-slate-400 cursor-not-allowed"
                : "bg-indigo-600 hover:bg-indigo-700 text-white cursor-pointer"
            }`}
          >
            {running ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Running Pipeline…
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                Run SVOS Pipeline
              </>
            )}
          </button>
          {running && (
            <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500 animate-pulse">
              Running all 6 stages — audit → replay → backtest → robustness → virtual demo → approval…
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Main export ──────────────────────────────────────────────────────────────

interface FullPipelineReportProps {
  strategy: Strategy;
}

export default function FullPipelineReport({ strategy }: FullPipelineReportProps) {
  const [report, setReport] = useState<PipelineReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showRunPanel, setShowRunPanel] = useState(false);

  const fetchReport = useCallback(() => {
    setLoading(true);
    setError(null);
    fetch(`/api/new-dashboard/strategies/${strategy.id}/pipeline-report`)
      .then((r) => {
        if (!r.ok) throw new Error(`No SVOS pipeline report found for "${strategy.id}"`);
        return r.json();
      })
      .then((data) => {
        setReport(data);
        setLoading(false);
        setShowRunPanel(false);
      })
      .catch((e) => {
        setError(e.message);
        setLoading(false);
      });
  }, [strategy.id]);

  useEffect(() => {
    fetchReport();
  }, [fetchReport]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-48 gap-3 text-slate-500 dark:text-slate-400">
        <Loader2 className="h-6 w-6 animate-spin" />
        <p className="text-xs font-mono uppercase tracking-widest animate-pulse">
          Loading pipeline report…
        </p>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="space-y-4">
        <div className="bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 rounded-lg px-5 py-4 flex items-center gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-500 flex-shrink-0" />
          <div>
            <p className="font-semibold text-sm text-amber-800 dark:text-amber-300">
              No SVOS Pipeline Report Available
            </p>
            <p className="text-xs text-amber-700 dark:text-amber-400 mt-0.5">
              {error ||
                "This strategy has not been run through the SVOS pipeline yet. Use the panel below to generate stage reports."}
            </p>
          </div>
        </div>
        <RunPipelinePanel strategy={strategy} onComplete={fetchReport} />
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      {/* 0. Summary */}
      <StrategySummarySection strategy={strategy} report={report} />

      {/* 1–6: Each SVOS stage */}
      {report.stages.map((stage) => (
        <StageSection key={stage.stage} stage={stage} />
      ))}

      {/* Final lifecycle summary */}
      <FinalSummary report={report} strategy={strategy} />

      {/* Re-run panel */}
      {showRunPanel ? (
        <RunPipelinePanel
          strategy={strategy}
          onComplete={() => { setShowRunPanel(false); fetchReport(); }}
        />
      ) : (
        <div className="flex justify-end">
          <button
            onClick={() => setShowRunPanel(true)}
            className="flex items-center gap-2 px-4 py-2 rounded text-sm font-semibold font-mono bg-indigo-600 hover:bg-indigo-700 text-white transition-colors"
          >
            <RefreshCw className="h-4 w-4" />
            Re-run Pipeline
          </button>
        </div>
      )}
    </div>
  );
}
