import type { ModelVersion } from "@/types/model-registry";
import { Badge } from "@/components/ui";

export interface ModelDetailPanelProps {
  model: ModelVersion | null;
}

const CORE_METRIC_KEYS = new Set(["eval_f1", "eval_precision", "eval_recall", "eval_loss"]);

function truncateUrl(url: string, max = 44): string {
  return url.length > max ? `${url.slice(0, max)}…` : url;
}

export function ModelDetailPanel({ model }: ModelDetailPanelProps) {
  if (!model) {
    return (
      <div
        className="rounded-lg p-4"
        style={{ background: "var(--surface-3)", border: "1px solid var(--line)" }}
      >
        <p className="font-body text-sm" style={{ color: "var(--ink-3)" }}>
          Select a model version to view details
        </p>
      </div>
    );
  }

  const metrics = model.metrics;
  const perEntityKeys = metrics ? Object.keys(metrics).filter((k) => !CORE_METRIC_KEYS.has(k)) : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <span className="font-mono text-base font-semibold" style={{ color: "var(--ink)" }}>
          {model.run_name ?? `v${model.version_number}`}
        </span>
        <Badge variant={model.status} />
        <div className="flex-1" />
        <span className="font-mono text-xs" style={{ color: "var(--ink-3)" }}>
          Training job: {model.training_job_id || "—"}
        </span>
      </div>

      {/* Metrics grid */}
      {metrics && (
        <section>
          <h3 className="mb-2 font-body text-sm font-semibold" style={{ color: "var(--ink-2)" }}>
            Evaluation Metrics
          </h3>
          <div className="grid grid-cols-4 gap-2 text-xs">
            {(
              [
                ["F1", metrics.eval_f1],
                ["Precision", metrics.eval_precision],
                ["Recall", metrics.eval_recall],
                ["Loss", metrics.eval_loss],
              ] as const
            ).map(([label, value]) => (
              <div key={label} className="rounded p-2" style={{ background: "var(--surface-3)" }}>
                <span className="font-body" style={{ color: "var(--ink-3)" }}>{label}</span>
                <p className="font-mono font-medium" style={{ color: "var(--ink)" }}>
                  {typeof value === "number" ? value.toFixed(4) : "—"}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Per-entity metrics */}
      {perEntityKeys.length > 0 && (
        <details>
          <summary className="cursor-pointer font-body text-sm font-semibold" style={{ color: "var(--ink-2)" }}>
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

      {/* MLflow link */}
      {model.mlflow_run_url && (
        <section>
          <h3 className="mb-1 font-body text-sm font-semibold" style={{ color: "var(--ink-2)" }}>
            MLflow Run
          </h3>
          <a
            href={model.mlflow_run_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-lg p-3 transition-colors"
            style={{ background: "var(--surface-2)", border: "1px solid var(--line)" }}
          >
            <span aria-hidden="true">⎘</span>
            <div className="min-w-0">
              <p className="font-body text-sm font-medium" style={{ color: "var(--ink)" }}>MLflow run</p>
              <p className="truncate font-mono text-xs" style={{ color: "var(--ink-3)" }}>
                {truncateUrl(model.mlflow_run_url)}
              </p>
            </div>
          </a>
        </section>
      )}

      {/* Artifact path */}
      {model.artifact_path && (
        <section>
          <h3 className="mb-1 font-body text-sm font-semibold" style={{ color: "var(--ink-2)" }}>
            Artifact Path
          </h3>
          <code className="break-all font-mono text-xs" style={{ color: "var(--ink-2)" }}>
            {model.artifact_path}
          </code>
        </section>
      )}
    </div>
  );
}
