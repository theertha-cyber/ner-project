export interface JobMetricsProps {
  metrics: Record<string, number>;
}

const STAT_KEYS = [
  { key: "eval_f1", label: "f1" },
  { key: "eval_precision", label: "precision" },
  { key: "eval_recall", label: "recall" },
] as const;

export function JobMetrics({ metrics }: JobMetricsProps) {
  const statEntries = STAT_KEYS.filter(({ key }) => typeof metrics[key] === "number");
  const evalLoss = metrics.eval_loss;

  if (statEntries.length === 0 && typeof evalLoss !== "number") return null;

  return (
    <div>
      <h4 className="mb-2 font-body text-sm font-medium" style={{ color: "var(--ink-2)" }}>
        Evaluation Metrics
      </h4>
      <div className="grid grid-cols-3 gap-3">
        {statEntries.map(({ key, label }) => {
          const value = metrics[key];
          const pct = Math.min(Math.max(value * 100, 0), 100);
          return (
            <div key={key}>
              <p className="font-mono text-2xl font-semibold" style={{ color: "var(--ink)" }}>
                {value.toFixed(2)}
              </p>
              <p className="font-body text-xs uppercase tracking-wide" style={{ color: "var(--ink-3)" }}>
                {label}
              </p>
              <div
                className="mt-1 h-1.5 w-full overflow-hidden rounded-full"
                style={{ background: "var(--surface-3)" }}
              >
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${pct}%`, background: "var(--primary)" }}
                />
              </div>
            </div>
          );
        })}
      </div>
      {typeof evalLoss === "number" && (
        <p className="mt-3 font-mono text-xs" style={{ color: "var(--ink-2)" }}>
          eval_loss {evalLoss.toFixed(3)}
        </p>
      )}
    </div>
  );
}
