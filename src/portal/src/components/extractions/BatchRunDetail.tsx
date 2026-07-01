import type { BatchRun, BatchRunStatus } from "@/types/extraction";

const STATUS_STYLE: Record<BatchRunStatus, string> = {
  completed: "bg-status-completed text-white",
  running: "bg-warning text-white",
  queued: "bg-warning text-white",
  failed: "bg-status-failed text-white",
};

function progressPct(run: BatchRun): number {
  const total = run.total_documents ?? 0;
  const processed = run.processed_count ?? 0;
  if (total === 0) return 0;
  return Math.round((processed / total) * 100);
}

export interface BatchRunDetailProps {
  run: BatchRun;
}

export function BatchRunDetail({ run }: BatchRunDetailProps) {
  const pct = progressPct(run);

  return (
    <div className="rounded-xl border border-border bg-surface-raised p-6 flex flex-col gap-5 h-full"
      style={{ boxShadow: "var(--shadow-card)" }}>
      {/* Header row */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="font-mono text-sm text-text-primary">{run.run_id}</span>
        <span
          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLE[run.status] ?? "bg-gray-200 text-gray-700"}`}
        >
          {run.status}
        </span>
        {run.model_version && (
          <span className="text-xs text-text-secondary font-mono">
            model v{run.model_version}
          </span>
        )}
      </div>

      {/* Large percentage */}
      <div
        className="font-display font-extrabold leading-none"
        style={{ fontSize: 46, color: "var(--primary)" }}
      >
        {pct}%
      </div>

      {/* Progress bar */}
      <div className="h-2 rounded-full bg-border overflow-hidden">
        <div
          className="h-full rounded-full bg-brand-primary transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-4 gap-3">
        <StatCell label="TOTAL" value={run.total_documents ?? 0} color="text-text-primary" />
        <StatCell label="PROCESSED" value={run.processed_count ?? 0} color="text-success" />
        <StatCell label="SKIPPED" value={run.skipped_count ?? 0} color="text-warning" />
        <StatCell label="FAILED" value={run.failed_count ?? 0} color="text-error" />
      </div>
    </div>
  );
}

function StatCell({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="rounded-lg border border-border p-3 flex flex-col gap-1">
      <span className="font-mono text-[10px] font-semibold text-text-secondary tracking-widest uppercase">
        {label}
      </span>
      <span className={`text-2xl font-bold ${color}`}>{value}</span>
    </div>
  );
}
