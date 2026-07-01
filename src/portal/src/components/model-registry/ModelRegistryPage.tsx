"use client";

import { useState, useMemo } from "react";
import { useAuth } from "@/lib/auth";
import { useModelVersions } from "@/hooks/use-model-versions";
import type { ModelVersion } from "@/types/model-registry";
import { ModelVersionCard } from "./ModelVersionCard";
import { ModelDetailPanel } from "./ModelDetailPanel";

const BASE_MODEL_ID = "v0-base";

function buildBaseModelEntry(activeModel: ModelVersion | null | undefined): ModelVersion {
  if (activeModel?.version_number === 0) return activeModel;
  return {
    id: BASE_MODEL_ID,
    version_number: 0,
    status: "archived",
    training_job_id: "",
    created_at: "",
    metrics: null,
    mlflow_run_id: null,
    mlflow_run_url: null,
    artifact_path: null,
  };
}

export function ModelRegistryPage() {
  const { user } = useAuth();
  const { data, isLoading, activeModel } = useModelVersions();
  const [selectedModel, setSelectedModel] = useState<ModelVersion | null>(null);

  const role = user?.role ?? "business_user";

  const displayedModels = useMemo<ModelVersion[]>(() => {
    const fineTuned = isLoading ? [] : [...(data ?? [])].sort((a, b) => b.version_number - a.version_number);
    return [...fineTuned, buildBaseModelEntry(activeModel)];
  }, [data, isLoading, activeModel]);

  const versionCount = displayedModels.length;

  return (
    <div className="animate-fade-up flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-border px-6 py-3">
        <p className="text-xs font-medium text-gray-400">GET /api/v1/models</p>
        <h1 className="text-xl font-semibold text-gray-900">Model Registry</h1>
        {!isLoading && (
          <p className="text-xs text-gray-500">{versionCount} version{versionCount !== 1 ? "s" : ""}</p>
        )}
      </div>

      {/* Split panel */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Card list */}
        <div className="flex w-80 flex-col border-r border-border overflow-y-auto">
          <div className="flex flex-col gap-2 p-3">
            {isLoading && (
              <>
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    className="h-16 w-full animate-pulse rounded-lg bg-gray-100"
                  />
                ))}
              </>
            )}

            {displayedModels.map((model) => (
              <ModelVersionCard
                key={model.id}
                model={model}
                isActive={activeModel?.id === model.id || (model.version_number === 0 && activeModel?.version_number === 0)}
                isSelected={selectedModel?.id === model.id}
                onSelect={() => setSelectedModel(model)}
              />
            ))}
          </div>
        </div>

        {/* Right: Detail panel */}
        <div className="flex-1 overflow-y-auto p-6">
          <ModelDetailPanel model={selectedModel} role={role} />
        </div>
      </div>
    </div>
  );
}
