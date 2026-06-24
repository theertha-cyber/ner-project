export interface JobMetricsProps {
  metrics: Record<string, number>;
}

const F1_THRESHOLD = 0.7;

function barColor(value: number): string {
  return value >= F1_THRESHOLD ? "bg-status-completed" : "bg-status-failed";
}

export function JobMetrics({ metrics }: JobMetricsProps) {
  const entries = Object.entries(metrics).filter(
    ([key]) => !key.startsWith("eval_"),
  );

  if (entries.length === 0) return null;

  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium text-gray-700">Evaluation Metrics</h4>
      {entries.map(([key, value]) => {
        const pct = Math.min(Math.max(value * 100, 0), 100);
        return (
          <div key={key}>
            <div className="flex items-center justify-between text-xs text-gray-600">
              <span>{key}</span>
              <span>{(value * 100).toFixed(1)}%</span>
            </div>
            <div className="mt-0.5 h-2 w-full overflow-hidden rounded-full bg-gray-200">
              <div
                className={`h-full rounded-full transition-all ${barColor(value)}`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
