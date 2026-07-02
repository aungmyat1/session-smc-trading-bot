import React, { useEffect, useState } from "react";
import { CheckCircle2, FileStack, FlaskConical, PackageCheck, RotateCcw, ShieldCheck, TriangleAlert } from "lucide-react";
import { useSocket } from "../context/SocketContext.js";
import type { DeploymentRecord, RegistryStrategy, ReportDetail, StrategySummary } from "../types.js";
import { ReportViewer } from "./ReportViewer.js";

function Panel({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-[26px] border border-white/10 bg-slate-950/70 p-5 shadow-[0_18px_50px_rgba(2,8,16,0.34)]">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-white">{title}</h2>
        {subtitle ? <p className="mt-1 text-sm text-slate-400">{subtitle}</p> : null}
      </div>
      {children}
    </section>
  );
}

function SummaryCard({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
      <p className="text-[11px] uppercase tracking-[0.24em] text-slate-400">{label}</p>
      <p className={`mt-3 text-2xl font-semibold ${tone}`}>{value}</p>
    </div>
  );
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "Unavailable";
  }
  if (typeof value === "number") {
    return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  return String(value);
}

function ActionBanner({ text, danger = false }: { text: string; danger?: boolean }) {
  return (
    <div className={`rounded-2xl border px-4 py-3 text-sm ${danger ? "border-rose-400/20 bg-rose-400/10 text-rose-100" : "border-emerald-300/20 bg-emerald-300/10 text-emerald-100"}`}>
      {text}
    </div>
  );
}

export function SvosResearchDashboard() {
  const {
    svos,
    mutationBlockedReason,
    createDeployment,
    importDeployment,
    preflightDeployment,
    activateDeployment,
    rollbackDeployment,
    reviewReport,
    generateReport,
    getReport,
  } = useSocket();

  const [selectedStrategy, setSelectedStrategy] = useState("");
  const [deploymentNotes, setDeploymentNotes] = useState("");
  const [rollbackIntent, setRollbackIntent] = useState<{ deploymentId: string; toVersion: string; reason: string } | null>(null);
  const [reportType, setReportType] = useState("daily");
  const [actionMessage, setActionMessage] = useState("");
  const [selectedReportId, setSelectedReportId] = useState("");
  const [selectedReport, setSelectedReport] = useState<ReportDetail | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState("");

  if (svos.loading && !svos.data) {
    return (
      <div className="rounded-[26px] border border-white/10 bg-slate-950/70 p-8 text-sm text-slate-300">
        Loading SVOS overview, strategy registry, reports, and deployment history.
      </div>
    );
  }

  if (!svos.data) {
    return (
      <div className="rounded-[26px] border border-rose-400/20 bg-rose-400/10 p-8 text-sm text-rose-100">
        SVOS data is unavailable right now. The dashboard is showing the backend truth instead of placeholder lifecycle states.
      </div>
    );
  }

  const controlsDisabled = Boolean(mutationBlockedReason);
  const strategies = svos.data.strategies;
  const registryStrategies = svos.data.registry.strategies;
  const deployments = svos.data.deployments;
  const currentStrategy = String(svos.data.overview.current_strategy || svos.data.governance.current_strategy || "");
  const chosenStrategy = selectedStrategy || currentStrategy || strategies[0]?.id || "";

  useEffect(() => {
    if (!selectedReportId) {
      setSelectedReport(null);
      setReportError("");
      return;
    }

    let cancelled = false;
    setReportLoading(true);
    setReportError("");
    getReport(selectedReportId)
      .then((payload) => {
        if (!cancelled) {
          setSelectedReport(payload);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setSelectedReport(null);
          setReportError((error as Error).message);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setReportLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [getReport, selectedReportId]);

  async function runAndReport(task: Promise<{ ok: boolean; error?: string }>, success: string) {
    const result = await task;
    setActionMessage(result.ok ? success : result.error || "Action failed.");
  }

  return (
    <div className="space-y-6">
      {actionMessage ? <ActionBanner text={actionMessage} danger={actionMessage.toLowerCase().includes("failed")} /> : null}

      <div className="grid gap-4 lg:grid-cols-4">
        <SummaryCard label="Current Strategy" value={currentStrategy || "Unavailable"} tone="text-white" />
        <SummaryCard label="Registry Strategies" value={String(svos.data.registry.strategy_count)} tone="text-sky-200" />
        <SummaryCard label="Deployments" value={String(svos.data.registry.deployment_count)} tone="text-emerald-200" />
        <SummaryCard label="Production Health" value={formatValue(svos.data.productionHealth?.status || "Unavailable")} tone="text-amber-100" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <Panel title="SVOS Research Inventory" subtitle="Registry, validation stage, and the latest evidence-backed strategy records.">
          <div className="grid gap-4 md:grid-cols-2">
            {strategies.map((strategy) => (
              <StrategyCard
                key={strategy.id}
                strategy={strategy}
                active={chosenStrategy === strategy.id}
                onSelect={() => setSelectedStrategy(strategy.id)}
              />
            ))}
          </div>
        </Panel>

        <Panel title="Readiness and Governance" subtitle="Read-only checkpoints from the existing control plane.">
          <div className="space-y-3 text-sm text-slate-200">
            <StatusRow label="Approval status" value={formatValue(svos.data.governance.approval_status)} />
            <StatusRow label="Current stage" value={formatValue(svos.data.governance.strategy_status)} />
            <StatusRow label="Deployment target" value={formatValue(svos.data.governance.deployment_target)} />
            <StatusRow label="Recommendation badge" value={formatValue(svos.data.overview.recommendation_badge)} />
            <StatusRow label="Production readiness" value={formatValue((svos.data.readiness.production_readiness as Record<string, unknown> | undefined)?.status)} />
            <StatusRow label="Testing" value={formatValue((svos.data.readiness.testing as Record<string, unknown> | undefined)?.status)} />
            <StatusRow label="Quality" value={formatValue((svos.data.readiness.quality as Record<string, unknown> | undefined)?.status)} />
            <StatusRow label="Persistence" value={formatValue((svos.data.readiness.persistence as Record<string, unknown> | undefined)?.status)} />
          </div>

          {svos.data.productionHealth ? (
            <div className="mt-4 rounded-2xl border border-white/8 bg-white/[0.04] p-4 text-sm text-slate-200">
              <p className="font-semibold text-white">Production policy</p>
              <p className="mt-2">Live trading: {formatValue((svos.data.productionHealth.policy as Record<string, unknown> | undefined)?.live_trading)}</p>
              <p className="mt-1">Demo only: {formatValue((svos.data.productionHealth.policy as Record<string, unknown> | undefined)?.demo_only)}</p>
            </div>
          ) : (
            <div className="mt-4 rounded-2xl border border-amber-300/20 bg-amber-300/10 p-4 text-sm text-amber-100">
              Production health endpoint returned a degraded response. The UI keeps showing that explicitly rather than assuming readiness.
            </div>
          )}
        </Panel>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <Panel title="Deployment Controls" subtitle="Validate, import, preflight, activate-disabled, and rollback using the existing API authority.">
          <div className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
            <div className="flex items-center gap-2 text-white">
              <PackageCheck className="h-4 w-4" />
              <h3 className="font-semibold">Create deployment</h3>
            </div>
            <select
              value={chosenStrategy}
              onChange={(event) => setSelectedStrategy(event.target.value)}
              className="mt-3 w-full rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-white outline-none"
            >
              {[...new Set(strategies.map((item) => item.id))].map((strategyId) => (
                <option key={strategyId} value={strategyId}>
                  {strategyId}
                </option>
              ))}
            </select>
            <textarea
              value={deploymentNotes}
              onChange={(event) => setDeploymentNotes(event.target.value)}
              placeholder="Release notes or deployment reason"
              className="mt-3 min-h-24 w-full rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-white outline-none placeholder:text-slate-500"
            />
            <button
              disabled={controlsDisabled || !chosenStrategy}
              onClick={() => runAndReport(createDeployment(chosenStrategy, deploymentNotes), `Deployment created for ${chosenStrategy}.`)}
              className="mt-3 rounded-full bg-emerald-300 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-40"
            >
              Create deployment package
            </button>
          </div>

          <div className="mt-4 space-y-3">
            {deployments.length ? (
              deployments.map((deployment) => (
                <DeploymentCard
                  key={deployment.deployment_id}
                  deployment={deployment}
                  controlsDisabled={controlsDisabled}
                  onImport={() => runAndReport(importDeployment(deployment.deployment_id), `Imported ${deployment.deployment_id}.`)}
                  onPreflight={() => runAndReport(preflightDeployment(deployment.deployment_id), `Preflight completed for ${deployment.deployment_id}.`)}
                  onActivate={() => runAndReport(activateDeployment(deployment.deployment_id), `Activation staging recorded for ${deployment.deployment_id}.`)}
                  onRollback={() => setRollbackIntent({ deploymentId: deployment.deployment_id, toVersion: deployment.version, reason: "" })}
                />
              ))
            ) : (
              <ActionBanner text="No deployment records exist yet. Create one from an approved or review-ready strategy package." />
            )}
          </div>

          {rollbackIntent ? (
            <div className="mt-4 rounded-2xl border border-rose-400/20 bg-rose-400/10 p-4 text-sm text-rose-100">
              <div className="flex items-center gap-2 font-semibold">
                <RotateCcw className="h-4 w-4" />
                Rollback request
              </div>
              <input
                value={rollbackIntent.toVersion}
                onChange={(event) => setRollbackIntent({ ...rollbackIntent, toVersion: event.target.value })}
                placeholder="Target version"
                className="mt-3 w-full rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-white outline-none"
              />
              <textarea
                value={rollbackIntent.reason}
                onChange={(event) => setRollbackIntent({ ...rollbackIntent, reason: event.target.value })}
                placeholder="Reason required for rollback audit trail"
                className="mt-3 min-h-20 w-full rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-white outline-none"
              />
              <div className="mt-3 flex gap-2">
                <button
                  disabled={!rollbackIntent.reason.trim() || !rollbackIntent.toVersion.trim()}
                  onClick={async () => {
                    const current = rollbackIntent;
                    const result = await rollbackDeployment(current.deploymentId, current.toVersion, current.reason);
                    setActionMessage(result.ok ? `Rollback deployment created from ${current.deploymentId}.` : result.error || "Rollback failed.");
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
        </Panel>

        <Panel title="Reports and Evidence" subtitle="Report review and generation are gated by backend role checks.">
          <div className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
            <div className="flex items-center gap-2 text-white">
              <FileStack className="h-4 w-4" />
              <h3 className="font-semibold">Generate report</h3>
            </div>
            <select
              value={reportType}
              onChange={(event) => setReportType(event.target.value)}
              className="mt-3 w-full rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-white outline-none"
            >
              <option value="daily">daily</option>
              <option value="risk">risk</option>
              <option value="system-health">system-health</option>
              <option value="production-preflight">production-preflight</option>
              <option value="live-readiness">live-readiness</option>
              <option value="all">all</option>
            </select>
            <button
              disabled={controlsDisabled}
              onClick={() => runAndReport(generateReport(reportType), `Requested report generation for ${reportType}.`)}
              className="mt-3 rounded-full bg-sky-300 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-40"
            >
              Generate
            </button>
          </div>

          <div className="mt-4 space-y-3">
            {(svos.data.reports.reports || []).slice(0, 10).map((report, index) => {
              const reportId = String(report.id || report.report_id || report.path || `report-${index}`);
              return (
                <div key={reportId} className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-semibold text-white">{String(report.title || reportId)}</p>
                      <p className="mt-1 text-xs text-slate-400">{String(report.generated_at || report.created_at || report.path || "Timestamp unavailable")}</p>
                    </div>
                    <button
                      disabled={controlsDisabled}
                      onClick={() => runAndReport(reviewReport(reportId), `Marked ${reportId} as reviewed.`)}
                      className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40"
                    >
                      Mark reviewed
                    </button>
                  </div>
                </div>
              );
            })}

            {!(svos.data.reports.reports || []).length ? (
              <ActionBanner text="No indexed reports were returned from the backend." />
            ) : null}
          </div>
        </Panel>
      </div>

      <Panel title="Strategy Comparison" subtitle="Side-by-side registry comparison for version, evidence, and deployment readiness.">
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-[0.2em] text-slate-400">
              <tr>
                <th className="pb-3">Strategy</th>
                <th className="pb-3">Stage</th>
                <th className="pb-3">Version</th>
                <th className="pb-3">Evidence</th>
                <th className="pb-3">Deployments</th>
                <th className="pb-3">Brokers</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/6 text-slate-200">
              {registryStrategies.map((strategy) => (
                <tr key={strategy.strategy}>
                  <td className="py-3 font-medium text-white">{strategy.strategy}</td>
                  <td className="py-3">{strategy.current_stage || "Unavailable"}</td>
                  <td className="py-3">{strategy.latest_version || "Unavailable"}</td>
                  <td className="py-3">{strategy.evidence_count}</td>
                  <td className="py-3">{strategy.deployments.length}</td>
                  <td className="py-3">{strategy.supported_brokers.join(", ") || "Unavailable"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <Panel title="Validation Report Viewer" subtitle="Open indexed reports directly from the backend report catalog.">
          <div className="space-y-3">
            {(svos.data.reports.reports || []).slice(0, 12).map((report, index) => {
              const reportId = String(report.id || report.report_id || report.path || `report-${index}`);
              const selected = selectedReportId === reportId;
              return (
                <button
                  key={reportId}
                  onClick={() => setSelectedReportId(reportId)}
                  className={`w-full rounded-2xl border px-4 py-3 text-left transition ${selected ? "border-sky-300/30 bg-sky-300/10" : "border-white/8 bg-white/[0.04] hover:bg-white/[0.08]"}`}
                >
                  <p className="font-semibold text-white">{String(report.title || reportId)}</p>
                  <p className="mt-1 text-xs text-slate-400">{String(report.generated_at || report.created_at || report.path || "Timestamp unavailable")}</p>
                </button>
              );
            })}
          </div>
        </Panel>

        <ReportViewer report={selectedReport} loading={reportLoading} error={reportError} emptyMessage="Choose a report to inspect the validation markdown." />
      </div>

      <Panel title="Registry Snapshot" subtitle="Lifecycle inventory composed from `/api/v1/strategy-registry`.">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {registryStrategies.map((strategy) => (
            <RegistryCard key={strategy.strategy} strategy={strategy} />
          ))}
        </div>
      </Panel>

      <div className="rounded-2xl border border-sky-300/15 bg-sky-300/10 px-4 py-3 text-sm text-sky-100">
        <div className="flex items-start gap-3">
          <FlaskConical className="mt-0.5 h-4 w-4 shrink-0" />
          <p>
            This MVP intentionally excludes Gemini parse and explain actions, arbitrary strategy activation, and any path that could enable `LIVE_TRADING`. Deployment staging remains disabled unless external environment policy already authorizes otherwise.
          </p>
        </div>
      </div>
    </div>
  );
}

const StrategyCard: React.FC<{
  strategy: StrategySummary;
  active: boolean;
  onSelect: () => void;
}> = ({
  strategy,
  active,
  onSelect,
}) => {
  return (
    <button
      onClick={onSelect}
      className={`rounded-2xl border p-4 text-left transition ${active ? "border-sky-300/40 bg-sky-300/10" : "border-white/8 bg-white/[0.04] hover:bg-white/[0.08]"}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-white">{strategy.name}</p>
          <p className="mt-1 text-xs text-slate-400">{strategy.status}</p>
        </div>
        {active ? <CheckCircle2 className="h-5 w-5 text-sky-200" /> : null}
      </div>
      <p className="mt-3 line-clamp-3 text-sm text-slate-300">{strategy.description || "No description recorded."}</p>
      <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
        <span>v{strategy.version}</span>
        <span>{strategy.author}</span>
      </div>
    </button>
  );
};

const StatusRow: React.FC<{ label: string; value: string }> = ({ label, value }) => {
  return (
    <div className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.04] px-4 py-3">
      <span className="text-slate-400">{label}</span>
      <span className="font-semibold text-white">{value}</span>
    </div>
  );
};

const DeploymentCard: React.FC<{
  deployment: DeploymentRecord;
  controlsDisabled: boolean;
  onImport: () => void;
  onPreflight: () => void;
  onActivate: () => void;
  onRollback: () => void;
}> = ({
  deployment,
  controlsDisabled,
  onImport,
  onPreflight,
  onActivate,
  onRollback,
}) => {
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="font-semibold text-white">{deployment.strategy} · {deployment.version}</p>
          <p className="mt-1 text-xs text-slate-400">{deployment.deployment_id}</p>
          <p className="mt-2 text-sm text-slate-300">Status: {deployment.status} · Target: {deployment.target}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button disabled={controlsDisabled} onClick={onImport} className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40">
            Import
          </button>
          <button disabled={controlsDisabled} onClick={onPreflight} className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40">
            Preflight
          </button>
          <button disabled={controlsDisabled} onClick={onActivate} className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40">
            Activate disabled
          </button>
          <button disabled={controlsDisabled} onClick={onRollback} className="rounded-full border border-rose-300/30 px-3 py-1.5 text-xs font-semibold text-rose-100 disabled:opacity-40">
            Rollback
          </button>
        </div>
      </div>
    </div>
  );
};

const RegistryCard: React.FC<{ strategy: RegistryStrategy }> = ({ strategy }) => {
  const stage = strategy.current_stage || "Unknown";
  const warning = stage.toUpperCase().includes("BLOCK") || stage.toUpperCase().includes("FAIL");
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-white">{strategy.strategy}</p>
          <p className="mt-1 text-xs text-slate-400">Latest version {strategy.latest_version || "Unavailable"}</p>
        </div>
        {warning ? <TriangleAlert className="h-5 w-5 text-amber-200" /> : <ShieldCheck className="h-5 w-5 text-emerald-200" />}
      </div>
      <div className="mt-3 space-y-1 text-sm text-slate-300">
        <p>Stage: {stage}</p>
        <p>Evidence count: {strategy.evidence_count}</p>
        <p>Transitions: {strategy.transition_count}</p>
        <p>Brokers: {strategy.supported_brokers.join(", ") || "Unavailable"}</p>
      </div>
    </div>
  );
};
