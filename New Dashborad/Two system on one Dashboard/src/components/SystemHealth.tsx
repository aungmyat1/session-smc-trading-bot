/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
import { SystemHealth as SystemHealthType, SystemStatus } from "../types.js";
import { Activity, Database, Zap, Cpu, ShieldAlert, Wifi, ArrowDownUp } from "lucide-react";

interface Props {
  health: SystemHealthType;
  isConnected: boolean;
}

export const SystemHealth: React.FC<Props> = ({ health, isConnected }) => {
  const getStatusColor = (status: SystemStatus) => {
    switch (status) {
      case SystemStatus.ACTIVE:
      case SystemStatus.CONNECTED:
        return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
      case SystemStatus.WARNING:
        return "text-amber-400 bg-amber-500/10 border-amber-500/30";
      case SystemStatus.ERROR:
      case SystemStatus.DISCONNECTED:
        return "text-rose-400 bg-rose-500/10 border-rose-500/30";
      default:
        return "text-zinc-400 bg-zinc-500/10 border-zinc-500/30";
    }
  };

  const getIcon = (name: string) => {
    switch (name.toLowerCase()) {
      case "broker link":
        return <ArrowDownUp className="w-3.5 h-3.5" />;
      case "redis cache":
        return <Activity className="w-3.5 h-3.5" />;
      case "database pool":
        return <Database className="w-3.5 h-3.5" />;
      case "risk manager":
        return <ShieldAlert className="w-3.5 h-3.5" />;
      case "executor core":
        return <Zap className="w-3.5 h-3.5" />;
      case "smc processor":
        return <Cpu className="w-3.5 h-3.5" />;
      default:
        return <Wifi className="w-3.5 h-3.5" />;
    }
  };

  const services = [
    health.broker,
    health.redis,
    health.database,
    health.riskEngine,
    health.executionEngine,
    health.strategyEngine,
  ];

  return (
    <div className="w-full bg-zinc-900 border border-zinc-800/80 rounded-xl p-3 shadow-lg flex flex-wrap items-center justify-between gap-3 font-mono text-xs">
      <div className="flex items-center gap-2">
        <span className="text-zinc-500 text-[10px] uppercase tracking-widest font-bold">System Connection:</span>
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded border text-[11px] bg-zinc-950 border-zinc-800">
          <span className={`relative flex h-2 w-2`}>
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${isConnected ? "bg-emerald-400" : "bg-amber-400"}`}></span>
            <span className={`relative inline-flex rounded-full h-2 w-2 ${isConnected ? "bg-emerald-500" : "bg-amber-500"}`}></span>
          </span>
          <span className={isConnected ? "text-emerald-400 font-medium" : "text-amber-400 font-medium"}>
            {isConnected ? "WS STREAMING" : "POLLING FALLBACK"}
          </span>
        </div>
        <span className="text-zinc-600">|</span>
        <span className="text-zinc-400 text-[11px]">Clock Sync: <span className="text-zinc-300 font-medium">{health.clockSync}</span></span>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {services.map((service, idx) => {
          if (!service) return null;
          return (
            <div
              key={idx}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded border text-[11px] transition-all duration-300 ${getStatusColor(service.status)}`}
            >
              {getIcon(service.name)}
              <span className="font-semibold text-zinc-300">{service.name.split(" ")[0]}:</span>
              <span>{service.status === SystemStatus.ACTIVE || service.status === SystemStatus.CONNECTED ? `${service.latency}ms` : "OFFLINE"}</span>
            </div>
          );
        })}

        <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded border text-[11px] bg-emerald-500/10 border-emerald-500/30 text-emerald-400`}>
          <Wifi className="w-3.5 h-3.5 animate-pulse" />
          <span className="font-semibold text-zinc-300">WS:</span>
          <span>{health.websocket ? `${health.websocket.latency}ms` : "Active"}</span>
        </div>
      </div>
    </div>
  );
};
