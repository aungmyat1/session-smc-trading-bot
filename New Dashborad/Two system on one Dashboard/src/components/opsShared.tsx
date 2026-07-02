import React from "react";

export function Panel({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
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

export function MetricCard({ label, value, accent = "text-white", detail }: { label: string; value: string; accent?: string; detail?: string }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
      <p className="text-[11px] uppercase tracking-[0.24em] text-slate-400">{label}</p>
      <p className={`mt-3 text-2xl font-semibold ${accent}`}>{value}</p>
      {detail ? <p className="mt-2 text-xs text-slate-400">{detail}</p> : null}
    </div>
  );
}

export function StatusChip({ label, tone = "slate" }: { label: string; tone?: "emerald" | "amber" | "rose" | "sky" | "slate" }) {
  const tones = {
    emerald: "border-emerald-300/25 bg-emerald-300/10 text-emerald-100",
    amber: "border-amber-300/25 bg-amber-300/10 text-amber-100",
    rose: "border-rose-300/25 bg-rose-300/10 text-rose-100",
    sky: "border-sky-300/25 bg-sky-300/10 text-sky-100",
    slate: "border-white/10 bg-white/[0.04] text-slate-200",
  };

  return <span className={`inline-flex rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${tones[tone]}`}>{label}</span>;
}

export function formatValue(value: unknown, digits = 2): string {
  if (value === null || value === undefined || value === "") {
    return "Unavailable";
  }
  if (typeof value === "number") {
    return value.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });
  }

  const numeric = Number(value);
  if (!Number.isNaN(numeric) && String(value).trim() !== "") {
    return numeric.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });
  }

  return String(value);
}

export function formatTime(value: unknown): string {
  if (!value) {
    return "Unavailable";
  }
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return `${date.toISOString().slice(0, 10)} ${date.toISOString().slice(11, 19)} UTC`;
}

export function toneFromStatus(value: unknown): "emerald" | "amber" | "rose" | "sky" | "slate" {
  const text = String(value || "").toUpperCase();
  if (!text) {
    return "slate";
  }
  if (["PASS", "CLEAR", "HEALTHY", "CONNECTED", "READY", "APPROVED", "ACTIVE", "COMPLETED"].some((token) => text.includes(token))) {
    return "emerald";
  }
  if (["FAIL", "DENIED", "BLOCKED", "DEGRADED", "DISCONNECTED", "STOP", "CRITICAL", "ERROR"].some((token) => text.includes(token))) {
    return "rose";
  }
  if (["WARN", "WARNING", "REVIEW", "PENDING", "UNKNOWN", "STALE"].some((token) => text.includes(token))) {
    return "amber";
  }
  return "sky";
}
