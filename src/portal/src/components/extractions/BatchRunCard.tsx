import type { BatchRun, BatchRunStatus } from "@/types/extraction";

const STATUS_STYLE: Record<BatchRunStatus, string> = {
  completed: "bg-status-completed text-white",
  running: "bg-status-running text-white",
  queued: "bg-status-queued text-white",
  failed: "bg-status-failed text-white",
};

function progressPct(run: BatchRun): number {
  const total = run.total_documents ?? 0;
  const processed = run.processed_count ?? 0;
  if (total === 0) return 0;
  return Math.round((processed / total) * 100);
}

export interface BatchRunCardProps {
  run: BatchRun;
  isSelected: boolean;
  onClick: () => void;
}

export function BatchRunCard({ run, isSelected, onClick }: BatchRunCardProps) {
  const pct = progressPct(run);
  const dateStr = run.started_at
    ? new Date(run.started_at).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";

  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "w-full rounded-xl border p-4 text-left transition-colors",
        isSelected
          ? "border-brand-primary bg-brand-primary/5"
          : "border-border hover:border-brand-primary/40",
      ].join(" ")}
    >
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="font-mono text-xs text-text-primary truncate">{run.run_id}</span>
        <span
          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[run.status] ?? "bg-gray-200 text-gray-700"}`}
        >
          {run.status}
        </span>
      </div>

      <div className="h-1.5 rounded-full bg-border overflow-hidden mb-2">
        <div
          className="h-full rounded-full bg-brand-primary transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>

      <div className="flex items-center justify-between text-xs text-text-secondary">
        <span>
          {pct}% docs{run.model_version ? ` · model v${run.model_version}` : ""}
        </span>
        {dateStr && <span>{dateStr}</span>}
      </div>
    </button>
  );
}
