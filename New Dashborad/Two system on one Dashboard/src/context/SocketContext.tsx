import React, { createContext, useContext, useEffect, useRef, useState } from "react";
import type { LiveSnapshot, ReportDetail, RequestState, SessionState, StrategyPipelineReport, SvosSnapshot } from "../types.js";

type JsonBody = Record<string, unknown> | undefined;

interface MutationResult {
  ok: boolean;
  error?: string;
}

interface SocketContextType {
  session: RequestState<SessionState>;
  live: RequestState<LiveSnapshot>;
  svos: RequestState<SvosSnapshot>;
  isConnected: boolean;
  isStale: boolean;
  mutationPending: boolean;
  mutationBlockedReason: string;
  refreshAll: () => Promise<void>;
  closePosition: (positionId: string, reason: string) => Promise<MutationResult>;
  protectPosition: (positionId: string, stopLoss: number, takeProfit: number, reason: string) => Promise<MutationResult>;
  cancelOrder: (orderId: string, reason: string) => Promise<MutationResult>;
  emergencyStop: (reason: string, scope: "block_only" | "close_positions") => Promise<MutationResult>;
  clearEmergencyStop: (reason: string) => Promise<MutationResult>;
  createDeployment: (strategy: string, notes: string) => Promise<MutationResult>;
  importDeployment: (deploymentId: string) => Promise<MutationResult>;
  preflightDeployment: (deploymentId: string) => Promise<MutationResult>;
  activateDeployment: (deploymentId: string) => Promise<MutationResult>;
  rollbackDeployment: (deploymentId: string, toVersion: string, reason: string) => Promise<MutationResult>;
  reviewReport: (reportId: string) => Promise<MutationResult>;
  generateReport: (reportType: string) => Promise<MutationResult>;
  acknowledgeIncident: (incidentId: string) => Promise<MutationResult>;
  getReport: (reportId: string) => Promise<ReportDetail>;
  getPipelineReport: (strategyId: string) => Promise<StrategyPipelineReport>;
}

const STALE_AFTER_MS = 10_000;
const LIVE_POLL_MS = 3_000;
const SVOS_POLL_MS = 15_000;

const SocketContext = createContext<SocketContextType | undefined>(undefined);

function createRequestState<T>(): RequestState<T> {
  return {
    data: null,
    loading: true,
    error: "",
    lastSuccessAt: null,
  };
}

function getCookie(name: string): string {
  const prefix = `${name}=`;
  return document.cookie
    .split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith(prefix))
    ?.slice(prefix.length) ?? "";
}

async function readJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  if (!text) {
    return {} as T;
  }
  return JSON.parse(text) as T;
}

export const SocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [session, setSession] = useState<RequestState<SessionState>>(createRequestState);
  const [live, setLive] = useState<RequestState<LiveSnapshot>>(createRequestState);
  const [svos, setSvos] = useState<RequestState<SvosSnapshot>>(createRequestState);
  const [mutationCount, setMutationCount] = useState(0);

  const sessionAbortRef = useRef<AbortController | null>(null);
  const liveAbortRef = useRef<AbortController | null>(null);
  const svosAbortRef = useRef<AbortController | null>(null);
  const liveIntervalRef = useRef<number | null>(null);
  const svosIntervalRef = useRef<number | null>(null);
  const sessionTimerRef = useRef<number | null>(null);
  const refreshingLiveRef = useRef(false);
  const refreshingSvosRef = useRef(false);
  const refreshingSessionRef = useRef(false);

  const isStale = !live.data || !live.lastSuccessAt || Date.now() - live.lastSuccessAt > STALE_AFTER_MS;
  const isConnected = Boolean(live.data && !isStale && !live.error);
  const mutationPending = mutationCount > 0;

  const brokerConnected = live.data?.broker_status?.broker_connection === "CONNECTED";
  const mutationBlockedReason = !session.data?.authenticated
    ? "Authentication required for operator actions."
    : !session.data.mutation_allowed
      ? "Your role is read-only on this dashboard."
      : isStale
        ? "Live data is stale. Refresh before sending a control action."
        : !brokerConnected
          ? "Broker connection is not healthy enough for mutations."
          : mutationPending
            ? "A control action is already in progress."
            : "";

  async function apiRequest<T>(path: string, init?: RequestInit, body?: JsonBody): Promise<T> {
    const headers = new Headers(init?.headers ?? {});
    headers.set("Accept", "application/json");
    const method = (init?.method ?? "GET").toUpperCase();
    if (body !== undefined) {
      headers.set("Content-Type", "application/json");
    }
    if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
      const csrfToken = getCookie("dashboard_csrf");
      if (csrfToken) {
        headers.set("X-CSRF-Token", csrfToken);
      }
      headers.set("X-Requested-With", "fetch");
    }

    const response = await fetch(path, {
      ...init,
      headers,
      credentials: "same-origin",
      body: body === undefined ? init?.body : JSON.stringify(body),
    });

    if (!response.ok) {
      const errorPayload = await readJson<{ error?: string }>(response).catch(() => ({ error: "" }));
      throw new Error(errorPayload.error || `Request failed: ${response.status}`);
    }

    return readJson<T>(response);
  }

  async function refreshSession() {
    if (refreshingSessionRef.current) {
      return;
    }
    refreshingSessionRef.current = true;
    sessionAbortRef.current?.abort();
    const controller = new AbortController();
    sessionAbortRef.current = controller;

    setSession((current) => ({ ...current, loading: current.data === null, error: "" }));
    try {
      const payload = await apiRequest<SessionState>(`/api/session/me?t=${Date.now()}`, { signal: controller.signal });
      setSession({
        data: payload,
        loading: false,
        error: "",
        lastSuccessAt: Date.now(),
      });
    } catch (error) {
      if ((error as Error).name !== "AbortError") {
        setSession((current) => ({
          ...current,
          loading: false,
          error: (error as Error).message,
        }));
      }
    } finally {
      refreshingSessionRef.current = false;
    }
  }

  async function refreshLive() {
    if (refreshingLiveRef.current) {
      return;
    }
    refreshingLiveRef.current = true;
    liveAbortRef.current?.abort();
    const controller = new AbortController();
    liveAbortRef.current = controller;

    setLive((current) => ({ ...current, loading: current.data === null, error: "" }));
    try {
      const payload = await apiRequest<LiveSnapshot>(`/api/live-dashboard?t=${Date.now()}`, { signal: controller.signal });
      setLive({
        data: payload,
        loading: false,
        error: "",
        lastSuccessAt: Date.now(),
      });
    } catch (error) {
      if ((error as Error).name !== "AbortError") {
        setLive((current) => ({
          ...current,
          loading: false,
          error: (error as Error).message,
        }));
      }
    } finally {
      refreshingLiveRef.current = false;
    }
  }

  async function refreshSvos() {
    if (refreshingSvosRef.current) {
      return;
    }
    refreshingSvosRef.current = true;
    svosAbortRef.current?.abort();
    const controller = new AbortController();
    svosAbortRef.current = controller;

    setSvos((current) => ({ ...current, loading: current.data === null, error: "" }));
    try {
      const [overview, strategies, reports, governance, readiness, deployments, registry, rgm, smo, latestReports, productionHealthResponse] = await Promise.all([
        apiRequest<Record<string, unknown>>(`/api/new-dashboard/overview?t=${Date.now()}`, { signal: controller.signal }),
        apiRequest<SvosSnapshot["strategies"]>(`/api/new-dashboard/strategies?t=${Date.now()}`, { signal: controller.signal }),
        apiRequest<SvosSnapshot["reports"]>(`/api/new-dashboard/reports?t=${Date.now()}`, { signal: controller.signal }),
        apiRequest<Record<string, unknown>>(`/api/governance?t=${Date.now()}`, { signal: controller.signal }),
        apiRequest<Record<string, unknown>>(`/api/platform/readiness?t=${Date.now()}`, { signal: controller.signal }),
        apiRequest<{ deployments: SvosSnapshot["deployments"] }>(`/api/v1/deployments?t=${Date.now()}`, { signal: controller.signal }),
        apiRequest<SvosSnapshot["registry"]>(`/api/v1/strategy-registry?t=${Date.now()}`, { signal: controller.signal }),
        apiRequest<Record<string, unknown>>(`/api/rgm?t=${Date.now()}`, { signal: controller.signal }),
        apiRequest<SvosSnapshot["smo"]>(`/api/smo?t=${Date.now()}`, { signal: controller.signal }),
        apiRequest<SvosSnapshot["latestReports"]>(`/api/reports/latest?t=${Date.now()}`, { signal: controller.signal }),
        fetch(`/api/v1/production/health?t=${Date.now()}`, { credentials: "same-origin", signal: controller.signal }),
      ]);

      const productionHealth = productionHealthResponse.ok
        ? await readJson<Record<string, unknown>>(productionHealthResponse)
        : await readJson<Record<string, unknown>>(productionHealthResponse).catch(() => null);

      setSvos({
        data: {
          overview,
          strategies,
          reports,
          governance,
          readiness,
          deployments: deployments.deployments,
          registry,
          productionHealth,
          rgm,
          smo,
          latestReports,
          fetched_at: new Date().toISOString(),
        },
        loading: false,
        error: "",
        lastSuccessAt: Date.now(),
      });
    } catch (error) {
      if ((error as Error).name !== "AbortError") {
        setSvos((current) => ({
          ...current,
          loading: false,
          error: (error as Error).message,
        }));
      }
    } finally {
      refreshingSvosRef.current = false;
    }
  }

  async function refreshAll() {
    await Promise.all([refreshSession(), refreshLive(), refreshSvos()]);
  }

  async function runMutation(path: string, body?: JsonBody, init?: RequestInit): Promise<MutationResult> {
    if (mutationBlockedReason) {
      return { ok: false, error: mutationBlockedReason };
    }

    setMutationCount((value) => value + 1);
    try {
      await apiRequest(path, { ...init, method: init?.method ?? "POST" }, body);
      await Promise.all([refreshSession(), refreshLive(), refreshSvos()]);
      return { ok: true };
    } catch (error) {
      return { ok: false, error: (error as Error).message };
    } finally {
      setMutationCount((value) => Math.max(0, value - 1));
    }
  }

  useEffect(() => {
    refreshAll();
    liveIntervalRef.current = window.setInterval(refreshLive, LIVE_POLL_MS);
    svosIntervalRef.current = window.setInterval(refreshSvos, SVOS_POLL_MS);
    sessionTimerRef.current = window.setInterval(refreshSession, SVOS_POLL_MS);

    return () => {
      sessionAbortRef.current?.abort();
      liveAbortRef.current?.abort();
      svosAbortRef.current?.abort();
      if (liveIntervalRef.current !== null) {
        window.clearInterval(liveIntervalRef.current);
      }
      if (svosIntervalRef.current !== null) {
        window.clearInterval(svosIntervalRef.current);
      }
      if (sessionTimerRef.current !== null) {
        window.clearInterval(sessionTimerRef.current);
      }
    };
  }, []);

  return (
    <SocketContext.Provider
      value={{
        session,
        live,
        svos,
        isConnected,
        isStale,
        mutationPending,
        mutationBlockedReason,
        refreshAll,
        closePosition: (positionId, reason) => runMutation(`/api/live-dashboard/positions/${encodeURIComponent(positionId)}/close`, { reason }),
        protectPosition: (positionId, stopLoss, takeProfit, reason) =>
          runMutation(`/api/live-dashboard/positions/${encodeURIComponent(positionId)}/protect`, {
            stop_loss: stopLoss,
            take_profit: takeProfit,
            reason,
          }),
        cancelOrder: (orderId, reason) => runMutation(`/api/live-dashboard/orders/${encodeURIComponent(orderId)}/cancel`, { reason }),
        emergencyStop: (reason, scope) =>
          runMutation("/api/emergency-stop", {
            reason,
            scope,
            confirm_token: "CONFIRM-EMERGENCY-STOP",
          }),
        clearEmergencyStop: (reason) =>
          runMutation("/api/emergency-stop/clear", {
            reason,
            confirm_token: "CONFIRM-CLEAR-EMERGENCY-STOP",
          }),
        createDeployment: (strategy, notes) =>
          runMutation("/api/v1/deployments", {
            strategy,
            notes,
          }),
        importDeployment: (deploymentId) => runMutation(`/api/v1/production/deployments/${encodeURIComponent(deploymentId)}/import`),
        preflightDeployment: (deploymentId) => runMutation(`/api/v1/production/deployments/${encodeURIComponent(deploymentId)}/preflight`),
        activateDeployment: (deploymentId) => runMutation(`/api/v1/production/deployments/${encodeURIComponent(deploymentId)}/activate`),
        rollbackDeployment: (deploymentId, toVersion, reason) =>
          runMutation(`/api/v1/deployments/${encodeURIComponent(deploymentId)}/rollback`, {
            to_version: toVersion,
            reason,
          }),
        reviewReport: (reportId) => runMutation(`/api/reports/${encodeURIComponent(reportId)}/review`),
        generateReport: (reportType) => runMutation("/api/reports/generate", { type: reportType }),
        acknowledgeIncident: (incidentId) => runMutation("/api/incidents/ack", { incident_id: incidentId }),
        getReport: (reportId) => apiRequest(`/api/reports/${encodeURIComponent(reportId)}?t=${Date.now()}`),
        getPipelineReport: (strategyId) => apiRequest(`/api/new-dashboard/strategies/${encodeURIComponent(strategyId)}/pipeline-report?t=${Date.now()}`),
      }}
    >
      {children}
    </SocketContext.Provider>
  );
};

export function useSocket() {
  const context = useContext(SocketContext);
  if (!context) {
    throw new Error("useSocket must be used inside SocketProvider");
  }
  return context;
}
