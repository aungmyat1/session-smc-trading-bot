/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useRef } from "react";
import { VirtualDemoReport, BrokerSimulationLog } from "../types";
import { Terminal, Play, Pause, Activity, Cpu, Radio, Shield, AlertTriangle } from "lucide-react";

interface VirtualDemoViewProps {
  virtualDemo?: VirtualDemoReport;
  symbol: string;
}

export default function VirtualDemoView({ virtualDemo, symbol }: VirtualDemoViewProps) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamLogs, setStreamLogs] = useState<BrokerSimulationLog[]>([]);
  const [tickPrice, setTickPrice] = useState(150.0);
  const [ordersSubmitted, setOrdersSubmitted] = useState(0);
  const [ordersFilled, setOrdersFilled] = useState(0);
  const [ordersRejected, setOrdersRejected] = useState(0);
  
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // Load baseline logs
  useEffect(() => {
    if (virtualDemo) {
      setStreamLogs(virtualDemo.executionLogs.slice(0, 8));
      setOrdersSubmitted(virtualDemo.simulatedOrdersSubmitted);
      setOrdersFilled(virtualDemo.simulatedOrdersFilled);
      setOrdersRejected(virtualDemo.simulatedOrdersRejected);
      
      const lastLog = virtualDemo.executionLogs[virtualDemo.executionLogs.length - 1];
      if (lastLog) {
        // extract price from log text if possible
        const match = lastLog.message.match(/\$(\d+\.\d+)/);
        if (match && match[1]) {
          setTickPrice(parseFloat(match[1]));
        }
      }
    }
  }, [virtualDemo]);

  // Clean up streaming intervals
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const toggleStream = () => {
    if (isStreaming) {
      if (timerRef.current) clearInterval(timerRef.current);
      setIsStreaming(false);
    } else {
      setIsStreaming(true);
      
      timerRef.current = setInterval(() => {
        // Generate a live tick price
        setTickPrice(prev => {
          const change = (Math.random() - 0.49) * 0.45; // slight upward drift
          return parseFloat((prev + change).toFixed(2));
        });

        // Chance of order submission
        if (Math.random() > 0.4) {
          setOrdersSubmitted(prev => prev + 1);
          
          const isFill = Math.random() > 0.08;
          const latency = 12 + Math.floor(Math.random() * 80);
          const spread = 1.0 + Math.random() * 2.5;
          const slippage = Math.random() * 1.5;
          const logTime = new Date().toISOString().split("T")[1].slice(0, 8);

          if (isFill) {
            setOrdersFilled(prev => prev + 1);
            const newLog: BrokerSimulationLog = {
              time: logTime,
              level: "EXECUTION",
              message: `FILL SUCCESS: Buy 100 ${symbol} at $${(tickPrice + slippage).toFixed(2)} (Slippage: ${slippage.toFixed(2)} bps, Spread: ${spread.toFixed(2)} bps)`,
              latencyMs: latency,
              spreadBps: spread,
              slippageBps: slippage
            };
            setStreamLogs(prev => [newLog, ...prev.slice(0, 19)]);
          } else {
            setOrdersRejected(prev => prev + 1);
            const newLog: BrokerSimulationLog = {
              time: logTime,
              level: "WARNING",
              message: `ORDER REJECTED: Slippage protection deviation cap exceeded for ${symbol} at $${tickPrice.toFixed(2)}`,
              latencyMs: latency,
              spreadBps: spread,
              slippageBps: 0
            };
            setStreamLogs(prev => [newLog, ...prev.slice(0, 19)]);
          }
        } else {
          // Heartbeat message
          const logTime = new Date().toISOString().split("T")[1].slice(0, 8);
          const latency = 8 + Math.floor(Math.random() * 12);
          const newLog: BrokerSimulationLog = {
            time: logTime,
            level: "INFO",
            message: `Broker feed tick synchronized. Roundtrip RTT: ${latency}ms`,
            latencyMs: latency,
            spreadBps: 1.2,
            slippageBps: 0
          };
          setStreamLogs(prev => [newLog, ...prev.slice(0, 19)]);
        }
      }, 1500);
    }
  };

  const getLogLevelStyles = (level: string) => {
    switch (level) {
      case "EXECUTION":
        return "text-emerald-400 font-bold";
      case "WARNING":
        return "text-amber-400 font-bold animate-pulse";
      case "ERROR":
        return "text-red-400 font-bold animate-pulse";
      case "INFO":
      default:
        return "text-blue-400";
    }
  };

  if (!virtualDemo) {
    return (
      <div className="bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-850 rounded-lg p-8 text-center text-slate-500 dark:text-slate-400 transition-colors">
        <Terminal className="h-10 w-10 text-slate-400 dark:text-slate-500 mx-auto mb-3" />
        <p className="font-semibold text-sm text-slate-800 dark:text-slate-200">No Broker Emulation Generated</p>
        <p className="text-xs text-slate-500 dark:text-slate-450 mt-1">Please promote your strategy to the Virtual Demo stage to establish broker simulation feeds.</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      {/* Telemetry Panel */}
      <div className="lg:col-span-4 space-y-6">
        {/* Connection Console Card */}
        <div className="bg-slate-950 text-slate-100 border border-slate-900 rounded-lg p-5 shadow-lg">
          <div className="flex justify-between items-center mb-5 border-b border-slate-800 pb-3">
            <span className="text-[10px] font-mono text-slate-500 uppercase tracking-widest">Broker Gateway</span>
            <span className={`h-2.5 w-2.5 rounded-full ${isStreaming ? "bg-emerald-500 animate-ping" : "bg-red-500"}`} />
          </div>

          <div className="text-center py-6">
            <span className="text-[10px] font-mono text-slate-400 uppercase tracking-widest block">Live Simulated Spot Feed</span>
            <span className="text-4xl font-mono font-bold tracking-tight block text-white mt-1.5 animate-pulse">
              ${tickPrice.toFixed(2)}
            </span>
            <span className="text-[11px] font-mono text-slate-400 bg-slate-900 border border-slate-800 px-2 py-1 rounded inline-block mt-3 uppercase">
              SYMBOL: {symbol} // SPOT FEED
            </span>
          </div>

          <div className="pt-4 border-t border-slate-800 mt-2">
            <button
              onClick={toggleStream}
              className={`w-full py-2.5 rounded-md text-xs font-mono uppercase tracking-wider flex items-center justify-center space-x-2 transition-colors border ${
                isStreaming
                  ? "bg-amber-600 border-amber-700 hover:bg-amber-500 text-white"
                  : "bg-emerald-600 border-emerald-700 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-950/20"
              }`}
              id="virtual-toggle-stream-btn"
            >
              {isStreaming ? (
                <>
                  <Pause className="h-4 w-4" />
                  <span>Disconnect Live Feeds</span>
                </>
              ) : (
                <>
                  <Play className="h-4 w-4 fill-white" />
                  <span>Connect Live Tick Stream</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Execution Metrics Grid */}
        <div className="bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-850 rounded-lg p-5 shadow-sm space-y-4 transition-colors">
          <h3 className="font-display font-semibold text-slate-900 dark:text-slate-100 text-sm flex items-center space-x-1.5 border-b border-slate-100 dark:border-slate-850 pb-2">
            <Activity className="h-4 w-4 text-slate-600 dark:text-slate-400" />
            <span>Virtual Broker Performance</span>
          </h3>

          <div className="grid grid-cols-2 gap-3 text-xs font-mono">
            <div className="bg-slate-50 dark:bg-slate-900 border border-slate-100 dark:border-slate-800 p-3 rounded-md">
              <span className="text-[9px] text-slate-400 dark:text-slate-500 block uppercase">Submitted</span>
              <span className="text-base font-bold text-slate-900 dark:text-slate-100">{ordersSubmitted}</span>
            </div>
            <div className="bg-slate-50 dark:bg-slate-900 border border-slate-100 dark:border-slate-800 p-3 rounded-md">
              <span className="text-[9px] text-slate-400 dark:text-slate-500 block uppercase">Filled</span>
              <span className="text-base font-bold text-emerald-600 dark:text-emerald-450">{ordersFilled}</span>
            </div>
            <div className="bg-slate-50 dark:bg-slate-900 border border-slate-100 dark:border-slate-800 p-3 rounded-md">
              <span className="text-[9px] text-slate-400 dark:text-slate-500 block uppercase">Rejected</span>
              <span className="text-base font-bold text-red-600 dark:text-red-450">{ordersRejected}</span>
            </div>
            <div className="bg-slate-50 dark:bg-slate-900 border border-slate-100 dark:border-slate-800 p-3 rounded-md">
              <span className="text-[9px] text-slate-400 dark:text-slate-500 block uppercase">Avg Latency</span>
              <span className="text-base font-bold text-slate-900 dark:text-slate-100">{virtualDemo.averageLatencyMs.toFixed(1)}ms</span>
            </div>
          </div>
        </div>
      </div>

      {/* Real-time Order Console */}
      <div className="lg:col-span-8 flex flex-col border border-slate-950 bg-slate-950 text-slate-200 rounded-lg shadow-xl overflow-hidden min-h-[400px]">
        {/* Terminal Header */}
        <div className="bg-slate-900 border-b border-slate-800 px-4 py-3 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Terminal className="h-4 w-4 text-slate-400" />
            <span className="font-mono text-xs text-slate-300 font-bold tracking-wider uppercase">
              VIRTUAL_BROKER_CONSOLE // TRANSACTION_LOGS
            </span>
          </div>
          <span className="font-mono text-[10px] text-slate-500">LIVE FEED CHANNEL ENABLED</span>
        </div>

        {/* Console outputs */}
        <div className="flex-1 p-5 font-mono text-[11px] space-y-2.5 overflow-y-auto max-h-[350px] dark-scrollbar bg-slate-950 flex flex-col-reverse">
          {streamLogs.map((log, idx) => (
            <div key={idx} className="flex items-start space-x-2.5 border-b border-slate-900 pb-2 last:border-0 hover:bg-slate-900/30 px-1 py-0.5 rounded transition-colors">
              <span className="text-slate-500 shrink-0 select-none">[{log.time}]</span>
              <span className={`${getLogLevelStyles(log.level)} shrink-0 uppercase select-none w-14`}>
                {log.level}:
              </span>
              <span className="text-slate-300 flex-1 leading-relaxed">{log.message}</span>
              <span className="text-[10px] text-slate-500 shrink-0 hidden sm:inline select-none">
                {log.latencyMs}ms RTT
              </span>
            </div>
          ))}

          {streamLogs.length === 0 && (
            <div className="text-center text-slate-500 py-16">
              Awaiting live broker network connection... Click 'Connect Live Tick Stream' to start price streaming.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
