import React, { useEffect, useState } from "react";
import { Activity, ClipboardCheck, FileClock, ShieldAlert, Siren, Workflow } from "lucide-react";
import { useSocket } from "../context/SocketContext.js";
import type { IncidentRecord, ReportDetail, ReportSummary, RegistryStrategy } from "../types.js";
import { MetricCard, Panel, StatusChip, formatTime, formatValue, toneFromStatus } from "./opsShared.js";
import { ReportViewer } from "./ReportViewer.js";

function latestReportList(latest: Record<string, ReportSummary>): ReportSummary[] {
  return Object.values(latest || {}).sort((left, right) => String(right.generated_at || right.created_at || "").localeCompare(String(left.generated_at || left.created_at || "")));
}

export function OverviewDashboard() {
  const { session, live, svos, acknowledgeIncident, getReport } = useSocket();
  const [selectedReportId, setSelectedReportId] = useState("");
  const [selectedReport, setSelectedReport] = useState<ReportDetail | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState("");
  const [incidentMessage, setIncidentMessage] = useState("");
  const [selectedStrategy, setSelectedStrategy] = useState("");

  const latestReports = latestReportList(svos.data?.latestReports.latest || {});
  const incidents = (svos.data?.smo.recent_incidents || []) as IncidentRecord[];
  const registryStrategies = svos.data?.registry.strategies || [];
  const currentStrategyName = String(svos.data?.overview.current_strategy || svos.data?.governance.current_strategy || "");
  const activeStrategy = registryStrategies.find((item) => item.strategy === (selectedStrategy || currentStrategyName)) || registryStrategies[0];

  useEffect(() => {
    if (!selectedStrategy && currentStrategyName) {
      setSelectedStrategy(currentStrategyName);
    }
  }, [currentStrategyName, selectedStrategy]);

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

  if ((svos.loading || live.loading) && (!svos.data || !live.data)) {
    return <div className="rounded-[26px] border border-white/10 bg-slate-950/70 p-8 text-sm text-slate-300">Loading dashboard readiness, incident, and package state.</div>;
  }

  if (!svos.data || !live.data) {
    return <div className="rounded-[26px] border border-rose-400/20 bg-rose-400/10 p-8 text-sm text-rose-100">Overview data is unavailable. The dashboard is keeping the missing state explicit instead of filling assumptions.</div>;
  }

  const readiness = svos.data.readiness;
  const productionReadiness = (readiness.production_readiness as Record<string, unknown> | undefined)?.status;
  const testing = (readiness.testing as Record<string, unknown> | undefined)?.status;
  const quality = (readiness.quality as Record<string, unknown> | undefined)?.status;
  const persistence = (readiness.persistence as Record<string, unknown> | undefined)?.status;
  const readinessGates = [
    { label: "Infrastructure", value: svos.data.productionHealth?.status || "Unavailable" },
    { label: "Research", value: svos.data.governance.strategy_status || "Unavailable" },
    { label: "SVOS", value: svos.data.governance.approval_status || "Unavailable" },
    { label: "Dashboard", value: svos.data.smo.monitoring_status || "Unavailable" },
    { label: "Demo", value: productionReadiness || "Unavailable" },
    { label: "30-Day Stable Demo", value: testing || "Unavailable" },
    { label: "Production Qualification", value: quality || "Unavailable" },
    { label: "Operational Persistence", value: persistence || "Unavailable" },
  ];

  return (
    <div className="space-y-6">
      {incidentMessage ? <div className="rounded-2xl border border-emerald-300/20 bg-emerald-300/10 px-4 py-3 text-sm text-emerald-100">{incidentMessage}</div> : null}

      <div className="grid gap-4 lg:grid-cols-4">
        <MetricCard label="Recommendation" value={String(svos.data.latestReports.recommendation_badge || svos.data.smo.recommendation_badge || "REVIEW")} accent="text-amber-100" detail="Latest report badge" />
        <MetricCard label="Unacked Incidents" value={String(svos.data.smo.unacknowledged_incident_count || 0)} accent={(svos.data.smo.unacknowledged_incident_count || 0) > 0 ? "text-rose-200" : "text-emerald-200"} detail="Operational inbox" />
        <MetricCard label="Live Equity" value={formatValue(live.data.overview.equity)} accent="text-white" detail={`Broker ${live.data.broker_status.broker_connection || "UNKNOWN"}`} />
        <MetricCard label="Current Strategy" value={currentStrategyName || "Unavailable"} accent="text-sky-100" detail={`${svos.data.registry.strategy_count} registry entries`} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <Panel title="Readiness Gates" subtitle="Demo-first progression composed from readiness, governance, and production health.">
          <div className="grid gap-3 md:grid-cols-2">
            {readinessGates.map((gate) => (
              <div key={gate.label} className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm text-slate-300">{gate.label}</p>
                  <StatusChip label={String(gate.value)} tone={toneFromStatus(gate.value)} />
                </div>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Control State" subtitle="The overview keeps destructive readiness blockers obvious.">
          <div className="space-y-3">
            <ControlRow icon={ShieldAlert} label="Emergency Stop" value={String((svos.data.rgm.emergency_stop as Record<string, unknown> | undefined)?.active ? "ACTIVE" : "CLEAR")} />
            <ControlRow icon={Activity} label="Broker Connection" value={live.data.broker_status.broker_connection || "UNKNOWN"} />
            <ControlRow icon={Workflow} label="Monitoring" value={String(svos.data.smo.monitoring_status || "Unavailable")} />
            <ControlRow icon={ClipboardCheck} label="Risk Qualification" value={String(svos.data.rgm.qualification_status || "Unavailable")} />
            <ControlRow icon={FileClock} label="Latest Reports" value={String(Object.keys(svos.data.latestReports.latest || {}).length)} />
          </div>
        </Panel>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <Panel title="Approved Package Verification" subtitle="Release and manifest facts from the strategy registry.">
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <select
              value={activeStrategy?.strategy || ""}
              onChange={(event) => setSelectedStrategy(event.target.value)}
              className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-white outline-none"
            >
              {registryStrategies.map((strategy) => (
                <option key={strategy.strategy} value={strategy.strategy}>
                  {strategy.strategy}
                </option>
              ))}
            </select>
            {activeStrategy ? <StatusChip label={activeStrategy.current_stage || "Unknown"} tone={toneFromStatus(activeStrategy.current_stage)} /> : null}
          </div>
          {activeStrategy ? <PackageVerificationCard strategy={activeStrategy} /> : <p className="text-sm text-slate-400">No registry strategies are available yet.</p>}
        </Panel>

        <Panel title="Deployment Timeline" subtitle="Most recent deployment requests and their current status.">
          <div className="space-y-3">
            {svos.data.deployments.slice(0, 8).map((deployment) => (
              <div key={deployment.deployment_id} className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-semibold text-white">{deployment.strategy} {deployment.version}</p>
                    <p className="mt-1 text-xs text-slate-400">{formatTime(deployment.requested_at)} by {deployment.actor || "unknown actor"}</p>
                  </div>
                  <StatusChip label={deployment.status || "unknown"} tone={toneFromStatus(deployment.status)} />
                </div>
                <p className="mt-3 text-sm text-slate-300">{deployment.notes || "No release note provided."}</p>
              </div>
            ))}
            {!svos.data.deployments.length ? <p className="text-sm text-slate-400">No deployment history has been recorded yet.</p> : null}
          </div>
        </Panel>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <Panel title="Operational Report Center" subtitle="Open the latest readiness, risk, and system reports inline.">
          <div className="space-y-3">
            {latestReports.map((report) => {
              const reportId = String(report.report_id || report.id || "");
              return (
                <button
                  key={reportId}
                  onClick={() => setSelectedReportId(reportId)}
                  className={`w-full rounded-2xl border px-4 py-3 text-left transition ${selectedReportId === reportId ? "border-sky-300/30 bg-sky-300/10" : "border-white/8 bg-white/[0.04] hover:bg-white/[0.08]"}`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold text-white">{report.title || report.report_type || reportId}</p>
                      <p className="mt-1 text-xs text-slate-400">{formatTime(report.generated_at || report.created_at)}</p>
                    </div>
                    <StatusChip label={String(report.report_type || "report")} tone="sky" />
                  </div>
                </button>
              );
            })}
            {!latestReports.length ? <p className="text-sm text-slate-400">No latest report entries are available yet.</p> : null}
          </div>
        </Panel>

        <ReportViewer report={selectedReport} loading={reportLoading} error={reportError} emptyMessage="Choose a report from the report center to inspect the generated evidence." />
      </div>

      <Panel title="Incident Inbox" subtitle="Recent incidents from `/api/smo`, with role-gated acknowledgement.">
        <div className="grid gap-4 lg:grid-cols-2">
          {incidents.map((incident, index) => {
            const incidentId = String(incident.incident_id || incident.id || `incident-${index}`);
            return (
              <div key={incidentId} className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold text-white">{String(incident.title || incident.summary || incident.message || incidentId)}</p>
                    <p className="mt-1 text-xs text-slate-400">{formatTime(incident.created_at || incident.timestamp)}</p>
                  </div>
                  <StatusChip label={String(incident.severity || incident.status || "incident")} tone={toneFromStatus(incident.severity || incident.status)} />
                </div>
                <p className="mt-3 text-sm text-slate-300">{String(incident.message || incident.summary || "No additional incident detail was returned.")}</p>
                {session.data?.permitted_actions.includes("incidents:ack") ? (
                  <button
                    onClick={async () => {
                      const result = await acknowledgeIncident(incidentId);
                      setIncidentMessage(result.ok ? `Acknowledged ${incidentId}.` : result.error || "Incident acknowledgement failed.");
                    }}
                    className="mt-4 rounded-full border border-white/10 px-4 py-2 text-sm font-semibold text-white"
                  >
                    Acknowledge
                  </button>
                ) : (
                  <div className="mt-4 text-xs text-slate-500">Incident acknowledgement requires `incident_operator` or `admin`.</div>
                )}
              </div>
            );
          })}
          {!incidents.length ? (
            <div className="rounded-2xl border border-emerald-300/20 bg-emerald-300/10 p-4 text-sm text-emerald-100">
              No recent incidents were returned by the backend.
            </div>
          ) : null}
        </div>
      </Panel>
    </div>
  );
}

function ControlRow({ icon: Icon, label, value }: { icon: React.ComponentType<{ className?: string }>; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.04] px-4 py-3">
      <span className="inline-flex items-center gap-2 text-sm text-slate-300">
        <Icon className="h-4 w-4" />
        {label}
      </span>
      <StatusChip label={value} tone={toneFromStatus(value)} />
    </div>
  );
}

function PackageVerificationCard({ strategy }: { strategy: RegistryStrategy }) {
  const release = strategy.release || {};
  const manifest = strategy.manifest || {};

  return (
    <div className="space-y-3">
      <div className="grid gap-3 md:grid-cols-2">
        <MetricCard label="Latest Version" value={String(strategy.latest_version || "Unavailable")} accent="text-white" />
        <MetricCard label="Evidence Count" value={String(strategy.evidence_count || 0)} accent="text-emerald-200" />
        <MetricCard label="Deployments" value={String(strategy.deployments.length)} accent="text-sky-200" />
        <MetricCard label="Rollbacks" value={String(strategy.rollbacks.length)} accent={strategy.rollbacks.length ? "text-amber-100" : "text-emerald-200"} />
      </div>
      <div className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
        <p className="text-sm font-semibold text-white">Release metadata</p>
        <div className="mt-3 grid gap-2 text-sm text-slate-300">
          <p>Deployment target: {formatValue(release.deployment_target, 0)}</p>
          <p>Approved by: {formatValue(release.approved_by, 0)}</p>
          <p>Manifest hash: {formatValue(manifest.package_hash, 0)}</p>
          <p>Supported brokers: {strategy.supported_brokers.length ? strategy.supported_brokers.join(", ") : "Unavailable"}</p>
          <p>Supported symbols: {strategy.supported_symbols.length ? strategy.supported_symbols.join(", ") : "Unavailable"}</p>
        </div>
      </div>
    </div>
  );
}
