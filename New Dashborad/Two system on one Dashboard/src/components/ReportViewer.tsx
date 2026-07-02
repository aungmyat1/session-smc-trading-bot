import React from "react";
import type { ReportDetail } from "../types.js";
import { Panel, formatTime } from "./opsShared.js";

export function ReportViewer({
  report,
  loading,
  error,
  emptyMessage,
}: {
  report: ReportDetail | null;
  loading: boolean;
  error: string;
  emptyMessage: string;
}) {
  return (
    <Panel title="Report Viewer" subtitle="Markdown evidence is loaded directly from the backend report index.">
      {loading ? <p className="text-sm text-slate-300">Loading report content.</p> : null}
      {!loading && error ? <div className="rounded-2xl border border-rose-300/20 bg-rose-300/10 px-4 py-3 text-sm text-rose-100">{error}</div> : null}
      {!loading && !error && !report ? <p className="text-sm text-slate-400">{emptyMessage}</p> : null}
      {!loading && !error && report ? (
        <div className="space-y-3">
          <div className="rounded-2xl border border-white/8 bg-white/[0.04] p-4">
            <p className="font-semibold text-white">{report.title || report.report_id || "Report"}</p>
            <p className="mt-1 text-xs text-slate-400">{formatTime(report.generated_at || report.created_at)}</p>
          </div>
          <pre className="max-h-[32rem] overflow-auto rounded-2xl border border-white/8 bg-slate-950/80 p-4 text-xs leading-6 text-slate-200 whitespace-pre-wrap">
            {report.content}
          </pre>
        </div>
      ) : null}
    </Panel>
  );
}
