export interface JobProgressProps {
  currentEpoch: number | null;
  currentLoss: number | null;
  numEpochs: number;
}

export function JobProgress({ currentEpoch, currentLoss, numEpochs }: JobProgressProps) {
  if (currentEpoch === null) return null;

  const pct = Math.min(Math.max((currentEpoch / numEpochs) * 100, 0), 100);

  return (
    <div
      data-testid="job-progress-callout"
      className="rounded-lg p-4"
      style={{ background: "var(--primary-soft)", border: "1px solid var(--primary-line)" }}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className="inline-block h-2 w-2 rounded-full animate-pulse"
            style={{ background: "var(--primary)" }}
          />
          <span className="font-body text-sm font-semibold" style={{ color: "var(--primary)" }}>
            Fine-tuning in progress
          </span>
        </div>
        <span className="font-mono text-xs" style={{ color: "var(--ink-2)" }}>
          epoch {currentEpoch}/{numEpochs}
        </span>
      </div>

      <div
        className="mt-3 h-2 w-full overflow-hidden rounded-full"
        style={{ background: "var(--surface-3)" }}
      >
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, background: "var(--primary)" }}
        />
      </div>

      <div className="mt-3 flex items-center justify-between font-mono text-xs" style={{ color: "var(--ink-2)" }}>
        <span>loss {currentLoss !== null ? currentLoss.toFixed(4) : "—"}</span>
        <span>epoch {currentEpoch.toFixed(1)}</span>
        <span>GPU worker-2</span>
      </div>
    </div>
  );
}
