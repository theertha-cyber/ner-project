import type { ModelVersion } from "@/types/model-registry";
import { Badge } from "@/components/ui";

export interface ModelVersionSectionProps {
  model: ModelVersion;
  isActive: boolean;
}

const CORE_METRIC_KEYS = new Set(["eval_f1", "eval_precision", "eval_recall", "eval_loss"]);

export function ModelVersionSection({ model, isActive }: ModelVersionSectionProps) {
  const metrics = model.metrics;
  const perEntityKeys = metrics ? Object.keys(metrics).filter((k) => !CORE_METRIC_KEYS.has(k)) : [];

  return (
    <section>
      <h3 className="mb-2 font-body text-sm font-semibold" style={{ color: "var(--ink-2)" }}>
        Model Version
      </h3>

      <div
        className="rounded-lg p-3"
        style={{ background: "var(--surface-2)", border: "1px solid var(--line)" }}
      >
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-semibold" style={{ color: "var(--ink)" }}>
            {model.run_name ?? `v${model.version_number}`}
          </span>
          <Badge variant={model.status} />
          {isActive && (
            <span className="flex items-center gap-1.5 font-body text-xs" style={{ color: "var(--ink-2)" }}>
              <span className="inline-block h-2 w-2 rounded-full bg-status-promoted" />
              serving
            </span>
          )}
        </div>

        {model.artifact_path && (
          <p className="mt-2 break-all font-mono text-xs" style={{ color: "var(--ink-3)" }}>
            {model.artifact_path}
          </p>
        )}

        {perEntityKeys.length > 0 && (
          <details className="mt-3">
            <summary className="cursor-pointer font-body text-xs font-semibold" style={{ color: "var(--ink-2)" }}>
              Per-Entity Metrics
            </summary>
            <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
              {perEntityKeys.map((key) => (
                <div key={key} className="rounded p-2" style={{ background: "var(--surface-3)" }}>
                  <span className="font-body" style={{ color: "var(--ink-3)" }}>{key}</span>
                  <p className="font-mono font-medium" style={{ color: "var(--ink)" }}>
                    {typeof metrics![key] === "number" ? metrics![key].toFixed(4) : String(metrics![key])}
                  </p>
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
    </section>
  );
}
