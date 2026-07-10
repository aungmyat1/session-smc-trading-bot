/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Demo Validation Mode panel (2026-07-06, Production Candidate Advancement).
 * Read-only view over dashboard/status_server.py's /api/validation/* routes
 * (execution/validation_session.py + execution/validation_metrics.py). Uses
 * the existing authenticatedFetch()/OperatorLogin session — no new auth, no
 * new socket channel, no direct broker access (this dashboard process never
 * talks to MT5 — see dashboard/live_dashboard_service.py's docstring).
 */

import React, { useEffect, useState, useCallback } from "react";
import { useSocket } from "../context/SocketContext.js";
import { ShieldCheck, Activity, RotateCcw, AlertTriangle, RefreshCw } from "lucide-react";

interface ValidationSession {
  session_id: string;
  operator: string;
  broker: string;
  account: string;
  software_version: string;
  git_commit: string;
  config_hash: string;
  status: string;
  started_at: string | null;
  ended_at: string | null;
}

interface LifecycleStats {
  trade_count: number;
  stage_count: number;
  failed_stage_count: number;
  success_rate: number | null;
}

interface StageLatency {
  count: number;
  avg_ms: number;
  max_ms: number;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
}

interface RecoveryEvent {
  runtime_id: string;
  severity: string;
  state: Record<string, unknown>;
  created_at: string;
}

export const ValidationDashboard: React.FC = () => {
  const { authenticatedFetch } = useSocket();
  const [session, setSession] = useState<ValidationSession | null>(null);
  const [lifecycle, setLifecycle] = useState<LifecycleStats | null>(null);
  const [latency, setLatency] = useState<Record<string, StageLatency>>({});
  const [recovery, setRecovery] = useState<RecoveryEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const sessionRes = await authenticatedFetch("/api/validation/session");
      const sessionJson = await sessionRes.json();
      const activeSession: ValidationSession | null = sessionJson.session;
      setSession(activeSession);

      if (activeSession) {
        const [lifecycleRes, latencyRes] = await Promise.all([
          authenticatedFetch(`/api/validation/lifecycle?session_id=${encodeURIComponent(activeSession.session_id)}`),
          authenticatedFetch(`/api/validation/latency?session_id=${encodeURIComponent(activeSession.session_id)}`),
        ]);
        const lifecycleJson = await lifecycleRes.json();
        const latencyJson = await latencyRes.json();
        setLifecycle(lifecycleJson.lifecycle);
        setLatency(latencyJson.latency || {});
      } else {
        setLifecycle(null);
        setLatency({});
      }

      const recoveryRes = await authenticatedFetch("/api/validation/recovery?limit=10");
      const recoveryJson = await recoveryRes.json();
      setRecovery(recoveryJson.recovery_events || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load validation data");
    } finally {
      setLoading(false);
    }
  }, [authenticatedFetch]);

  useEffect(() => {
    load();
    const timer = setInterval(load, 15000);
    return () => clearInterval(timer);
  }, [load]);

  if (loading) {
    return (
      <div className="w-full bg-zinc-900 border border-zinc-800/80 rounded-xl p-6 flex items-center justify-center gap-2 text-zinc-400 font-mono text-xs">
        <RefreshCw className="w-4 h-4 animate-spin" /> Loading validation session...
      </div>
    );
  }

  return (
    <div className="w-full flex flex-col gap-4 font-mono text-xs">
      {/* Validation Mode banner */}
      <div className="w-full bg-amber-500/10 border border-amber-500/30 rounded-xl p-3 flex items-center gap-2 text-amber-300">
        <ShieldCheck className="w-4 h-4" />
        <span className="font-bold uppercase tracking-wider text-[11px]">Demo Validation Mode</span>
        <span className="text-zinc-400">— real MT5 demo broker, real execution pipeline, capped size/trades</span>
      </div>

      {error && (
        <div className="w-full bg-rose-500/10 border border-rose-500/30 rounded-xl p-3 flex items-center gap-2 text-rose-300">
          <AlertTriangle className="w-4 h-4" /> {error}
        </div>
      )}

      {!session ? (
        <div className="w-full bg-zinc-900 border border-zinc-800/80 rounded-xl p-6 text-center text-zinc-500">
          No active validation session. Start the runner with <code>--mode demo_validation</code> to begin one.
        </div>
      ) : (
        <>
          {/* Session info */}
          <div className="w-full bg-zinc-900 border border-zinc-800/80 rounded-xl p-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Field label="Session" value={session.session_id} />
            <Field label="Status" value={session.status} />
            <Field label="Operator" value={session.operator} />
            <Field label="Broker" value={session.broker} />
            <Field label="Account" value={session.account} />
            <Field label="Version" value={session.software_version} />
            <Field label="Commit" value={session.git_commit.slice(0, 10)} />
            <Field label="Started" value={session.started_at ? new Date(session.started_at).toLocaleString() : "—"} />
          </div>

          {/* Lifecycle stats */}
          {lifecycle && (
            <div className="w-full bg-zinc-900 border border-zinc-800/80 rounded-xl p-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
              <Field label="Trades" value={String(lifecycle.trade_count)} />
              <Field label="Stage rows" value={String(lifecycle.stage_count)} />
              <Field label="Failed stages" value={String(lifecycle.failed_stage_count)} />
              <Field
                label="Success rate"
                value={lifecycle.success_rate !== null ? `${(lifecycle.success_rate * 100).toFixed(1)}%` : "n/a"}
              />
            </div>
          )}

          {/* Latency table */}
          <div className="w-full bg-zinc-900 border border-zinc-800/80 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3 text-zinc-300 font-bold uppercase tracking-wider text-[11px]">
              <Activity className="w-3.5 h-3.5" /> Stage Latency (ms)
            </div>
            {Object.keys(latency).length === 0 ? (
              <div className="text-zinc-500">No timed stages recorded yet.</div>
            ) : (
              <table className="w-full text-left">
                <thead>
                  <tr className="text-zinc-500 text-[10px] uppercase">
                    <th className="pb-1">Stage</th>
                    <th className="pb-1">Count</th>
                    <th className="pb-1">Avg</th>
                    <th className="pb-1">Max</th>
                    <th className="pb-1">P50</th>
                    <th className="pb-1">P95</th>
                    <th className="pb-1">P99</th>
                  </tr>
                </thead>
                <tbody>
                  {(Object.entries(latency) as [string, StageLatency][]).map(([stage, stats]) => (
                    <tr key={stage} className="border-t border-zinc-800/60 text-zinc-300">
                      <td className="py-1 font-semibold">{stage}</td>
                      <td>{stats.count}</td>
                      <td>{stats.avg_ms}</td>
                      <td>{stats.max_ms}</td>
                      <td>{stats.p50_ms}</td>
                      <td>{stats.p95_ms}</td>
                      <td>{stats.p99_ms}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Recovery history */}
          <div className="w-full bg-zinc-900 border border-zinc-800/80 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3 text-zinc-300 font-bold uppercase tracking-wider text-[11px]">
              <RotateCcw className="w-3.5 h-3.5" /> Recovery History
            </div>
            {recovery.length === 0 ? (
              <div className="text-zinc-500">No recovery events recorded.</div>
            ) : (
              <ul className="flex flex-col gap-1.5">
                {recovery.map((event, idx) => (
                  <li key={idx} className="flex items-center gap-2 text-zinc-400">
                    <span
                      className={`w-1.5 h-1.5 rounded-full ${event.severity === "warning" ? "bg-amber-400" : "bg-emerald-400"}`}
                    />
                    <span className="text-zinc-300">{new Date(event.created_at).toLocaleString()}</span>
                    <span>runtime={event.runtime_id}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  );
};

const Field: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="flex flex-col gap-0.5">
    <span className="text-zinc-500 text-[10px] uppercase tracking-wider">{label}</span>
    <span className="text-zinc-200 font-semibold truncate">{value}</span>
  </div>
);
