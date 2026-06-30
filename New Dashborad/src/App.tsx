import React, { useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, Database, FileText, Shield, Workflow } from 'lucide-react';

type StrategyRecord = {
  strategy: string;
  current_stage: string;
  latest_version: string;
  evidence_count: number;
  transition_count: number;
  legacy_status: string;
  manifest?: {
    description?: string;
    symbols?: string[];
    timeframes?: string[];
  };
};

type OverviewPayload = {
  current_strategy: string;
  recommendation_badge: string;
  registry: {
    strategies: StrategyRecord[];
    lifecycle_stages: string[];
  };
  deployment: {
    deployment_readiness: string;
    approved: boolean;
    demo_only: boolean;
    live_trading: boolean;
  };
  monitoring: {
    monitoring_status: string;
    incident_count: number;
  };
  persistence: {
    configured_mode: string;
    effective_mode: string;
    pg_active: boolean;
    authoritative: boolean;
  };
  readiness: {
    production_readiness: {
      release_status?: string;
      mandatory_failures?: string[];
      warnings?: string[];
    };
    stabilization: {
      verdict?: string;
    };
  };
};

type StrategyDetailPayload = {
  record: StrategyRecord;
  evidence: Array<Record<string, unknown>>;
  transitions: Array<Record<string, unknown>>;
  gate_decisions: Array<Record<string, unknown>>;
  approvals: Array<Record<string, unknown>>;
};

type ReportsPayload = {
  reports: Array<{
    report_id: string;
    report_type: string;
    title: string;
    path: string;
    created_at: string;
  }>;
};

const sectionCard =
  'rounded-3xl border border-slate-200 bg-white/90 shadow-[0_24px_80px_rgba(15,23,42,0.08)] backdrop-blur';

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed for ${url}`);
  }
  return response.json();
}

function StatusBadge({ label, tone }: { label: string; tone: 'blue' | 'amber' | 'emerald' | 'slate' | 'rose' }) {
  const tones: Record<'blue' | 'amber' | 'emerald' | 'slate' | 'rose', string> = {
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    amber: 'bg-amber-50 text-amber-700 border-amber-200',
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    slate: 'bg-slate-100 text-slate-700 border-slate-200',
    rose: 'bg-rose-50 text-rose-700 border-rose-200',
  };
  return <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${tones[tone]}`}>{label}</span>;
}

function toneForValue(value: string): 'blue' | 'amber' | 'emerald' | 'slate' | 'rose' {
  const upper = value.toUpperCase();
  if (upper.includes('APPROVED') || upper.includes('PASS') || upper.includes('SAFE')) return 'emerald';
  if (upper.includes('BLOCK') || upper.includes('FAIL') || upper.includes('REJECT')) return 'rose';
  if (upper.includes('WATCH') || upper.includes('REVIEW') || upper.includes('NOT READY')) return 'amber';
  if (upper.includes('AUTO') || upper.includes('PG')) return 'blue';
  return 'slate';
}

export default function App() {
  const [overview, setOverview] = useState<OverviewPayload | null>(null);
  const [strategy, setStrategy] = useState<StrategyDetailPayload | null>(null);
  const [reports, setReports] = useState<ReportsPayload | null>(null);
  const [selectedStrategy, setSelectedStrategy] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [overviewPayload, reportsPayload] = await Promise.all([
          fetchJson<OverviewPayload>('/api/new-dashboard/overview'),
          fetchJson<ReportsPayload>('/api/new-dashboard/reports'),
        ]);
        if (cancelled) return;
        setOverview(overviewPayload);
        setReports(reportsPayload);
        const firstStrategy =
          overviewPayload.current_strategy ||
          overviewPayload.registry?.strategies?.[0]?.strategy ||
          '';
        setSelectedStrategy(firstStrategy);
      } catch (loadError) {
        if (!cancelled) setError(loadError instanceof Error ? loadError.message : 'Failed to load dashboard');
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedStrategy) return;
    let cancelled = false;
    fetchJson<StrategyDetailPayload>(`/api/new-dashboard/strategies/${selectedStrategy}`)
      .then((payload) => {
        if (!cancelled) setStrategy(payload);
      })
      .catch((loadError) => {
        if (!cancelled) setError(loadError instanceof Error ? loadError.message : 'Failed to load strategy detail');
      });
    return () => {
      cancelled = true;
    };
  }, [selectedStrategy]);

  const recentReports = useMemo(() => reports?.reports?.slice(0, 8) || [], [reports]);
  const strategies = overview?.registry?.strategies || [];

  if (error) {
    return (
      <main className="min-h-screen bg-[radial-gradient(circle_at_top,_#e0f2fe,_#f8fafc_55%,_#e2e8f0)] px-6 py-10 text-slate-900">
        <div className="mx-auto max-w-5xl rounded-3xl border border-rose-200 bg-white p-10 shadow-xl">
          <h1 className="font-display text-3xl font-bold">New Dashboard</h1>
          <p className="mt-4 text-sm text-slate-600">{error}</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_#dbeafe,_#f8fafc_45%,_#e2e8f0)] px-6 py-8 text-slate-900">
      <div className="mx-auto max-w-7xl space-y-6">
        <section className={`${sectionCard} overflow-hidden`}>
          <div className="grid gap-6 bg-[linear-gradient(120deg,_rgba(15,23,42,0.96),_rgba(30,41,59,0.92),_rgba(2,132,199,0.82))] px-8 py-8 text-white md:grid-cols-[1.4fr_1fr]">
            <div>
              <p className="font-mono text-xs uppercase tracking-[0.3em] text-sky-200">Strategy Engineering Platform</p>
              <h1 className="mt-3 font-display text-4xl font-bold">Project Readiness and Control Dashboard</h1>
              <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-200">
                This frontend is wired to the existing Flask/SVOS backend and shows repository-backed readiness,
                governance, persistence, monitoring, and report state.
              </p>
            </div>
            <div className="grid gap-3 rounded-3xl border border-white/10 bg-white/10 p-5 backdrop-blur">
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-200">Current strategy</span>
                <StatusBadge label={overview?.current_strategy || 'none'} tone="blue" />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-200">Readiness</span>
                <StatusBadge
                  label={overview?.readiness?.production_readiness?.release_status || 'UNKNOWN'}
                  tone={toneForValue(overview?.readiness?.production_readiness?.release_status || 'UNKNOWN')}
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-200">Stabilization</span>
                <StatusBadge
                  label={overview?.readiness?.stabilization?.verdict || 'UNKNOWN'}
                  tone={toneForValue(overview?.readiness?.stabilization?.verdict || 'UNKNOWN')}
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-200">Recommendation</span>
                <StatusBadge label={overview?.recommendation_badge || 'REVIEW'} tone={toneForValue(overview?.recommendation_badge || 'REVIEW')} />
              </div>
            </div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {[
            {
              icon: <Shield className="h-5 w-5" />,
              label: 'Deployment readiness',
              value: overview?.deployment?.deployment_readiness || 'UNKNOWN',
            },
            {
              icon: <Database className="h-5 w-5" />,
              label: 'Persistence mode',
              value: overview?.persistence?.effective_mode || 'UNKNOWN',
            },
            {
              icon: <Activity className="h-5 w-5" />,
              label: 'Monitoring',
              value: overview?.monitoring?.monitoring_status || 'UNKNOWN',
            },
            {
              icon: <AlertTriangle className="h-5 w-5" />,
              label: 'Incident count',
              value: String(overview?.monitoring?.incident_count ?? 0),
            },
          ].map((card) => (
            <article key={card.label} className={`${sectionCard} p-5`}>
              <div className="flex items-center justify-between">
                <div className="rounded-2xl bg-slate-900 p-3 text-white">{card.icon}</div>
                <StatusBadge label={card.value} tone={toneForValue(card.value)} />
              </div>
              <p className="mt-4 text-sm font-medium text-slate-500">{card.label}</p>
            </article>
          ))}
        </section>

        <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <article className={`${sectionCard} p-6`}>
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-display text-2xl font-semibold">Strategy registry</h2>
                <p className="mt-1 text-sm text-slate-500">Repo-backed strategy records from the current SVOS control surface.</p>
              </div>
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <Workflow className="h-4 w-4" />
                {strategies.length} tracked
              </div>
            </div>
            <div className="mt-5 grid gap-3">
              {strategies.map((item) => (
                <button
                  key={item.strategy}
                  type="button"
                  onClick={() => setSelectedStrategy(item.strategy)}
                  className={`rounded-2xl border p-4 text-left transition ${
                    selectedStrategy === item.strategy
                      ? 'border-sky-300 bg-sky-50 shadow-sm'
                      : 'border-slate-200 bg-white hover:border-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold text-slate-900">{item.strategy}</p>
                      <p className="mt-1 text-xs text-slate-500">{item.manifest?.description || 'No description available'}</p>
                    </div>
                    <StatusBadge label={item.current_stage} tone={toneForValue(item.current_stage)} />
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
                    <span>Version {item.latest_version}</span>
                    <span>Evidence {item.evidence_count}</span>
                    <span>Transitions {item.transition_count}</span>
                    <span>Status {item.legacy_status}</span>
                  </div>
                </button>
              ))}
            </div>
          </article>

          <article className={`${sectionCard} p-6`}>
            <h2 className="font-display text-2xl font-semibold">Selected strategy</h2>
            {strategy ? (
              <div className="mt-5 space-y-4">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-slate-900">{strategy.record.strategy}</h3>
                    <StatusBadge label={strategy.record.current_stage} tone={toneForValue(strategy.record.current_stage)} />
                  </div>
                  <p className="mt-3 text-sm text-slate-600">{strategy.record.manifest?.description || 'No manifest description available.'}</p>
                  <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-500">
                    <span>Version {strategy.record.latest_version}</span>
                    <span>Evidence {strategy.record.evidence_count}</span>
                    <span>Transitions {strategy.record.transition_count}</span>
                  </div>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-2xl border border-slate-200 p-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Gate decisions</p>
                    <p className="mt-2 text-2xl font-semibold">{strategy.gate_decisions.length}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 p-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Approvals</p>
                    <p className="mt-2 text-2xl font-semibold">{strategy.approvals.length}</p>
                  </div>
                </div>
                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Manifest context</p>
                  <p className="mt-2 text-sm text-slate-600">
                    Symbols: {(strategy.record.manifest?.symbols || []).join(', ') || '—'}
                  </p>
                  <p className="mt-1 text-sm text-slate-600">
                    Timeframes: {(strategy.record.manifest?.timeframes || []).join(', ') || '—'}
                  </p>
                </div>
              </div>
            ) : (
              <p className="mt-5 text-sm text-slate-500">Select a strategy to inspect its lifecycle and evidence summary.</p>
            )}
          </article>
        </section>

        <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
          <article className={`${sectionCard} p-6`}>
            <div className="flex items-center gap-3">
              <div className="rounded-2xl bg-slate-900 p-3 text-white">
                <FileText className="h-5 w-5" />
              </div>
              <div>
                <h2 className="font-display text-2xl font-semibold">Readiness warnings</h2>
                <p className="text-sm text-slate-500">Mandatory failures and non-blocking warnings from the current approval pipeline.</p>
              </div>
            </div>
            <div className="mt-5 space-y-3">
              {(overview?.readiness?.production_readiness?.mandatory_failures || []).map((item) => (
                <div key={item} className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
                  {item}
                </div>
              ))}
              {(overview?.readiness?.production_readiness?.warnings || []).map((item) => (
                <div key={item} className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700">
                  {item}
                </div>
              ))}
              {!overview?.readiness?.production_readiness?.mandatory_failures?.length &&
              !overview?.readiness?.production_readiness?.warnings?.length ? (
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
                  No current approval warnings were reported by the backend.
                </div>
              ) : null}
            </div>
          </article>

          <article className={`${sectionCard} p-6`}>
            <h2 className="font-display text-2xl font-semibold">Recent reports</h2>
            <p className="mt-1 text-sm text-slate-500">Latest report index entries exposed by the existing dashboard backend.</p>
            <div className="mt-5 overflow-hidden rounded-2xl border border-slate-200">
              <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
                <thead className="bg-slate-50 text-slate-500">
                  <tr>
                    <th className="px-4 py-3 font-medium">Title</th>
                    <th className="px-4 py-3 font-medium">Type</th>
                    <th className="px-4 py-3 font-medium">Path</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {recentReports.map((report) => (
                    <tr key={report.report_id}>
                      <td className="px-4 py-3 font-medium text-slate-900">{report.title}</td>
                      <td className="px-4 py-3 text-slate-600">{report.report_type}</td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-500">{report.path}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        </section>
      </div>
    </main>
  );
}
