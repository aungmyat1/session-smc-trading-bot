import React from "react";
import { useSocket } from "../context/SocketContext.js";
import { MetricCard, Panel, StatusChip, formatTime, formatValue, toneFromStatus } from "./opsShared.js";

export function HealthDashboard() {
  const { live, svos } = useSocket();

  if ((live.loading || svos.loading) && (!live.data || !svos.data)) {
    return <div className="rounded-[26px] border border-white/10 bg-slate-950/70 p-8 text-sm text-slate-300">Loading health, monitoring, and control-plane telemetry.</div>;
  }

  if (!live.data || !svos.data) {
    return <div className="rounded-[26px] border border-rose-400/20 bg-rose-400/10 p-8 text-sm text-rose-100">Health telemetry is unavailable right now.</div>;
  }

  const productionPolicy = (svos.data.productionHealth?.policy as Record<string, unknown> | undefined) || {};
  const heartbeat = (svos.data.productionHealth?.heartbeat as Record<string, unknown> | undefined) || {};
  const runnerStatus = (svos.data.smo.runner_status as Record<string, unknown> | undefined) || {};
  const databaseStatus = (svos.data.smo.database_status as Record<string, unknown> | undefined) || {};
  const executionStatus = (svos.data.smo.execution_status as Record<string, unknown> | undefined) || {};
  const riskStatus = (svos.data.smo.risk_status as Record<string, unknown> | undefined) || {};
  const recentAudit = svos.data.smo.recent_audit || [];

  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-4">
        <MetricCard label="Monitoring" value={String(svos.data.smo.monitoring_status || "Unavailable")} accent="text-white" />
        <MetricCard label="Production Health" value={String(svos.data.productionHealth?.status || "Unavailable")} accent={toneFromStatus(svos.data.productionHealth?.status) === "rose" ? "text-rose-200" : "text-emerald-200"} />
        <MetricCard label="Heartbeat Age" value={formatValue(heartbeat.age_seconds)} accent="text-amber-100" detail={`Max ${formatValue(heartbeat.max_age_seconds)} sec`} />
        <MetricCard label="Emergency Stop" value={String(live.data.system.emergency_stop.active ? "ACTIVE" : "CLEAR")} accent={live.data.system.emergency_stop.active ? "text-rose-200" : "text-emerald-200"} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <Panel title="Runtime Health" subtitle="Live broker and execution plane status.">
          <div className="grid gap-3 md:grid-cols-2">
            <HealthRow label="Broker Connection" value={live.data.broker_status.broker_connection || "Unavailable"} />
            <HealthRow label="Connection Quality" value={live.data.broker_status.connection_quality || "Unavailable"} />
            <HealthRow label="MT5 Status" value={live.data.broker_status.mt5_status || "Unavailable"} />
            <HealthRow label="MetaAPI Status" value={live.data.broker_status.metaapi_status || "Unavailable"} />
            <HealthRow label="Broker Response" value={live.data.execution_monitor.broker_response || "Unavailable"} />
            <HealthRow label="Last Heartbeat" value={formatTime(live.data.broker_status.last_heartbeat)} />
          </div>
        </Panel>

        <Panel title="Policy Guardrails" subtitle="Production observability state and environment policy.">
          <div className="grid gap-3 md:grid-cols-2">
            <HealthRow label="Live Trading" value={String(productionPolicy.live_trading)} />
            <HealthRow label="Demo Only" value={String(productionPolicy.demo_only)} />
            <HealthRow label="Policy Status" value={String(productionPolicy.status || "Unavailable")} />
            <HealthRow label="Heartbeat Status" value={String(heartbeat.status || "Unavailable")} />
            <HealthRow label="Heartbeat Source" value={String(heartbeat.component || "Unavailable")} />
            <HealthRow label="Recorded At" value={formatTime(heartbeat.timestamp)} />
          </div>
        </Panel>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <Panel title="Service Health Matrix" subtitle="Control-plane subsystem summaries from `/api/smo`.">
          <div className="space-y-3">
            <ServiceCard label="Runner" payload={runnerStatus} />
            <ServiceCard label="Database" payload={databaseStatus} />
            <ServiceCard label="Execution" payload={executionStatus} />
            <ServiceCard label="Risk" payload={riskStatus} />
          </div>
        </Panel>

        <Panel title="Readiness Policy Matrix" subtitle="Cross-check the dashboard, research, and production gates in one place.">
          <div className="grid gap-3 md:grid-cols-2">
            <HealthRow label="Risk Status" value={String(svos.data.rgm.risk_status || "Unavailable")} />
            <HealthRow label="Qualification" value={String(svos.data.rgm.qualification_status || "Unavailable")} />
            <HealthRow label="Recovery Status" value={String(svos.data.rgm.recovery_status || "Unavailable")} />
            <HealthRow label="Execution Mode" value={String(svos.data.rgm.execution_mode_status || "Unavailable")} />
            <HealthRow label="Governance" value={String(svos.data.governance.approval_status || "Unavailable")} />
            <HealthRow label="Recommendation Badge" value={String(svos.data.latestReports.recommendation_badge || "Unavailable")} />
          </div>
        </Panel>
      </div>

      <Panel title="Audit Timeline" subtitle="Recent audit and control events for operational revalidation.">
        <div className="space-y-3">
          {recentAudit.slice(0, 12).map((entry, index) => (
            <div key={`${String(entry.timestamp || entry.occurred_at || index)}`} className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-semibold text-white">{String(entry.action || entry.title || "audit_event")}</p>
                  <p className="mt-1 text-xs text-slate-400">{formatTime(entry.timestamp || entry.occurred_at)}</p>
                </div>
                <StatusChip label={String(entry.status || "recorded")} tone={toneFromStatus(entry.status)} />
              </div>
              <p className="mt-3 text-sm text-slate-300">{String(entry.reason || entry.message || entry.summary || "No additional audit detail was included.")}</p>
            </div>
          ))}
          {!recentAudit.length ? <p className="text-sm text-slate-400">No recent audit entries were returned.</p> : null}
        </div>
      </Panel>
    </div>
  );
}

function HealthRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{label}</p>
      <div className="mt-2">
        <StatusChip label={value} tone={toneFromStatus(value)} />
      </div>
    </div>
  );
}

function ServiceCard({ label, payload }: { label: string; payload: Record<string, unknown> }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="font-semibold text-white">{label}</p>
        <StatusChip label={String(payload.status || payload.state || "Unavailable")} tone={toneFromStatus(payload.status || payload.state)} />
      </div>
      <div className="mt-3 grid gap-2 text-sm text-slate-300">
        {Object.entries(payload).slice(0, 5).map(([key, value]) => (
          <p key={key}>
            {key}: {formatValue(typeof value === "object" ? JSON.stringify(value) : value, 0)}
          </p>
        ))}
      </div>
    </div>
  );
}
