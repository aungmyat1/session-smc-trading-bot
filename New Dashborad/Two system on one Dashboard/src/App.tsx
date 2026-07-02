import React, { useEffect, useState } from "react";
import { ActivitySquare, AlertTriangle, BookOpenText, Clock3, LayoutDashboard, RefreshCw, ShieldAlert, Signal, Waves, Workflow, Wrench } from "lucide-react";
import { SocketProvider, useSocket } from "./context/SocketContext.js";
import { LiveOperationsDashboard } from "./components/LiveOperationsDashboard.js";
import { SvosResearchDashboard } from "./components/SvosResearchDashboard.js";
import { OverviewDashboard } from "./components/OverviewDashboard.js";
import { PipelineOpsDashboard } from "./components/PipelineOpsDashboard.js";
import { PositionsDashboard } from "./components/PositionsDashboard.js";
import { HealthDashboard } from "./components/HealthDashboard.js";

type ViewMode = "overview" | "live" | "pipeline" | "positions" | "svos" | "health";

const ROUTES: Array<{ mode: ViewMode; path: string; label: string; icon: React.ComponentType<{ className?: string }> }> = [
  { mode: "overview", path: "/new-dashboard/overview", label: "Overview", icon: LayoutDashboard },
  { mode: "live", path: "/new-dashboard/live", label: "Live", icon: Signal },
  { mode: "pipeline", path: "/new-dashboard/pipeline", label: "Pipeline", icon: Workflow },
  { mode: "positions", path: "/new-dashboard/positions", label: "Positions", icon: ActivitySquare },
  { mode: "svos", path: "/new-dashboard/svos", label: "SVOS", icon: BookOpenText },
  { mode: "health", path: "/new-dashboard/health", label: "Health", icon: Wrench },
];

function resolveViewMode(pathname: string): ViewMode {
  const normalized = pathname.replace(/\/+$/, "");
  const route = ROUTES.find((item) => normalized === item.path);
  return route?.mode || "overview";
}

function StatusPill({ label, tone }: { label: string; tone: "good" | "warn" | "danger" | "muted" }) {
  const styles = {
    good: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
    warn: "border-amber-300/30 bg-amber-300/10 text-amber-100",
    danger: "border-rose-400/30 bg-rose-400/10 text-rose-100",
    muted: "border-white/10 bg-white/5 text-slate-300",
  };

  return <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${styles[tone]}`}>{label}</span>;
}

function DashboardFrame() {
  const { session, live, svos, isConnected, isStale, mutationBlockedReason, mutationPending, refreshAll } = useSocket();
  const [currentTime, setCurrentTime] = useState(() => new Date());
  const [viewMode, setViewMode] = useState<ViewMode>(() => resolveViewMode(window.location.pathname));

  useEffect(() => {
    const timer = window.setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    function syncRoute() {
      setViewMode(resolveViewMode(window.location.pathname));
    }

    window.addEventListener("popstate", syncRoute);
    if (window.location.pathname === "/new-dashboard" || window.location.pathname === "/new-dashboard/") {
      window.history.replaceState({}, "", "/new-dashboard/overview");
      syncRoute();
    }

    return () => window.removeEventListener("popstate", syncRoute);
  }, []);

  function navigate(mode: ViewMode) {
    const route = ROUTES.find((item) => item.mode === mode);
    if (!route) {
      return;
    }
    window.history.pushState({}, "", route.path);
    setViewMode(mode);
  }

  const emergencyActive = Boolean(live.data?.system.emergency_stop?.active);
  const brokerLabel = live.data?.broker_status?.broker_connection || "UNKNOWN";
  const roleLabel = session.data?.role || "read-only";

  function renderView() {
    if (viewMode === "overview") {
      return <OverviewDashboard />;
    }
    if (viewMode === "live") {
      return <LiveOperationsDashboard />;
    }
    if (viewMode === "pipeline") {
      return <PipelineOpsDashboard />;
    }
    if (viewMode === "positions") {
      return <PositionsDashboard />;
    }
    if (viewMode === "svos") {
      return <SvosResearchDashboard />;
    }
    return <HealthDashboard />;
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(34,197,94,0.14),_transparent_32%),linear-gradient(180deg,_#07111a_0%,_#0b1721_45%,_#081018_100%)] text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-6 sm:px-6 lg:px-8">
        <header className="rounded-[28px] border border-white/10 bg-slate-950/70 p-5 shadow-[0_30px_120px_rgba(4,10,20,0.48)] backdrop-blur">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-emerald-300/25 bg-emerald-300/10 text-emerald-200">
                  <Waves className="h-6 w-6" />
                </div>
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.35em] text-emerald-200/80">Unified Operations</p>
                  <h1 className="text-2xl font-semibold tracking-tight text-white">SVOS Research and Trading Control</h1>
                </div>
              </div>
              <p className="max-w-3xl text-sm leading-6 text-slate-300">
                One operator surface for live execution safety, deployment progression, and SVOS evidence review. The dashboard stays read-only when data is stale, identity is missing, or the broker path is degraded.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Operator</p>
                <p className="mt-2 truncate text-sm font-medium text-white">{session.data?.actor || "Unauthenticated"}</p>
                <p className="mt-1 text-xs text-slate-400">{roleLabel}</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Trading Mode</p>
                <p className="mt-2 text-sm font-medium text-white">{live.data?.system.trading_mode || session.data?.trading_mode || "unknown"}</p>
                <p className="mt-1 text-xs text-slate-400">
                  Demo only: {String(live.data?.system.demo_only ?? session.data?.demo_only ?? true)}
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Broker Link</p>
                <p className="mt-2 text-sm font-medium text-white">{brokerLabel}</p>
                <p className="mt-1 text-xs text-slate-400">Heartbeat {live.data?.broker_status?.last_heartbeat || "unavailable"}</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Clock</p>
                <p className="mt-2 text-sm font-medium text-white">{currentTime.toISOString().slice(11, 19)} UTC</p>
                <p className="mt-1 text-xs text-slate-400">{currentTime.toISOString().slice(0, 10)}</p>
              </div>
            </div>
          </div>

          <div className="mt-5 flex flex-col gap-3 border-t border-white/10 pt-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-wrap items-center gap-2">
              <StatusPill label={isConnected ? "Live polling healthy" : "Live polling degraded"} tone={isConnected ? "good" : "warn"} />
              <StatusPill label={isStale ? "Data stale" : "Data fresh"} tone={isStale ? "danger" : "good"} />
              <StatusPill label={emergencyActive ? "Emergency stop active" : "Emergency stop clear"} tone={emergencyActive ? "danger" : "muted"} />
              <StatusPill label={mutationPending ? "Mutation pending" : "Mutations idle"} tone={mutationPending ? "warn" : "muted"} />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {ROUTES.map((route) => {
                const Icon = route.icon;
                const active = viewMode === route.mode;
                return (
                  <button
                    key={route.mode}
                    onClick={() => navigate(route.mode)}
                    className={`rounded-full px-4 py-2 text-sm font-semibold transition ${active ? "bg-emerald-300 text-slate-950" : "border border-white/10 bg-white/5 text-slate-200 hover:bg-white/10"}`}
                  >
                    <span className="inline-flex items-center gap-2">
                      <Icon className="h-4 w-4" />
                      {route.label}
                    </span>
                  </button>
                );
              })}
              <button
                onClick={refreshAll}
                className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:bg-white/10"
              >
                <span className="inline-flex items-center gap-2">
                  <RefreshCw className="h-4 w-4" />
                  Refresh
                </span>
              </button>
            </div>
          </div>
        </header>

        {mutationBlockedReason ? (
          <div className="mt-4 rounded-2xl border border-amber-300/20 bg-amber-300/10 px-4 py-3 text-sm text-amber-100">
            <div className="flex items-start gap-3">
              <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
              <div>
                <p className="font-semibold">Operator controls are guarded right now.</p>
                <p className="mt-1 text-amber-50/85">{mutationBlockedReason}</p>
              </div>
            </div>
          </div>
        ) : null}

        {live.error || svos.error || session.error ? (
          <div className="mt-4 rounded-2xl border border-rose-400/20 bg-rose-400/10 px-4 py-3 text-sm text-rose-100">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
              <div className="space-y-1">
                {session.error ? <p>Session: {session.error}</p> : null}
                {live.error ? <p>Live data: {live.error}</p> : null}
                {svos.error ? <p>SVOS data: {svos.error}</p> : null}
              </div>
            </div>
          </div>
        ) : null}

        <main className="mt-6 flex-1">
          {renderView()}
        </main>

        <footer className="mt-6 flex flex-col items-start justify-between gap-3 rounded-[24px] border border-white/8 bg-slate-950/60 px-5 py-4 text-xs text-slate-400 sm:flex-row sm:items-center">
          <div className="inline-flex items-center gap-2">
            <Clock3 className="h-4 w-4" />
            <span>Polling cadence: live every 3 seconds, SVOS every 15 seconds, controls disabled after 10 seconds of stale data.</span>
          </div>
          <span>Served from Flask at `/new-dashboard/` with existing backend safety and audit authorities.</span>
        </footer>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <SocketProvider>
      <DashboardFrame />
    </SocketProvider>
  );
}
