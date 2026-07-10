/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { createContext, useContext, useState, useEffect, useRef } from "react";
import { LiveDashboardState, SystemStatus } from "../types.js";

interface SocketContextType {
  state: LiveDashboardState | null;
  isConnected: boolean;
  // Operator session (2026-07-05) — see docs/systems/system2/DASHBOARD_READINESS.md
  // §9. Reuses the existing bearer-token backend (dashboard/rbac.py) as the
  // sole identity source; this is a thin client-side session wrapper, not a
  // second authentication implementation.
  isAuthenticated: boolean;
  operatorActor: string | null;
  login: (token: string, actor: string) => Promise<string | null>; // returns error message, or null on success
  logout: () => void;
  pauseTrading: () => Promise<void>;
  resumeTrading: () => Promise<void>;
  resetAnalytics: () => Promise<void>;
  selectPair: (symbol: string) => Promise<void>;
  forceCloseTrade: () => Promise<void>;
  activateStrategy: (id: string, broker: string, symbols: string[], riskProfile: string, version: string) => Promise<void>;
  pauseStrategy: (id: string) => Promise<void>;
  triggerKillSwitch: () => Promise<void>;
  clearEmergencyStop: () => Promise<void>;
  updateRiskControls: (maxDailyLoss: number, maxOpenPositions: number, maxLeverage: string, autoDisableConditions: any) => Promise<void>;
  reconnectBroker: () => Promise<void>;
  // Exposed so read-only panels (e.g. ValidationDashboard) can call
  // dashboard/status_server.py's authenticated GET endpoints without
  // duplicating the auth-header logic above.
  authenticatedFetch: (url: string, options?: RequestInit) => Promise<Response>;
}

const SocketContext = createContext<SocketContextType | undefined>(undefined);

const SESSION_TOKEN_KEY = "svosOperatorToken";
const SESSION_ACTOR_KEY = "svosOperatorActor";

export const SocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, setState] = useState<LiveDashboardState | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [operatorActor, setOperatorActor] = useState<string | null>(() => {
    // Optimistic restore on reload — sessionStorage.get, "current session" per
    // the sprint's storage requirement (cleared when the tab/browser closes,
    // unlike localStorage). Whether the credential is still actually valid is
    // confirmed by the next authenticated call; a 401 triggers logout() below.
    try {
      return window.sessionStorage.getItem(SESSION_TOKEN_KEY) ? window.sessionStorage.getItem(SESSION_ACTOR_KEY) : null;
    } catch {
      return null;
    }
  });
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef<number>(0);

  // Poll as backup
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchStateBackup = async () => {
    try {
      const res = await fetch(`/api/new-dashboard/live-state?t=${Date.now()}`);
      if (res.ok) {
        const contentType = res.headers.get("content-type");
        if (contentType && contentType.includes("application/json")) {
          const data = await res.json();
          setState(data);
        } else {
          console.warn("Backup polling received non-JSON response, likely server is restarting or proxy is warming up.");
        }
      }
    } catch (err) {
      console.warn("Backup polling failed (transient network drop or server restarting):", err);
    }
  };

  const startPolling = () => {
    if (!pollIntervalRef.current) {
      pollIntervalRef.current = setInterval(fetchStateBackup, 1500);
    }
  };

  const stopPolling = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  };

  // Reads the operator credential the login() function below stores. Single
  // source of identity: the existing dashboard/rbac.py bearer-token model —
  // this is a client-side session wrapper around it, not a second auth
  // implementation.
  const getOperatorAuthHeaders = (): Record<string, string> => {
    try {
      const token = window.sessionStorage.getItem(SESSION_TOKEN_KEY);
      const actor = window.sessionStorage.getItem(SESSION_ACTOR_KEY);
      if (token && actor) {
        return { Authorization: `Bearer ${token}`, "X-SVOS-Actor": actor };
      }
    } catch {
      // sessionStorage unavailable (e.g. private browsing) — fall through
    }
    return {};
  };

  const logout = () => {
    try {
      window.sessionStorage.removeItem(SESSION_TOKEN_KEY);
      window.sessionStorage.removeItem(SESSION_ACTOR_KEY);
    } catch {
      // ignore
    }
    setOperatorActor(null);
    if (socketRef.current) {
      socketRef.current.close();
    }
  };

  // Wraps fetch with operator auth headers and session-expiry handling: any
  // 401 means the stored credential is no longer valid server-side (rotated,
  // revoked) — the existing backend is stateless/header-based with no
  // server-side session to expire, so "session expiry" here means "the
  // credential this client is holding stopped working," detected on next use.
  const authenticatedFetch = async (url: string, options: RequestInit = {}): Promise<Response> => {
    const res = await fetch(url, {
      ...options,
      headers: { ...(options.headers || {}), ...getOperatorAuthHeaders() },
    });
    if (res.status === 401) {
      console.warn(`Operator session expired or invalid (401 from ${url}) — logging out.`);
      logout();
    }
    return res;
  };

  const login = async (token: string, actor: string): Promise<string | null> => {
    if (!token.trim() || !actor.trim()) {
      return "Token and actor name are both required.";
    }
    try {
      // Validate against a real, already-authenticated endpoint before
      // committing to the session — never store a credential that hasn't
      // been proven to work.
      const res = await fetch("/api/ws-ticket", {
        headers: { Authorization: `Bearer ${token}`, "X-SVOS-Actor": actor },
      });
      if (res.status === 401) {
        return "Invalid operator token.";
      }
      if (res.status === 503) {
        return "Operator authentication is not configured on the server.";
      }
      if (!res.ok) {
        return `Login failed (HTTP ${res.status}).`;
      }
      window.sessionStorage.setItem(SESSION_TOKEN_KEY, token);
      window.sessionStorage.setItem(SESSION_ACTOR_KEY, actor);
      setOperatorActor(actor);
      // Pick up the new credential immediately rather than waiting for the
      // next scheduled reconnect (up to 3s away).
      connectWebSocket();
      return null;
    } catch (err) {
      return `Login request failed: ${err}`;
    }
  };

  const connectWebSocket = async () => {
    if (socketRef.current) {
      socketRef.current.close();
    }

    // Browsers cannot set Authorization/X-SVOS-Actor headers on a WebSocket
    // upgrade request, so /ws is authenticated via a short-lived ticket
    // obtained through a normal, fully-authenticated REST call instead
    // (see dashboard/rbac.py mint_ws_ticket/validate_ws_ticket).
    let ticket: string | null = null;
    try {
      const ticketRes = await fetch("/api/ws-ticket", { headers: getOperatorAuthHeaders() });
      if (ticketRes.ok) {
        ticket = (await ticketRes.json()).ticket;
      } else {
        console.warn(`WebSocket ticket request failed (HTTP ${ticketRes.status}) — no operator credential available yet, using REST polling.`);
      }
    } catch (err) {
      console.warn("WebSocket ticket request errored — using REST polling.", err);
    }

    if (!ticket) {
      // Don't attempt a connection the server can only reject — that would
      // just spam reconnects. Poll instead; the next scheduled retry picks
      // up a ticket the moment one becomes obtainable.
      startPolling();
      reconnectAttemptsRef.current++;
      reconnectTimeoutRef.current = setTimeout(connectWebSocket, 3000);
      return;
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    // dashboard/status_server.py only registers GET /ws — /api/ws does not
    // exist (verified live: 404). The previous alternating logic sent half
    // of all reconnect attempts at a route that can never succeed.
    const wsUrl = `${protocol}//${window.location.host}/ws?ticket=${encodeURIComponent(ticket)}`;

    console.log(`Connecting WebSocket to /ws (attempt #${reconnectAttemptsRef.current})...`);
    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    ws.onopen = () => {
      console.log("WebSocket connected successfully");
      setIsConnected(true);
      reconnectAttemptsRef.current = 0; // Reset counter upon success
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      // The server pushes discrete event notifications, not a bootstrap
      // snapshot on connect — fetch one explicitly so the UI shows real
      // data immediately rather than waiting for the first event.
      fetchStateBackup();
      stopPolling();
    };

    ws.onmessage = (event) => {
      // Real /ws messages are BaseEvent-shaped (event_type/source_system/
      // payload/severity — dashboard/events.py), not a full state snapshot
      // and not the {type: "INITIAL_STATE"|"TICK", state} shape this used
      // to check for (that shape was never sent by the real backend, only
      // by this app's original mock server.ts). Treat any real event as
      // "something changed, refresh" rather than trying to reconstruct
      // partial UI state from an individual event's payload.
      try {
        const parsed = JSON.parse(event.data);
        if (parsed && typeof parsed.event_type === "string") {
          fetchStateBackup();
        }
      } catch (err) {
        console.error("Error parsing socket message", err);
      }
    };

    ws.onclose = () => {
      console.log("WebSocket closed. Attempting reconnect...");
      setIsConnected(false);
      socketRef.current = null;
      startPolling();
      reconnectAttemptsRef.current++;
      reconnectTimeoutRef.current = setTimeout(() => {
        connectWebSocket();
      }, 3000);
    };

    ws.onerror = (err) => {
      console.warn("WebSocket encountered connection error:", err);
      ws.close();
    };
  };

  useEffect(() => {
    // Initial fetch to get state immediately
    fetchStateBackup();
    // Connect WS
    connectWebSocket();

    return () => {
      if (socketRef.current) {
        socketRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  // All operator-control actions below call the REAL backend
  // (dashboard/status_server.py) via authenticatedFetch — no locally-
  // simulated routes, no /api/action multiplexing (that was this app's
  // original mock server.ts, not a real contract). Each mutation requires
  // both a real operator session (401 → auto-logout) and an explicit
  // confirmation click, so the CONFIRM-token these endpoints require is
  // never auto-filled without the operator deliberately choosing to send it.

  const requireLogin = (): boolean => {
    if (!operatorActor) {
      window.alert("Operator login required for this action.");
      return false;
    }
    return true;
  };

  const pauseTrading = async () => {
    if (!requireLogin()) return;
    if (!window.confirm("Pause all new trade entries? Existing positions stay open.")) return;
    try {
      const res = await authenticatedFetch("/api/control/pause", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm_token: "CONFIRM-PAUSE-TRADING", reason: `Operator pause (${operatorActor})` }),
      });
      if (res.ok) await fetchStateBackup();
      else console.error("Pause trading failed:", res.status, await res.text());
    } catch (err) {
      console.error(err);
    }
  };

  const resumeTrading = async () => {
    if (!requireLogin()) return;
    if (!window.confirm("Resume trading?")) return;
    try {
      const res = await authenticatedFetch("/api/control/resume", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm_token: "CONFIRM-RESUME-TRADING", reason: `Operator resume (${operatorActor})` }),
      });
      if (res.ok) await fetchStateBackup();
      else console.error("Resume trading failed:", res.status, await res.text());
    } catch (err) {
      console.error(err);
    }
  };

  // No real backend concept of "reset analytics" exists (the only real
  // analytics source is TradeJournalDB — a destructive server-side reset of
  // real trade history is a far bigger action than a UI "reset" implies).
  // This clears only locally-derived display state, touching no persisted
  // data, and is intentionally client-only rather than a fetch to a route
  // that doesn't exist.
  const resetAnalytics = async () => {
    await fetchStateBackup();
  };

  // Pure client-side UI navigation — selecting which pair's chart to view
  // has no server-side concept and never needed a backend round-trip.
  const selectPair = async (symbol: string) => {
    setState((prev) => (prev ? { ...prev, selectedPair: symbol } : null));
  };

  // No real backend concept of "close this one pending trade" exists — the
  // only close-related backend action is /api/control/close-all, which
  // closes EVERY open position across every pair via a full emergency stop
  // (scope=close_positions). Silently mapping "close this one trade" to
  // "close everything and halt" would be a real safety bug, not a fix, so
  // this is deliberately left unimplemented rather than wired to the wrong
  // action. activeTrade (what this operates on) is already reported
  // `unavailable` by /api/new-dashboard/live-state today regardless.
  const forceCloseTrade = async () => {
    console.warn("forceCloseTrade: no safe single-position-close endpoint exists yet (see docs/systems/system2/DASHBOARD_READINESS.md §9) — not sent.");
  };

  // Activating a new strategy deployment is deliberately blocked server-side
  // (production/activation.py dead-ends at STAGED_DISABLED) — there is no
  // endpoint to wire this to, and there shouldn't be one without a separate,
  // explicit decision to unblock live strategy activation.
  const activateStrategy = async (_id: string, _broker: string, _symbols: string[], _riskProfile: string, _version: string) => {
    console.warn("activateStrategy: strategy activation is deliberately blocked server-side — not sent.");
  };

  const pauseStrategy = async (id: string) => {
    if (!requireLogin()) return;
    if (!window.confirm(`Pause strategy "${id}"?`)) return;
    try {
      const res = await authenticatedFetch("/api/control/toggle-strategy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          strategy_id: id,
          action: "pause",
          confirm_token: `CONFIRM-TOGGLE-STRATEGY-${id}`,
          reason: `Operator pause (${operatorActor})`,
        }),
      });
      if (res.ok) await fetchStateBackup();
      else console.error("Pause strategy failed:", res.status, await res.text());
    } catch (err) {
      console.error(err);
    }
  };

  const triggerKillSwitch = async () => {
    if (!requireLogin()) return;
    // Explicit operator confirmation before sending — CONFIRM-EMERGENCY-STOP
    // is a fixed, server-required literal (not an operator-chosen secret),
    // but it must never be sent without a deliberate confirm click.
    if (!window.confirm("EMERGENCY STOP: this closes ALL open positions and halts new trading. Continue?")) return;
    try {
      const res = await authenticatedFetch("/api/emergency-stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reason: `Operator emergency kill switch (${operatorActor})`,
          confirm_token: "CONFIRM-EMERGENCY-STOP",
          scope: "close_positions",
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.emergency_stop && data.emergency_stop.active) {
          await fetchStateBackup();
        } else {
          console.error("Kill switch request succeeded but backend did not report an active emergency stop:", data);
        }
      } else {
        console.error("Emergency kill switch request failed:", res.status, await res.text());
      }
    } catch (err) {
      console.error(err);
    }
  };

  const clearEmergencyStop = async () => {
    if (!requireLogin()) return;
    if (!window.confirm("Clear the active emergency stop and allow trading to resume?")) return;
    try {
      const res = await authenticatedFetch("/api/emergency-stop/clear", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: `Operator review complete (${operatorActor})`, confirm_token: "CONFIRM-CLEAR-EMERGENCY-STOP" }),
      });
      if (res.ok) await fetchStateBackup();
      else console.error("Clear emergency stop failed:", res.status, await res.text());
    } catch (err) {
      console.error(err);
    }
  };

  // No backend endpoint exists for editing live risk controls
  // (/api/operations/risk is read-only) — deliberately not wired to a
  // fabricated route.
  const updateRiskControls = async (_maxDailyLoss: number, _maxOpenPositions: number, _maxLeverage: string, _autoDisableConditions: any) => {
    console.warn("updateRiskControls: no backend write endpoint exists yet (see docs/systems/system2/DASHBOARD_READINESS.md §9) — not sent.");
  };

  // No backend endpoint exists for forcing a broker reconnect — this is
  // tied to the separate, larger "shared broker runtime" milestone
  // (dashboard opens its own MetaAPI session today; reconnecting that
  // session in isolation from the runner's own connection would be
  // misleading, not a fix).
  const reconnectBroker = async () => {
    console.warn("reconnectBroker: no backend endpoint exists yet — tied to the Shared Broker Runtime milestone, not sent.");
  };

  return (
    <SocketContext.Provider
      value={{
        state,
        isConnected,
        isAuthenticated: !!operatorActor,
        operatorActor,
        login,
        logout,
        pauseTrading,
        resumeTrading,
        resetAnalytics,
        selectPair,
        forceCloseTrade,
        activateStrategy,
        pauseStrategy,
        triggerKillSwitch,
        clearEmergencyStop,
        updateRiskControls,
        reconnectBroker,
        authenticatedFetch
      }}
    >
      {children}
    </SocketContext.Provider>
  );
};

export const useSocket = () => {
  const context = useContext(SocketContext);
  if (context === undefined) {
    throw new Error("useSocket must be used within a SocketProvider");
  }
  return context;
};
