import type { ModelVersion } from "@/types/model-registry";
import { Badge } from "@/components/ui";

export interface ModelVersionCardProps {
  model: ModelVersion;
  isActive: boolean;
  isSelected: boolean;
  onClick: () => void;
}

export function ModelVersionCard({ model, isActive, isSelected, onClick }: ModelVersionCardProps) {
  const f1 = model.metrics?.eval_f1;
  const f1Label = f1 != null ? f1.toFixed(2) : "—";

  const dateStr = model.created_at
    ? new Date(model.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
    : null;

  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full rounded-lg p-3 text-left transition-colors"
      style={{
        border: `1px solid ${isSelected ? "var(--primary-line)" : "var(--line)"}`,
        background: isSelected ? "var(--primary-soft)" : "var(--surface-2)",
      }}
    >
      <div className="mb-1.5 flex items-center gap-2">
        <span className="font-mono text-xs font-semibold" style={{ color: "var(--ink)" }}>
          {model.run_name ?? `v${model.version_number}`}
        </span>
        <div className="flex-1" />
        {isActive && <span className="inline-block h-2 w-2 rounded-full bg-status-promoted" />}
        <Badge variant={model.status} />
      </div>
      <div className="flex items-center justify-between font-mono text-xs" style={{ color: "var(--ink-3)" }}>
        <span>F1 {model.status === "training" ? "—" : f1Label}</span>
        {dateStr && <span>{dateStr}</span>}
      </div>
    </button>
  );
}
