/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// Minimal operator login widget (2026-07-05). Reuses the existing
// dashboard/rbac.py bearer-token backend as the sole identity source — this
// is a thin client-side form, not a new authentication system. No
// registration, no password reset, no account management: an operator
// token is a single shared credential issued out-of-band by whoever
// configures SVOS_OPERATOR_TOKEN, not a per-user password.

import React, { useState } from "react";
import { LogIn, LogOut, ShieldCheck } from "lucide-react";
import { useSocket } from "../context/SocketContext.js";

export const OperatorLogin: React.FC = () => {
  const { isAuthenticated, operatorActor, login, logout } = useSocket();
  const [open, setOpen] = useState(false);
  const [token, setToken] = useState("");
  const [actor, setActor] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (isAuthenticated) {
    return (
      <div className="flex items-center gap-2 text-xs font-mono">
        <span className="flex items-center gap-1 text-emerald-400" title="Operator session active">
          <ShieldCheck className="w-3.5 h-3.5" /> {operatorActor}
        </span>
        <button
          onClick={logout}
          className="flex items-center gap-1 text-zinc-400 hover:text-white border border-zinc-800 px-2 py-1 rounded-lg transition"
        >
          <LogOut className="w-3 h-3" /> Logout
        </button>
      </div>
    );
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    const result = await login(token, actor);
    setSubmitting(false);
    if (result) {
      setError(result);
    } else {
      setOpen(false);
      setToken("");
    }
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-xs font-bold text-zinc-300 hover:text-white border border-zinc-800 px-3 py-1.5 rounded-xl transition"
      >
        <LogIn className="w-3.5 h-3.5" /> Operator Login
      </button>
      {open && (
        <form
          onSubmit={submit}
          className="absolute right-0 mt-2 w-64 bg-zinc-900 border border-zinc-800 rounded-xl p-3 shadow-xl z-50 flex flex-col gap-2"
        >
          <label className="text-[10px] uppercase tracking-wide text-zinc-500 font-bold">
            Operator token
          </label>
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            className="bg-zinc-950 border border-zinc-800 rounded-lg px-2 py-1.5 text-xs text-white font-mono"
            autoComplete="off"
            required
          />
          <label className="text-[10px] uppercase tracking-wide text-zinc-500 font-bold">
            Actor name
          </label>
          <input
            type="text"
            value={actor}
            onChange={(e) => setActor(e.target.value)}
            placeholder="e.g. jane@ops"
            className="bg-zinc-950 border border-zinc-800 rounded-lg px-2 py-1.5 text-xs text-white font-mono"
            autoComplete="off"
            required
          />
          {error && <p className="text-[11px] text-rose-400">{error}</p>}
          <button
            type="submit"
            disabled={submitting}
            className="mt-1 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-zinc-950 font-bold text-xs py-1.5 rounded-lg transition"
          >
            {submitting ? "Checking..." : "Login"}
          </button>
        </form>
      )}
    </div>
  );
};
