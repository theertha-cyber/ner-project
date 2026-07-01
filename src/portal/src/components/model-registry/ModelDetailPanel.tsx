"use client";

import type { ModelVersion } from "@/types/model-registry";
import { Spinner } from "@/components/ui";
import { useToast } from "@/hooks";
import { usePromoteModel } from "@/hooks/use-promote-model";
import { useDemoteModel } from "@/hooks/use-demote-model";
import { useWarmupModel } from "@/hooks/use-warmup-model";

export interface ModelDetailPanelProps {
  model: ModelVersion | null;
  role: string;
}

const CORE_METRIC_KEYS = new Set(["eval_f1", "eval_precision", "eval_recall", "eval_loss"]);
const CONLL_LABELS = ["PER", "ORG", "LOC", "MISC"];

export function ModelDetailPanel({ model, role }: ModelDetailPanelProps) {
  const { toast } = useToast();
  const promoteMutation = usePromoteModel();
  const demoteMutation = useDemoteModel();
  const warmupMutation = useWarmupModel();

  const isTenantAdmin = role === "tenant_admin";

  if (!model) {
    return (
      <div className="flex h-full items-center justify-center py-12">
        <p className="text-sm text-gray-400">Select a model version to view details</p>
      </div>
    );
  }

  const isBaseModel = model.version_number === 0;
  const metrics = model.metrics;
  const perEntityKeys = metrics
    ? Object.keys(metrics).filter((k) => !CORE_METRIC_KEYS.has(k))
    : [];

  function handlePromote() {
    promoteMutation.mutate(
      { modelId: model!.id },
      {
        onSuccess: () => toast("Model promoted successfully"),
        onError: (err) => toast(err.message, "bad"),
      },
    );
  }

  function handleDemote() {
    demoteMutation.mutate(
      { modelId: model!.id },
      {
        onSuccess: () => toast("Model demoted successfully"),
        onError: (err) => toast(err.message, "bad"),
      },
    );
  }

  function handleWarmup() {
    warmupMutation.mutate(
      { modelId: model!.id },
      {
        onSuccess: () => toast("Warmup triggered successfully"),
        onError: (err) => toast(err.message, "bad"),
      },
    );
  }

  const canPromote = !isBaseModel && isTenantAdmin && model.status === "completed";
  const canDemote = !isBaseModel && isTenantAdmin && model.status === "promoted";
  const canWarmup = !isBaseModel && isTenantAdmin;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900">
          {isBaseModel ? "Base Model" : `v${model.version_number}`}
        </h2>
        {isBaseModel ? (
          <p className="font-mono text-xs text-gray-500">dslim/bert-base-NER</p>
        ) : (
          <p className="text-xs text-gray-400">Training job: {model.training_job_id}</p>
        )}
      </div>

      {/* Base model: supported labels */}
      {isBaseModel && (
        <section>
          <h3 className="mb-2 text-sm font-semibold text-gray-700">Supported Labels</h3>
          <div className="flex flex-wrap gap-1.5">
            {CONLL_LABELS.map((label) => (
              <span
                key={label}
                className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-700"
              >
                {label}
              </span>
            ))}
          </div>
          <p className="mt-2 text-xs text-gray-400">
            Shared base model — no fine-tuning required. Serves all tenants until a custom model is promoted.
          </p>
        </section>
      )}

      {/* Metrics grid */}
      {metrics && (
        <section>
          <h3 className="mb-2 text-sm font-semibold text-gray-700">Evaluation Metrics</h3>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="rounded bg-gray-50 p-2">
              <span className="text-gray-500">F1</span>
              <p className="font-medium text-gray-900">{metrics.eval_f1.toFixed(4)}</p>
            </div>
            <div className="rounded bg-gray-50 p-2">
              <span className="text-gray-500">Precision</span>
              <p className="font-medium text-gray-900">{metrics.eval_precision.toFixed(4)}</p>
            </div>
            <div className="rounded bg-gray-50 p-2">
              <span className="text-gray-500">Recall</span>
              <p className="font-medium text-gray-900">{metrics.eval_recall.toFixed(4)}</p>
            </div>
            <div className="rounded bg-gray-50 p-2">
              <span className="text-gray-500">Loss</span>
              <p className="font-medium text-gray-900">{metrics.eval_loss.toFixed(4)}</p>
            </div>
          </div>
        </section>
      )}

      {/* Per-entity metrics */}
      {perEntityKeys.length > 0 && (
        <details>
          <summary className="cursor-pointer text-sm font-semibold text-gray-700">
            Per-Entity Metrics
          </summary>
          <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
            {perEntityKeys.map((key) => (
              <div key={key} className="rounded bg-gray-50 p-2">
                <span className="text-gray-500">{key}</span>
                <p className="font-medium text-gray-900">{metrics![key].toFixed(4)}</p>
              </div>
            ))}
          </div>
        </details>
      )}

      {/* MLflow link */}
      {model.mlflow_run_url && (
        <section>
          <h3 className="mb-1 text-sm font-semibold text-gray-700">MLflow Run</h3>
          <a
            href={model.mlflow_run_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-brand-primary underline hover:text-brand-primary/80"
          >
            View in MLflow
          </a>
        </section>
      )}

      {/* Artifact path */}
      {model.artifact_path && (
        <section>
          <h3 className="mb-1 text-sm font-semibold text-gray-700">Artifact Path</h3>
          <code className="break-all font-mono text-xs text-gray-700">{model.artifact_path}</code>
        </section>
      )}

      {/* Actions */}
      {(canPromote || canDemote || canWarmup) && (
        <section className="flex flex-wrap gap-2 border-t border-border pt-4">
          {canPromote && (
            <button
              type="button"
              onClick={handlePromote}
              disabled={promoteMutation.isPending}
              className="flex items-center gap-1.5 rounded-lg bg-brand-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-primary/80 disabled:opacity-50"
            >
              {promoteMutation.isPending && <Spinner size="sm" />}
              Promote
            </button>
          )}
          {canDemote && (
            <button
              type="button"
              onClick={handleDemote}
              disabled={demoteMutation.isPending}
              className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              {demoteMutation.isPending && <Spinner size="sm" />}
              Demote
            </button>
          )}
          {canWarmup && (
            <button
              type="button"
              onClick={handleWarmup}
              disabled={warmupMutation.isPending}
              className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              {warmupMutation.isPending && <Spinner size="sm" />}
              Warmup
            </button>
          )}
        </section>
      )}
    </div>
  );
}
