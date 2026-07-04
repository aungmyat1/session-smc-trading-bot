/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { createContext, useContext, useState, useEffect, useRef } from "react";
import { LiveDashboardState, SystemStatus } from "../types.js";

interface SocketContextType {
  state: LiveDashboardState | null;
  isConnected: boolean;
  pauseTrading: () => Promise<void>;
  resumeTrading: () => Promise<void>;
  resetAnalytics: () => Promise<void>;
  selectPair: (symbol: string) => Promise<void>;
  forceCloseTrade: () => Promise<void>;
  activateStrategy: (id: string, broker: string, symbols: string[], riskProfile: string, version: string) => Promise<void>;
  pauseStrategy: (id: string) => Promise<void>;
  triggerKillSwitch: () => Promise<void>;
  updateRiskControls: (maxDailyLoss: number, maxOpenPositions: number, maxLeverage: string, autoDisableConditions: any) => Promise<void>;
  reconnectBroker: () => Promise<void>;
}

const SocketContext = createContext<SocketContextType | undefined>(undefined);

export const SocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, setState] = useState<LiveDashboardState | null>(null);
  const [isConnected, setIsConnected] = useState(false);
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

  const connectWebSocket = () => {
    if (socketRef.current) {
      socketRef.current.close();
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    // Alternate paths to guarantee routing compatibility with different reverse-proxy configurations
    const path = reconnectAttemptsRef.current % 2 === 0 ? "/ws" : "/api/ws";
    const wsUrl = `${protocol}//${window.location.host}${path}`;

    console.log(`Connecting WebSocket to ${wsUrl} (attempt #${reconnectAttemptsRef.current})...`);
    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    ws.onopen = () => {
      console.log("WebSocket connected successfully to", wsUrl);
      setIsConnected(true);
      reconnectAttemptsRef.current = 0; // Reset counter upon success
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      // Stop backup polling since we are connected
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "INITIAL_STATE" || payload.type === "TICK") {
          setState(payload.state);
        }
      } catch (err) {
        console.error("Error parsing socket message", err);
      }
    };

    ws.onclose = () => {
      console.log("WebSocket closed. Attempting reconnect...");
      setIsConnected(false);
      socketRef.current = null;

      // Start backup polling immediately so dashboard remains alive
      if (!pollIntervalRef.current) {
        pollIntervalRef.current = setInterval(fetchStateBackup, 1500);
      }

      // Increment reconnect attempts and schedule reconnect
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

  const pauseTrading = async () => {
    try {
      const res = await fetch("/api/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "pause" })
      });
      if (res.ok) {
        const data = await res.json();
        setState((prev) => prev ? { ...prev, isTradingPaused: data.isTradingPaused } : null);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const resumeTrading = async () => {
    try {
      const res = await fetch("/api/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "resume" })
      });
      if (res.ok) {
        const data = await res.json();
        setState((prev) => prev ? { ...prev, isTradingPaused: data.isTradingPaused } : null);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const resetAnalytics = async () => {
    try {
      const res = await fetch("/api/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "reset" })
      });
      if (res.ok) {
        const data = await res.json();
        if (data.state) setState(data.state);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const selectPair = async (symbol: string) => {
    try {
      const res = await fetch("/api/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "select_pair", symbol })
      });
      if (res.ok) {
        setState((prev) => prev ? { ...prev, selectedPair: symbol } : null);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const forceCloseTrade = async () => {
    try {
      const res = await fetch("/api/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "force_close" })
      });
      if (res.ok) {
        const data = await res.json();
        if (data.state) setState(data.state);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const activateStrategy = async (id: string, broker: string, symbols: string[], riskProfile: string, version: string) => {
    try {
      const res = await fetch("/api/live/strategy/activate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, broker, symbols, riskProfile, version })
      });
      if (res.ok) {
        const data = await res.json();
        if (data.state) setState(data.state);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const pauseStrategy = async (id: string) => {
    try {
      const res = await fetch("/api/live/strategy/pause", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id })
      });
      if (res.ok) {
        const data = await res.json();
        if (data.state) setState(data.state);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const triggerKillSwitch = async () => {
    try {
      const res = await fetch("/api/live/kill-switch", {
        method: "POST",
        headers: { "Content-Type": "application/json" }
      });
      if (res.ok) {
        const data = await res.json();
        if (data.state) setState(data.state);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const updateRiskControls = async (maxDailyLoss: number, maxOpenPositions: number, maxLeverage: string, autoDisableConditions: any) => {
    try {
      const res = await fetch("/api/live/risk-controls", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ maxDailyLoss, maxOpenPositions, maxLeverage, autoDisableConditions })
      });
      if (res.ok) {
        const data = await res.json();
        if (data.state) setState(data.state);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const reconnectBroker = async () => {
    try {
      const res = await fetch("/api/live/broker/reconnect", {
        method: "POST",
        headers: { "Content-Type": "application/json" }
      });
      if (res.ok) {
        const data = await res.json();
        if (data.state) setState(data.state);
      }
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <SocketContext.Provider
      value={{
        state,
        isConnected,
        pauseTrading,
        resumeTrading,
        resetAnalytics,
        selectPair,
        forceCloseTrade,
        activateStrategy,
        pauseStrategy,
        triggerKillSwitch,
        updateRiskControls,
        reconnectBroker
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
