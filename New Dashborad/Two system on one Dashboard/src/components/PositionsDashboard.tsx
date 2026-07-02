import React, { useEffect, useState } from "react";
import { ArrowDownRight, ArrowUpRight, Ban, Shield } from "lucide-react";
import { useSocket } from "../context/SocketContext.js";
import type { OrderItem, PositionItem } from "../types.js";
import { MetricCard, Panel, StatusChip, formatTime, formatValue, toneFromStatus } from "./opsShared.js";

function tradeTimestamp(trade: Record<string, string | number | null>): string {
  return String(trade.timestamp || trade.time || trade.close_time || trade.ts || "");
}

function tradeSymbol(trade: Record<string, string | number | null>): string {
  return String(trade.symbol || trade.instrument || trade.pair || "Unknown");
}

export function PositionsDashboard() {
  const { live, mutationBlockedReason, closePosition, protectPosition, cancelOrder } = useSocket();
  const [closeIntent, setCloseIntent] = useState<{ id: string; symbol: string; reason: string } | null>(null);
  const [protectIntent, setProtectIntent] = useState<{ id: string; symbol: string; stopLoss: string; takeProfit: string; reason: string } | null>(null);
  const [cancelIntent, setCancelIntent] = useState<{ id: string; symbol: string; reason: string } | null>(null);
  const [actionMessage, setActionMessage] = useState("");
  const [selectedTradeIndex, setSelectedTradeIndex] = useState(0);

  if (live.loading && !live.data) {
    return <div className="rounded-[26px] border border-white/10 bg-slate-950/70 p-8 text-sm text-slate-300">Loading position, order, and trade decision data.</div>;
  }

  if (!live.data) {
    return <div className="rounded-[26px] border border-rose-400/20 bg-rose-400/10 p-8 text-sm text-rose-100">Position and order data is unavailable right now.</div>;
  }

  const controlsDisabled = Boolean(mutationBlockedReason);
  const trades = live.data.trade_history.trades || [];
  const selectedTrade = trades[selectedTradeIndex] || null;
  const matchedPosition = selectedTrade ? live.data.positions.items.find((item) => item.symbol === tradeSymbol(selectedTrade)) : null;

  useEffect(() => {
    if (selectedTradeIndex >= trades.length) {
      setSelectedTradeIndex(0);
    }
  }, [selectedTradeIndex, trades.length]);

  async function submitClose(position: PositionItem) {
    const result = await closePosition(position.id, closeIntent?.reason || "");
    setActionMessage(result.ok ? `Close request sent for ${position.symbol}.` : result.error || "Close request failed.");
    if (result.ok) {
      setCloseIntent(null);
    }
  }

  async function submitProtect(position: PositionItem) {
    const stopLoss = Number(protectIntent?.stopLoss);
    const takeProfit = Number(protectIntent?.takeProfit);
    if (Number.isNaN(stopLoss) || Number.isNaN(takeProfit)) {
      setActionMessage("Stop loss and take profit must be numeric.");
      return;
    }
    const result = await protectPosition(position.id, stopLoss, takeProfit, protectIntent?.reason || "");
    setActionMessage(result.ok ? `Protection updated for ${position.symbol}.` : result.error || "Protection update failed.");
    if (result.ok) {
      setProtectIntent(null);
    }
  }

  async function submitCancel(order: OrderItem) {
    const result = await cancelOrder(order.id, cancelIntent?.reason || "");
    setActionMessage(result.ok ? `Cancel request sent for ${order.symbol}.` : result.error || "Cancel request failed.");
    if (result.ok) {
      setCancelIntent(null);
    }
  }

  return (
    <div className="space-y-6">
      {actionMessage ? <div className="rounded-2xl border border-emerald-300/20 bg-emerald-300/10 px-4 py-3 text-sm text-emerald-100">{actionMessage}</div> : null}

      <div className="grid gap-4 lg:grid-cols-4">
        <MetricCard label="Open Positions" value={String(live.data.positions.count)} accent="text-white" />
        <MetricCard label="Pending Orders" value={String(live.data.orders.pending.length)} accent="text-sky-200" />
        <MetricCard label="Realized PnL" value={formatValue(live.data.overview.realized_pnl)} accent="text-emerald-200" />
        <MetricCard label="Open Risk" value={formatValue(live.data.risk_dashboard.open_risk)} accent="text-amber-100" detail={mutationBlockedReason || "Controls available"} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <Panel title="Open Positions" subtitle="Dedicated position management surface with reasoned actions.">
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-[0.2em] text-slate-400">
                <tr>
                  <th className="pb-3">Symbol</th>
                  <th className="pb-3">Direction</th>
                  <th className="pb-3">Volume</th>
                  <th className="pb-3">PnL</th>
                  <th className="pb-3">Updated Controls</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/6 text-slate-200">
                {live.data.positions.items.map((position) => (
                  <tr key={position.id}>
                    <td className="py-4 font-medium text-white">{position.symbol}</td>
                    <td className="py-4">
                      <span className={`inline-flex items-center gap-1 ${position.direction === "buy" ? "text-emerald-200" : "text-rose-200"}`}>
                        {position.direction === "buy" ? <ArrowUpRight className="h-4 w-4" /> : <ArrowDownRight className="h-4 w-4" />}
                        {position.direction}
                      </span>
                    </td>
                    <td className="py-4">{formatValue(position.volume)}</td>
                    <td className={`py-4 ${position.unrealized_pnl >= 0 ? "text-emerald-200" : "text-rose-200"}`}>{formatValue(position.unrealized_pnl)}</td>
                    <td className="py-4">
                      <div className="flex flex-wrap gap-2">
                        <button disabled={controlsDisabled} onClick={() => setCloseIntent({ id: position.id, symbol: position.symbol, reason: "" })} className="rounded-full border border-rose-300/30 px-3 py-1.5 text-xs font-semibold text-rose-100 disabled:opacity-40">Close</button>
                        <button disabled={controlsDisabled} onClick={() => setProtectIntent({ id: position.id, symbol: position.symbol, stopLoss: String(position.stop_loss || ""), takeProfit: String(position.take_profit || ""), reason: "" })} className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40">Protect</button>
                      </div>
                    </td>
                  </tr>
                ))}
                {!live.data.positions.items.length ? (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-slate-400">No open positions were returned by the backend.</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel title="Trade Decision Inspector" subtitle="Quick operator context around recent closed trades and matching live exposure.">
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
              {trades.slice(0, 8).map((trade, index) => (
                <button
                  key={`${tradeTimestamp(trade)}-${index}`}
                  onClick={() => setSelectedTradeIndex(index)}
                  className={`rounded-full px-3 py-1.5 text-xs font-semibold ${selectedTradeIndex === index ? "bg-sky-300 text-slate-950" : "border border-white/10 bg-white/[0.04] text-white"}`}
                >
                  {tradeSymbol(trade)}
                </button>
              ))}
            </div>
            {selectedTrade ? (
              <div className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
                <p className="font-semibold text-white">{tradeSymbol(selectedTrade)}</p>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  <InspectorRow label="Closed At" value={formatTime(tradeTimestamp(selectedTrade))} />
                  <InspectorRow label="Side" value={String(selectedTrade.side || selectedTrade.direction || "Unavailable")} />
                  <InspectorRow label="PnL" value={formatValue(selectedTrade.pnl || selectedTrade.profit || selectedTrade.net_pnl)} />
                  <InspectorRow label="Strategy" value={String(selectedTrade.strategy || selectedTrade.strategy_name || matchedPosition?.strategy_name || "Unavailable")} />
                  <InspectorRow label="Matched Live Position" value={matchedPosition ? `${matchedPosition.symbol} ${matchedPosition.direction}` : "None"} />
                  <InspectorRow label="Portfolio Drawdown" value={`${formatValue(live.data.risk_dashboard.current_drawdown_pct)}%`} />
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-400">No trade history is available yet.</p>
            )}
          </div>
        </Panel>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <Panel title="Pending Orders" subtitle="Cancel actions remain guarded by live snapshot freshness and broker health.">
          <div className="space-y-3">
            {live.data.orders.pending.map((order) => (
              <div key={order.id} className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="font-semibold text-white">{order.symbol}</p>
                    <p className="mt-1 text-xs text-slate-400">{formatTime(order.created_at)}</p>
                  </div>
                  <StatusChip label={order.status || "pending"} tone={toneFromStatus(order.status)} />
                </div>
                <div className="mt-3 flex flex-wrap gap-4 text-sm text-slate-300">
                  <span>Volume {formatValue(order.volume)}</span>
                  <span>Entry {formatValue(order.entry_price, 5)}</span>
                  <span>SL {formatValue(order.stop_loss, 5)}</span>
                  <span>TP {formatValue(order.take_profit, 5)}</span>
                </div>
                <button disabled={controlsDisabled} onClick={() => setCancelIntent({ id: order.id, symbol: order.symbol, reason: "" })} className="mt-4 rounded-full border border-white/10 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">Cancel order</button>
              </div>
            ))}
            {!live.data.orders.pending.length ? <p className="text-sm text-slate-400">No pending orders are present.</p> : null}
          </div>
        </Panel>

        <Panel title="Execution and Risk Snapshot" subtitle="Supporting context for decisions made on this page.">
          <div className="grid gap-3 md:grid-cols-2">
            <InspectorRow label="Execution Queue" value={String(live.data.execution_monitor.current_execution_queue.length)} />
            <InspectorRow label="Latency" value={`${formatValue(live.data.execution_monitor.execution_latency_ms)} ms`} />
            <InspectorRow label="Order Status" value={String(live.data.execution_monitor.order_status || "Unavailable")} />
            <InspectorRow label="Broker Response" value={String(live.data.execution_monitor.broker_response || "Unavailable")} />
            <InspectorRow label="Daily Risk" value={formatValue(live.data.risk_dashboard.daily_risk)} />
            <InspectorRow label="Margin Usage" value={`${formatValue(live.data.risk_dashboard.margin_usage_pct)}%`} />
          </div>
        </Panel>
      </div>

      {closeIntent ? (
        <ActionDialog
          title={`Confirm close for ${closeIntent.symbol}`}
          value={closeIntent.reason}
          onChange={(reason) => setCloseIntent({ ...closeIntent, reason })}
          placeholder="Reason for the close request"
          onCancel={() => setCloseIntent(null)}
          onConfirm={() => {
            const position = live.data.positions.items.find((item) => item.id === closeIntent.id);
            if (position) {
              void submitClose(position);
            }
          }}
        />
      ) : null}

      {protectIntent ? (
        <div className="rounded-2xl border border-white/10 bg-slate-950/80 p-4 text-sm text-slate-200">
          <p className="font-semibold text-white">Protect {protectIntent.symbol}</p>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <input value={protectIntent.stopLoss} onChange={(event) => setProtectIntent({ ...protectIntent, stopLoss: event.target.value })} placeholder="Stop loss" className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-white outline-none" />
            <input value={protectIntent.takeProfit} onChange={(event) => setProtectIntent({ ...protectIntent, takeProfit: event.target.value })} placeholder="Take profit" className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-white outline-none" />
          </div>
          <textarea value={protectIntent.reason} onChange={(event) => setProtectIntent({ ...protectIntent, reason: event.target.value })} placeholder="Reason for the protection update" className="mt-3 min-h-20 w-full rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-white outline-none" />
          <div className="mt-3 flex gap-2">
            <button
              onClick={() => {
                const position = live.data.positions.items.find((item) => item.id === protectIntent.id);
                if (position) {
                  void submitProtect(position);
                }
              }}
              className="rounded-full bg-white px-4 py-2 font-semibold text-slate-950"
            >
              Confirm protect
            </button>
            <button onClick={() => setProtectIntent(null)} className="rounded-full border border-white/10 px-4 py-2 font-semibold text-white">Cancel</button>
          </div>
        </div>
      ) : null}

      {cancelIntent ? (
        <ActionDialog
          title={`Confirm order cancel for ${cancelIntent.symbol}`}
          value={cancelIntent.reason}
          onChange={(reason) => setCancelIntent({ ...cancelIntent, reason })}
          placeholder="Reason for the order cancellation"
          onCancel={() => setCancelIntent(null)}
          onConfirm={() => {
            const order = live.data.orders.pending.find((item) => item.id === cancelIntent.id);
            if (order) {
              void submitCancel(order);
            }
          }}
        />
      ) : null}
    </div>
  );
}

function InspectorRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{label}</p>
      <p className="mt-2 text-sm font-medium text-white">{value}</p>
    </div>
  );
}

function ActionDialog({
  title,
  value,
  onChange,
  placeholder,
  onCancel,
  onConfirm,
}: {
  title: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/80 p-4 text-sm text-slate-200">
      <p className="font-semibold text-white">{title}</p>
      <textarea value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} className="mt-3 min-h-20 w-full rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-white outline-none" />
      <div className="mt-3 flex gap-2">
        <button onClick={onConfirm} className="rounded-full bg-white px-4 py-2 font-semibold text-slate-950">Confirm</button>
        <button onClick={onCancel} className="rounded-full border border-white/10 px-4 py-2 font-semibold text-white">Cancel</button>
      </div>
    </div>
  );
}
