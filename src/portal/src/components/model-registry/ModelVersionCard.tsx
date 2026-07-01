"use client";

import type { ModelVersion } from "@/types/model-registry";
import { Badge } from "@/components/ui";

export interface ModelVersionCardProps {
  model: ModelVersion;
  isActive: boolean;
  isSelected: boolean;
  onSelect: () => void;
}

export function ModelVersionCard({ model, isActive, isSelected, onSelect }: ModelVersionCardProps) {
  const isBaseModel = model.version_number === 0;
  const f1 = model.metrics?.eval_f1;
  const f1Label = f1 != null ? f1.toFixed(2) : "—";

  const dateStr = model.created_at
    ? new Date(model.created_at).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : null;

  return (
    <button
      type="button"
      onClick={onSelect}
      className={[
        "w-full rounded-lg border p-3 text-left transition-colors",
        isSelected
          ? "border-brand-primary bg-brand-primary/5"
          : "border-border hover:border-brand-primary/50",
      ].join(" ")}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold text-gray-900">
          {model.version_number === 0 ? "Base Model" : `v${model.version_number}`}
        </span>
        <div className="flex items-center gap-1.5">
          {isActive && (
            <span className="inline-block h-2 w-2 rounded-full bg-status-promoted" />
          )}
          <Badge variant={model.status} />
        </div>
      </div>
      <div className="mt-1.5 flex items-center justify-between text-xs text-gray-500">
        {isBaseModel ? (
          <span className="italic">dslim/bert-base-NER</span>
        ) : (
          <>
            <span>F1 {model.status === "training" ? "—" : f1Label}</span>
            {dateStr && <span>{dateStr}</span>}
          </>
        )}
      </div>
    </button>
  );
}
