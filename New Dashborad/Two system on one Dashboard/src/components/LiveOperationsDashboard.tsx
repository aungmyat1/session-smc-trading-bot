import React, { useState } from "react";
import { AlertTriangle, ArrowDownRight, ArrowUpRight, Ban, Lock, Shield, ShieldAlert } from "lucide-react";
import { useSocket } from "../context/SocketContext.js";
import type { OrderItem, PositionItem } from "../types.js";

function Panel({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-[26px] border border-white/10 bg-slate-950/70 p-5 shadow-[0_18px_50px_rgba(2,8,16,0.34)]">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-white">{title}</h2>
        {subtitle ? <p className="mt-1 text-sm text-slate-400">{subtitle}</p> : null}
      </div>
      {children}
    </section>
  );
}

function StatCard({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
      <p className="text-[11px] uppercase tracking-[0.24em] text-slate-400">{label}</p>
      <p className={`mt-3 text-2xl font-semibold ${accent}`}>{value}</p>
    </div>
  );
}

function formatNumber(value: number | string | null | undefined, digits = 2): string {
  if (value === null || value === undefined || value === "") {
    return "Unavailable";
  }
  const numeric = Number(value);
  if (Number.isNaN(numeric)) {
    return String(value);
  }
  return numeric.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function ActionNotice({ message, danger = false }: { message: string; danger?: boolean }) {
  return (
    <div className={`rounded-2xl border px-4 py-3 text-sm ${danger ? "border-rose-400/25 bg-rose-400/10 text-rose-100" : "border-amber-300/20 bg-amber-300/10 text-amber-100"}`}>
      {message}
    </div>
  );
}

export function LiveOperationsDashboard() {
  const {
    live,
    session,
    mutationBlockedReason,
    brokerActionBlockedReason,
    closePosition,
    protectPosition,
    cancelOrder,
    emergencyStop,
    clearEmergencyStop,
  } = useSocket();

  const [closeIntent, setCloseIntent] = useState<{ id: string; reason: string; message: string } | null>(null);
  const [protectIntent, setProtectIntent] = useState<{ id: string; stopLoss: string; takeProfit: string; reason: string; message: string } | null>(null);
  const [cancelIntent, setCancelIntent] = useState<{ id: string; reason: string; message: string } | null>(null);
  const [emergencyReason, setEmergencyReason] = useState("");
  const [emergencyScope, setEmergencyScope] = useState<"block_only" | "close_positions">("block_only");
  const [clearReason, setClearReason] = useState("");
  const [actionMessage, setActionMessage] = useState("");

  if (live.loading && !live.data) {
    return (
      <div className="rounded-[26px] border border-white/10 bg-slate-950/70 p-8 text-sm text-slate-300">
        Loading live execution snapshot from `/api/live-dashboard`.
      </div>
    );
  }

  if (!live.data) {
    return (
      <div className="rounded-[26px] border border-rose-400/20 bg-rose-400/10 p-8 text-sm text-rose-100">
        Live execution data is unavailable right now. The dashboard is intentionally showing the real backend state instead of fabricated values.
      </div>
    );
  }

  const { overview, positions, orders, trade_history, risk_dashboard, market_watch, broker_status, system, execution_monitor } = live.data;
  const controlsDisabled = Boolean(mutationBlockedReason);
  const brokerControlsDisabled = Boolean(mutationBlockedReason || brokerActionBlockedReason);
  const isAdmin = session.data?.role === "admin";

  async function handleClose(position: PositionItem) {
    const result = await closePosition(position.id, closeIntent?.reason || "");
    setActionMessage(result.ok ? `Close request sent for ${position.symbol}.` : result.error || "Close request failed.");
    if (result.ok) {
      setCloseIntent(null);
    }
  }

  async function handleProtect(position: PositionItem) {
    const stopLoss = Number(protectIntent?.stopLoss);
    const takeProfit = Number(protectIntent?.takeProfit);
    if (Number.isNaN(stopLoss) || Number.isNaN(takeProfit)) {
      setActionMessage("Stop loss and take profit must be numeric.");
      return;
    }
    const result = await protectPosition(position.id, stopLoss, takeProfit, protectIntent?.reason || "");
    setActionMessage(result.ok ? `Protection update sent for ${position.symbol}.` : result.error || "Protection update failed.");
    if (result.ok) {
      setProtectIntent(null);
    }
  }

  async function handleCancel(order: OrderItem) {
    const result = await cancelOrder(order.id, cancelIntent?.reason || "");
    setActionMessage(result.ok ? `Cancel request sent for ${order.symbol}.` : result.error || "Cancel request failed.");
    if (result.ok) {
      setCancelIntent(null);
    }
  }

  return (
    <div className="space-y-6">
      {actionMessage ? <ActionNotice message={actionMessage} danger={actionMessage.toLowerCase().includes("failed")} /> : null}
      {brokerActionBlockedReason ? <ActionNotice message={brokerActionBlockedReason} /> : null}

      <div className="grid gap-4 lg:grid-cols-4">
        <StatCard label="Equity" value={formatNumber(overview.equity)} accent="text-white" />
        <StatCard label="Daily PnL" value={formatNumber(overview.daily_pnl)} accent={overview.daily_pnl >= 0 ? "text-emerald-200" : "text-rose-200"} />
        <StatCard label="Open Positions" value={String(overview.open_positions)} accent="text-sky-200" />
        <StatCard label="Current Drawdown" value={`${formatNumber(risk_dashboard.current_drawdown_pct)}%`} accent="text-amber-100" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
        <Panel title="Account and Risk" subtitle="Authoritative execution overview from the Flask control plane.">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <div className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
              <p className="text-xs text-slate-400">Balance</p>
              <p className="mt-2 text-xl font-semibold text-white">{formatNumber(overview.account_balance)}</p>
            </div>
            <div className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
              <p className="text-xs text-slate-400">Free Margin</p>
              <p className="mt-2 text-xl font-semibold text-white">{formatNumber(overview.free_margin)}</p>
            </div>
            <div className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
              <p className="text-xs text-slate-400">Margin Level</p>
              <p className="mt-2 text-xl font-semibold text-white">{formatNumber(overview.margin_level_pct)}%</p>
            </div>
            <div className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
              <p className="text-xs text-slate-400">Open Risk</p>
              <p className="mt-2 text-xl font-semibold text-white">{formatNumber(risk_dashboard.open_risk)}</p>
            </div>
            <div className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
              <p className="text-xs text-slate-400">Exposure</p>
              <p className="mt-2 text-xl font-semibold text-white">{formatNumber(risk_dashboard.exposure)}</p>
            </div>
            <div className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
              <p className="text-xs text-slate-400">Execution Latency</p>
              <p className="mt-2 text-xl font-semibold text-white">{formatNumber(execution_monitor.execution_latency_ms)} ms</p>
            </div>
          </div>

          <div className="mt-4 space-y-2">
            {risk_dashboard.warnings.length ? (
              risk_dashboard.warnings.map((warning, index) => (
                <div key={`${warning.message}-${index}`} className="flex items-start gap-3 rounded-2xl border border-amber-300/20 bg-amber-300/10 px-4 py-3 text-sm text-amber-100">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{warning.message}</span>
                </div>
              ))
            ) : (
              <div className="rounded-2xl border border-emerald-300/20 bg-emerald-300/10 px-4 py-3 text-sm text-emerald-100">
                No active risk warnings were returned in the latest snapshot.
              </div>
            )}
          </div>
        </Panel>

        <Panel title="Broker and Safety" subtitle="Controls stay guarded unless the latest broker snapshot is healthy.">
          <div className="space-y-3 text-sm text-slate-300">
            <div className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.04] px-4 py-3">
              <span>Broker connection</span>
              <span className="font-semibold text-white">{broker_status.broker_connection || "Unavailable"}</span>
            </div>
            <div className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.04] px-4 py-3">
              <span>Connection quality</span>
              <span className="font-semibold text-white">{broker_status.connection_quality || "Unavailable"}</span>
            </div>
            <div className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.04] px-4 py-3">
              <span>Average spread</span>
              <span className="font-semibold text-white">{formatNumber(broker_status.spread)} pips</span>
            </div>
            <div className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.04] px-4 py-3">
              <span>Live trading enabled</span>
              <span className="font-semibold text-white">{String(system.live_trading_enabled)}</span>
            </div>
          </div>

          {system.emergency_stop?.active ? (
            <div className="mt-4 rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm text-rose-100">
              <div className="flex items-start gap-3">
                <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
                <div>
                  <p className="font-semibold">Emergency stop is active.</p>
                  <p className="mt-1">Reason: {system.emergency_stop.reason || "Not provided"}</p>
                </div>
              </div>
            </div>
          ) : null}

          <div className="mt-4 space-y-3 rounded-2xl border border-white/8 bg-white/[0.04] p-4">
            <div className="flex items-center gap-2 text-white">
              <Shield className="h-4 w-4" />
              <h3 className="font-semibold">Emergency Stop</h3>
            </div>
            <textarea
              value={emergencyReason}
              onChange={(event) => setEmergencyReason(event.target.value)}
              placeholder="Reason required for operator audit trail"
              className="min-h-24 w-full rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-white outline-none placeholder:text-slate-500"
            />
            <select
              value={emergencyScope}
              onChange={(event) => setEmergencyScope(event.target.value as "block_only" | "close_positions")}
              className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-white outline-none"
            >
              <option value="block_only">Block new activity only</option>
              <option value="close_positions">Block and close open positions</option>
            </select>
            <button
              disabled={controlsDisabled || !emergencyReason.trim()}
              onClick={async () => {
                const result = await emergencyStop(emergencyReason, emergencyScope);
                setActionMessage(result.ok ? "Emergency stop request accepted." : result.error || "Emergency stop failed.");
                if (result.ok) {
                  setEmergencyReason("");
                }
              }}
              className="rounded-full bg-rose-300 px-4 py-2 text-sm font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Trigger emergency stop
            </button>
            {isAdmin ? (
              <>
                <textarea
                  value={clearReason}
                  onChange={(event) => setClearReason(event.target.value)}
                  placeholder="Admin reason required to clear emergency stop"
                  className="min-h-20 w-full rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-white outline-none placeholder:text-slate-500"
                />
                <button
                  disabled={controlsDisabled || !clearReason.trim()}
                  onClick={async () => {
                    const result = await clearEmergencyStop(clearReason);
                    setActionMessage(result.ok ? "Emergency stop clear request accepted." : result.error || "Clear request failed.");
                    if (result.ok) {
                      setClearReason("");
                    }
                  }}
                  className="rounded-full border border-white/10 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Clear emergency stop
                </button>
              </>
            ) : (
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <Lock className="h-4 w-4" />
                Admin role required to clear an emergency stop.
              </div>
            )}
          </div>
        </Panel>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <Panel title="Open Positions" subtitle="Close and protect use the existing `/api/live-dashboard` controls.">
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-[0.2em] text-slate-400">
                <tr>
                  <th className="pb-3">Symbol</th>
                  <th className="pb-3">Direction</th>
                  <th className="pb-3">Volume</th>
                  <th className="pb-3">Entry</th>
                  <th className="pb-3">Current</th>
                  <th className="pb-3">PnL</th>
                  <th className="pb-3">Controls</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/6 text-slate-200">
                {positions.items.length ? (
                  positions.items.map((position) => (
                    <tr key={position.id}>
                      <td className="py-4 font-medium text-white">{position.symbol}</td>
                      <td className="py-4">
                        <span className={`inline-flex items-center gap-1 ${position.direction === "buy" ? "text-emerald-200" : "text-rose-200"}`}>
                          {position.direction === "buy" ? <ArrowUpRight className="h-4 w-4" /> : <ArrowDownRight className="h-4 w-4" />}
                          {position.direction}
                        </span>
                      </td>
                      <td className="py-4">{formatNumber(position.volume)}</td>
                      <td className="py-4">{formatNumber(position.entry_price, 5)}</td>
                      <td className="py-4">{formatNumber(position.current_price, 5)}</td>
                      <td className={`py-4 ${position.unrealized_pnl >= 0 ? "text-emerald-200" : "text-rose-200"}`}>{formatNumber(position.unrealized_pnl)}</td>
                      <td className="py-4">
                        <div className="flex flex-wrap gap-2">
                          <button
                            disabled={brokerControlsDisabled}
                            onClick={() => setCloseIntent({ id: position.id, reason: "", message: position.symbol })}
                            className="rounded-full border border-rose-300/30 px-3 py-1.5 text-xs font-semibold text-rose-100 disabled:opacity-40"
                          >
                            Close
                          </button>
                          <button
                            disabled={brokerControlsDisabled}
                            onClick={() =>
                              setProtectIntent({
                                id: position.id,
                                stopLoss: String(position.stop_loss || ""),
                                takeProfit: String(position.take_profit || ""),
                                reason: "",
                                message: position.symbol,
                              })
                            }
                            className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40"
                          >
                            Protect
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-slate-400">
                      No open positions were returned by the backend.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {closeIntent ? (
            <div className="mt-4 rounded-2xl border border-rose-400/20 bg-rose-400/10 p-4 text-sm text-rose-100">
              <p className="font-semibold">Confirm close for {closeIntent.message}</p>
              <textarea
                value={closeIntent.reason}
                onChange={(event) => setCloseIntent({ ...closeIntent, reason: event.target.value })}
                className="mt-3 min-h-20 w-full rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-white outline-none"
                placeholder="Reason required for audit trail"
              />
              <div className="mt-3 flex gap-2">
                <button
                  disabled={!closeIntent.reason.trim()}
                  onClick={() => {
                    const position = positions.items.find((item) => item.id === closeIntent.id);
                    if (position) {
                      void handleClose(position);
                    }
                  }}
                  className="rounded-full bg-rose-300 px-4 py-2 font-semibold text-slate-950 disabled:opacity-40"
                >
                  Confirm close
                </button>
                <button onClick={() => setCloseIntent(null)} className="rounded-full border border-white/10 px-4 py-2 font-semibold text-white">
                  Cancel
                </button>
              </div>
            </div>
          ) : null}

          {protectIntent ? (
            <div className="mt-4 rounded-2xl border border-white/10 bg-white/[0.04] p-4 text-sm text-slate-200">
              <p className="font-semibold text-white">Protect {protectIntent.message}</p>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <input
                  value={protectIntent.stopLoss}
                  onChange={(event) => setProtectIntent({ ...protectIntent, stopLoss: event.target.value })}
                  placeholder="Stop loss"
                  className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-white outline-none"
                />
                <input
                  value={protectIntent.takeProfit}
                  onChange={(event) => setProtectIntent({ ...protectIntent, takeProfit: event.target.value })}
                  placeholder="Take profit"
                  className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-white outline-none"
                />
              </div>
              <textarea
                value={protectIntent.reason}
                onChange={(event) => setProtectIntent({ ...protectIntent, reason: event.target.value })}
                placeholder="Reason for protection change"
                className="mt-3 min-h-20 w-full rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-white outline-none"
              />
              <div className="mt-3 flex gap-2">
                <button
                  disabled={!protectIntent.reason.trim()}
                  onClick={() => {
                    const position = positions.items.find((item) => item.id === protectIntent.id);
                    if (position) {
                      void handleProtect(position);
                    }
                  }}
                  className="rounded-full bg-sky-300 px-4 py-2 font-semibold text-slate-950 disabled:opacity-40"
                >
                  Confirm protection
                </button>
                <button onClick={() => setProtectIntent(null)} className="rounded-full border border-white/10 px-4 py-2 font-semibold text-white">
                  Cancel
                </button>
              </div>
            </div>
          ) : null}
        </Panel>

        <Panel title="Orders and Market Watch" subtitle="Pending order cancellation is the only write action exposed here.">
          <div className="space-y-4">
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="text-xs uppercase tracking-[0.2em] text-slate-400">
                  <tr>
                    <th className="pb-3">Order</th>
                    <th className="pb-3">Status</th>
                    <th className="pb-3">Entry</th>
                    <th className="pb-3">Control</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/6 text-slate-200">
                  {orders.pending.length ? (
                    orders.pending.map((order) => (
                      <tr key={order.id}>
                        <td className="py-4">
                          <p className="font-medium text-white">{order.symbol}</p>
                          <p className="text-xs text-slate-400">{order.direction}</p>
                        </td>
                        <td className="py-4">{order.status}</td>
                        <td className="py-4">{formatNumber(order.entry_price, 5)}</td>
                        <td className="py-4">
                          <button
                            disabled={brokerControlsDisabled}
                            onClick={() => setCancelIntent({ id: order.id, reason: "", message: order.symbol })}
                            className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40"
                          >
                            Cancel order
                          </button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={4} className="py-6 text-center text-slate-400">
                        No pending orders were returned.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {cancelIntent ? (
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 text-sm text-slate-200">
                <p className="font-semibold text-white">Confirm cancellation for {cancelIntent.message}</p>
                <textarea
                  value={cancelIntent.reason}
                  onChange={(event) => setCancelIntent({ ...cancelIntent, reason: event.target.value })}
                  placeholder="Reason required for audit trail"
                  className="mt-3 min-h-20 w-full rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-white outline-none"
                />
                <div className="mt-3 flex gap-2">
                  <button
                    disabled={!cancelIntent.reason.trim()}
                    onClick={() => {
                      const order = orders.pending.find((item) => item.id === cancelIntent.id);
                      if (order) {
                        void handleCancel(order);
                      }
                    }}
                    className="rounded-full bg-white px-4 py-2 font-semibold text-slate-950 disabled:opacity-40"
                  >
                    Confirm cancel
                  </button>
                  <button onClick={() => setCancelIntent(null)} className="rounded-full border border-white/10 px-4 py-2 font-semibold text-white">
                    Cancel
                  </button>
                </div>
              </div>
            ) : null}

            <div className="grid gap-3">
              {market_watch.symbols.length ? (
                market_watch.symbols.map((item) => (
                  <div key={item.symbol} className="rounded-2xl border border-white/8 bg-white/[0.04] px-4 py-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-semibold text-white">{item.symbol}</p>
                        <p className="text-xs text-slate-400">{item.time || "Price timestamp unavailable"}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm text-white">Bid {formatNumber(item.bid, 5)}</p>
                        <p className="text-xs text-slate-400">Ask {formatNumber(item.ask, 5)} | Spread {formatNumber(item.spread_pips)}</p>
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <ActionNotice message="Market watch is unavailable. The backend returned no live watchlist values." />
              )}
            </div>
          </div>
        </Panel>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <Panel title="Trade History" subtitle="Recent closed trades from journal-backed history.">
          <div className="space-y-3">
            {trade_history.trades.slice(0, 8).length ? (
              trade_history.trades.slice(0, 8).map((trade, index) => (
                <div key={`${String(trade.timestamp)}-${index}`} className="rounded-2xl border border-white/8 bg-white/[0.04] px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold text-white">
                        {String(trade.symbol || "Unknown symbol")} · {String(trade.result || "Unknown result")}
                      </p>
                      <p className="text-xs text-slate-400">{String(trade.timestamp || "Unknown time")}</p>
                    </div>
                    <div className={`text-sm font-semibold ${Number(trade.profit || 0) >= 0 ? "text-emerald-200" : "text-rose-200"}`}>
                      {formatNumber(Number(trade.profit || 0))}
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <ActionNotice message="No journal-backed closed trades were returned." />
            )}
          </div>
        </Panel>

        <Panel title="Execution Stream" subtitle="Latest execution queue items and broker responses.">
          <div className="space-y-3">
            {execution_monitor.current_execution_queue.length ? (
              execution_monitor.current_execution_queue.slice(0, 10).map((entry, index) => (
                <div key={`${String(entry.time)}-${index}`} className="rounded-2xl border border-white/8 bg-white/[0.04] px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold text-white">{String(entry.event || "EVENT")} · {String(entry.symbol || "N/A")}</p>
                      <p className="text-xs text-slate-400">{String(entry.time || "Unknown time")}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-semibold text-white">{String(entry.status || "UNKNOWN")}</p>
                      <p className="text-xs text-slate-400">{formatNumber(Number(entry.processing_time_ms || 0))} ms</p>
                    </div>
                  </div>
                  {entry.broker_response ? <p className="mt-2 text-xs text-slate-400">{String(entry.broker_response)}</p> : null}
                </div>
              ))
            ) : (
              <div className="rounded-2xl border border-white/8 bg-white/[0.04] px-4 py-6 text-center text-sm text-slate-400">
                No execution queue events were returned in the current snapshot.
              </div>
            )}
            <div className="rounded-2xl border border-sky-300/15 bg-sky-300/10 px-4 py-3 text-sm text-sky-100">
              <div className="flex items-start gap-3">
                <Ban className="mt-0.5 h-4 w-4 shrink-0" />
                <p>
                  This interface deliberately does not expose simulation-only controls such as pause or resume, broker reconnect, risk setting mutation, or direct strategy activation.
                </p>
              </div>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}
