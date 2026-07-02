import React, { useEffect, useState } from "react";
import { PackageCheck, RotateCcw, TestTubeDiagonal, Workflow } from "lucide-react";
import { useSocket } from "../context/SocketContext.js";
import type { ReportDetail, StrategyPipelineReport } from "../types.js";
import { MetricCard, Panel, StatusChip, formatTime, formatValue, toneFromStatus } from "./opsShared.js";
import { ReportViewer } from "./ReportViewer.js";

export function PipelineOpsDashboard() {
  const {
    svos,
    mutationBlockedReason,
    createDeployment,
    importDeployment,
    preflightDeployment,
    activateDeployment,
    rollbackDeployment,
    getPipelineReport,
    getReport,
  } = useSocket();

  const [selectedStrategy, setSelectedStrategy] = useState("");
  const [deploymentNotes, setDeploymentNotes] = useState("");
  const [pipelineReport, setPipelineReport] = useState<StrategyPipelineReport | null>(null);
  const [pipelineError, setPipelineError] = useState("");
  const [pipelineLoading, setPipelineLoading] = useState(false);
  const [reportDetail, setReportDetail] = useState<ReportDetail | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [rollbackIntent, setRollbackIntent] = useState<{ deploymentId: string; toVersion: string; reason: string } | null>(null);

  const strategies = svos.data?.strategies || [];
  const controlsDisabled = Boolean(mutationBlockedReason);
  const selectedStrategyId = selectedStrategy || strategies[0]?.id || "";

  useEffect(() => {
    if (!selectedStrategy && strategies[0]?.id) {
      setSelectedStrategy(strategies[0].id);
    }
  }, [selectedStrategy, strategies]);

  useEffect(() => {
    if (!selectedStrategyId) {
      setPipelineReport(null);
      setPipelineError("");
      return;
    }

    let cancelled = false;
    setPipelineLoading(true);
    setPipelineError("");
    getPipelineReport(selectedStrategyId)
      .then((payload) => {
        if (!cancelled) {
          setPipelineReport(payload);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setPipelineReport(null);
          setPipelineError((error as Error).message);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setPipelineLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [getPipelineReport, selectedStrategyId]);

  if (svos.loading && !svos.data) {
    return <div className="rounded-[26px] border border-white/10 bg-slate-950/70 p-8 text-sm text-slate-300">Loading pipeline, deployment, and verification state.</div>;
  }

  if (!svos.data) {
    return <div className="rounded-[26px] border border-rose-400/20 bg-rose-400/10 p-8 text-sm text-rose-100">Pipeline operations data is unavailable right now.</div>;
  }

  async function openLatestSvosReport() {
    const candidate = (svos.data.reports.reports || []).find((item) => item.report_type === "svos-stage" && String(item.path || "").includes(selectedStrategyId));
    if (!candidate?.report_id) {
      setReportError(`No indexed SVOS markdown report was found for ${selectedStrategyId}.`);
      setReportDetail(null);
      return;
    }
    setReportLoading(true);
    setReportError("");
    try {
      const payload = await getReport(candidate.report_id);
      setReportDetail(payload);
    } catch (error) {
      setReportError((error as Error).message);
      setReportDetail(null);
    } finally {
      setReportLoading(false);
    }
  }

  async function runAndReport(task: Promise<{ ok: boolean; error?: string }>, success: string) {
    const result = await task;
    setActionMessage(result.ok ? success : result.error || "Action failed.");
  }

  return (
    <div className="space-y-6">
      {actionMessage ? <div className="rounded-2xl border border-emerald-300/20 bg-emerald-300/10 px-4 py-3 text-sm text-emerald-100">{actionMessage}</div> : null}

      <div className="grid gap-4 lg:grid-cols-4">
        <MetricCard label="Strategies" value={String(svos.data.strategies.length)} accent="text-white" />
        <MetricCard label="Deployments" value={String(svos.data.deployments.length)} accent="text-emerald-200" />
        <MetricCard label="Latest Passed Stage" value={pipelineReport?.latest_passed_stage || "Unavailable"} accent="text-sky-100" />
        <MetricCard label="Pipeline Status" value={pipelineReport?.overall_status || "Unavailable"} accent={toneFromStatus(pipelineReport?.overall_status) === "rose" ? "text-rose-200" : "text-amber-100"} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <Panel title="Pipeline Controller" subtitle="Inspect the latest SVOS run and create deployment packages from the approved strategy set.">
          <div className="space-y-4">
            <select
              value={selectedStrategyId}
              onChange={(event) => setSelectedStrategy(event.target.value)}
              className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-white outline-none"
            >
              {strategies.map((strategy) => (
                <option key={strategy.id} value={strategy.id}>
                  {strategy.id}
                </option>
              ))}
            </select>
            <textarea
              value={deploymentNotes}
              onChange={(event) => setDeploymentNotes(event.target.value)}
              placeholder="Release note, package purpose, or operator context"
              className="min-h-24 w-full rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-white outline-none placeholder:text-slate-500"
            />
            <div className="flex flex-wrap gap-2">
              <button
                disabled={controlsDisabled || !selectedStrategyId}
                onClick={() => runAndReport(createDeployment(selectedStrategyId, deploymentNotes), `Deployment created for ${selectedStrategyId}.`)}
                className="rounded-full bg-emerald-300 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-40"
              >
                Create deployment
              </button>
              <button
                disabled={pipelineLoading || !selectedStrategyId}
                onClick={openLatestSvosReport}
                className="rounded-full border border-white/10 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
              >
                Open latest SVOS report
              </button>
            </div>
            {mutationBlockedReason ? <p className="text-xs text-amber-200">{mutationBlockedReason}</p> : null}
          </div>
        </Panel>

        <Panel title="Validation Run Summary" subtitle="Stage-by-stage view of the selected strategy pipeline.">
          {pipelineLoading ? <p className="text-sm text-slate-300">Loading pipeline report.</p> : null}
          {!pipelineLoading && pipelineError ? <div className="rounded-2xl border border-amber-300/20 bg-amber-300/10 px-4 py-3 text-sm text-amber-100">{pipelineError}</div> : null}
          {!pipelineLoading && !pipelineError && pipelineReport ? (
            <div className="space-y-3">
              {pipelineReport.stages.map((stage) => (
                <div key={stage.stage} className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold text-white">{stage.stage_num}. {stage.stage_label}</p>
                      <p className="mt-1 text-xs text-slate-400">{formatTime(stage.generated_at)}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <StatusChip label={stage.status} tone={toneFromStatus(stage.status)} />
                      <StatusChip label={stage.promotion_allowed ? "Promotion allowed" : "Hold"} tone={stage.promotion_allowed ? "emerald" : "amber"} />
                    </div>
                  </div>
                  <div className="mt-3 grid gap-3 md:grid-cols-4">
                    <MetricCard label="Score" value={formatValue(stage.score)} accent="text-white" />
                    <MetricCard label="Findings" value={String(stage.findings.length)} accent="text-amber-100" />
                    <MetricCard label="Hard Gates" value={String(stage.hard_gate_results.length)} accent="text-sky-100" />
                    <MetricCard label="Warnings" value={String(stage.warnings.length)} accent={stage.warnings.length ? "text-rose-200" : "text-emerald-200"} />
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </Panel>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Panel title="Deployment Timeline Actions" subtitle="Existing backend authority for import, preflight, activate, and rollback.">
          <div className="space-y-3">
            {svos.data.deployments.map((deployment) => (
              <div key={deployment.deployment_id} className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-semibold text-white">{deployment.deployment_id}</p>
                    <p className="mt-1 text-xs text-slate-400">{deployment.strategy} {deployment.version} • {formatTime(deployment.requested_at)}</p>
                  </div>
                  <StatusChip label={deployment.status || "unknown"} tone={toneFromStatus(deployment.status)} />
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <button disabled={controlsDisabled} onClick={() => runAndReport(importDeployment(deployment.deployment_id), `Imported ${deployment.deployment_id}.`)} className="rounded-full border border-white/10 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">Import</button>
                  <button disabled={controlsDisabled} onClick={() => runAndReport(preflightDeployment(deployment.deployment_id), `Preflight completed for ${deployment.deployment_id}.`)} className="rounded-full border border-white/10 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">Preflight</button>
                  <button disabled={controlsDisabled} onClick={() => runAndReport(activateDeployment(deployment.deployment_id), `Activation recorded for ${deployment.deployment_id}.`)} className="rounded-full bg-sky-300 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-40">Activate</button>
                  <button disabled={controlsDisabled} onClick={() => setRollbackIntent({ deploymentId: deployment.deployment_id, toVersion: deployment.version, reason: "" })} className="rounded-full border border-rose-300/30 px-4 py-2 text-sm font-semibold text-rose-100 disabled:opacity-40">Rollback</button>
                </div>
              </div>
            ))}
            {!svos.data.deployments.length ? <p className="text-sm text-slate-400">No deployment records are available.</p> : null}
          </div>
        </Panel>

        <ReportViewer report={reportDetail} loading={reportLoading} error={reportError} emptyMessage="Open the latest SVOS stage report for the selected strategy to inspect the markdown validation output." />
      </div>

      <Panel title="Package Verification Checklist" subtitle="A compact readiness view for demo-first package progression.">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <ChecklistCard icon={PackageCheck} label="Versioned Package" value={String(Boolean(selectedStrategyId))} />
          <ChecklistCard icon={Workflow} label="Pipeline Evidence" value={String(Boolean(pipelineReport?.stages.length))} />
          <ChecklistCard icon={TestTubeDiagonal} label="Preflight Path" value={String(Boolean(svos.data.deployments.length))} />
          <ChecklistCard icon={RotateCcw} label="Rollback Available" value={String(svos.data.deployments.some((item) => item.status?.toLowerCase().includes("rollback")) || svos.data.registry.rollback_count > 0)} />
        </div>
      </Panel>

      {rollbackIntent ? (
        <div className="rounded-2xl border border-rose-400/20 bg-rose-400/10 p-4 text-sm text-rose-100">
          <p className="font-semibold">Confirm rollback for {rollbackIntent.deploymentId}</p>
          <input
            value={rollbackIntent.toVersion}
            onChange={(event) => setRollbackIntent({ ...rollbackIntent, toVersion: event.target.value })}
            placeholder="Target version"
            className="mt-3 w-full rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-white outline-none"
          />
          <textarea
            value={rollbackIntent.reason}
            onChange={(event) => setRollbackIntent({ ...rollbackIntent, reason: event.target.value })}
            placeholder="Rollback reason for the audit trail"
            className="mt-3 min-h-20 w-full rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-white outline-none"
          />
          <div className="mt-3 flex gap-2">
            <button
              disabled={!rollbackIntent.reason.trim() || !rollbackIntent.toVersion.trim()}
              onClick={async () => {
                const current = rollbackIntent;
                const result = await rollbackDeployment(current.deploymentId, current.toVersion, current.reason);
                setActionMessage(result.ok ? `Rollback created from ${current.deploymentId}.` : result.error || "Rollback failed.");
                if (result.ok) {
                  setRollbackIntent(null);
                }
              }}
              className="rounded-full bg-white px-4 py-2 font-semibold text-slate-950 disabled:opacity-40"
            >
              Confirm rollback
            </button>
            <button onClick={() => setRollbackIntent(null)} className="rounded-full border border-white/10 px-4 py-2 font-semibold text-white">
              Cancel
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ChecklistCard({ icon: Icon, label, value }: { icon: React.ComponentType<{ className?: string }>; label: string; value: string }) {
  const passed = value === "true";
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
      <div className="flex items-center gap-2 text-white">
        <Icon className="h-4 w-4" />
        <p className="text-sm font-semibold">{label}</p>
      </div>
      <p className={`mt-3 text-xl font-semibold ${passed ? "text-emerald-200" : "text-amber-100"}`}>{passed ? "Ready" : "Pending"}</p>
    </div>
  );
}
