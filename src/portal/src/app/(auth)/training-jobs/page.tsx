"use client";

import { useState, useCallback, useEffect, useMemo } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useTrainingJobs } from "@/hooks/use-training-jobs";
import { useTrainingJob } from "@/hooks/use-training-job";
import { JobList } from "@/components/training-jobs/job-list";
import { JobFilterTabs } from "@/components/training-jobs/job-filter-tabs";
import type { FilterTab } from "@/components/training-jobs/job-filter-tabs";
import { JobDetailPanel } from "@/components/training-jobs/job-detail-panel";
import { JobActions } from "@/components/training-jobs/job-actions";
import { ModelActions } from "@/components/training-jobs/model-actions";
import { SubmitJobSlideover } from "@/components/training-jobs/submit-job-slideover";
import { BaseModelCard, BASE_MODEL_ID } from "@/components/training-jobs/base-model-card";
import { BaseModelPanel } from "@/components/training-jobs/base-model-panel";
import { ModelVersionCard } from "@/components/training-jobs/model-version-card";
import { ModelDetailPanel } from "@/components/training-jobs/model-detail-panel";
import { useModelVersions } from "@/hooks/use-model-versions";
import type { ModelVersion } from "@/types/model-registry";

type ViewMode = "jobs" | "models";

export default function TrainingJobsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { user } = useAuth();

  const view: ViewMode = searchParams.get("view") === "models" ? "models" : "jobs";
  const statusParam = searchParams.get("status");
  const selectedParam = searchParams.get("selected");
  const selectedModelId = searchParams.get("model");

  const currentTab: FilterTab = (statusParam as FilterTab) ?? "all";
  const selectedJobId = selectedParam;

  const [submitOpen, setSubmitOpen] = useState(false);

  const { data: listData, isLoading: listLoading } = useTrainingJobs(
    currentTab === "all" ? undefined : currentTab,
  );

  const selectedRowTenantId =
    listData?.items.find((job) => job.id === selectedJobId)?.tenant_id ?? null;

  const { data: selectedJob, isLoading: detailLoading, isError: detailError } =
    useTrainingJob(selectedJobId, user?.role, selectedRowTenantId);

  const { data: jobModelVersions } = useModelVersions(user?.role, selectedJob?.tenant_id);
  const selectedJobModel = jobModelVersions?.find((v) => v.training_job_id === selectedJob?.id);

  // Independent registry of all model versions for this tenant, browsable regardless
  // of whether a version is linked to a training job (legacy/orphaned versions included).
  const { data: allModelVersions, isLoading: modelsLoading, activeModel } = useModelVersions();

  const isBaseSelected = selectedModelId === BASE_MODEL_ID;

  const sortedModels = useMemo<ModelVersion[]>(
    () => [...(allModelVersions ?? [])].sort((a, b) => b.version_number - a.version_number),
    [allModelVersions],
  );
  const selectedModel = sortedModels.find((m) => m.id === selectedModelId) ?? null;
  const showBaseModel = user?.role === "system_admin" || activeModel?.version_number === 0;

  const handleTabChange = useCallback(
    (tab: FilterTab) => {
      const params = new URLSearchParams(searchParams.toString());
      if (tab === "all") {
        params.delete("status");
      } else {
        params.set("status", tab);
      }
      params.delete("selected");
      router.replace(`/training-jobs?${params.toString()}`);
    },
    [searchParams, router],
  );

  const handleSelect = useCallback(
    (id: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("selected", id);
      router.replace(`/training-jobs?${params.toString()}`);
    },
    [searchParams, router],
  );

  const handleSelectModel = useCallback(
    (id: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("model", id);
      router.replace(`/training-jobs?${params.toString()}`);
    },
    [searchParams, router],
  );

  const handleViewChange = useCallback(
    (next: ViewMode) => {
      const params = new URLSearchParams(searchParams.toString());
      if (next === "jobs") {
        params.delete("view");
      } else {
        params.set("view", "models");
      }
      router.replace(`/training-jobs?${params.toString()}`);
    },
    [searchParams, router],
  );

  useEffect(() => {
    if (view === "jobs" && !listLoading && !selectedParam && listData?.items.length) {
      handleSelect(listData.items[0].id);
    }
  }, [view, listLoading, selectedParam, listData, handleSelect]);

  const isTenantAdmin = user?.role === "tenant_admin";

  return (
    <div className="animate-fade-up flex h-full flex-col">
      {/* Header */}
      <div
        className="flex items-center justify-between pl-3 pr-6 py-3"
        style={{ borderBottom: "1px solid var(--line)" }}
      >
        <div
          className="flex gap-1 rounded-xl p-1"
          style={{ background: "var(--surface-2)", border: "1px solid var(--line)" }}
        >
          {(["jobs", "models"] as const).map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => handleViewChange(mode)}
              className="font-display font-bold transition-all"
              style={{
                padding: "9px 18px",
                borderRadius: 9,
                fontSize: 14,
                background: view === mode ? "var(--primary)" : "transparent",
                color: view === mode ? "#fff" : "var(--ink-2)",
                boxShadow: view === mode ? "0 6px 16px -6px var(--primary)" : "none",
              }}
            >
              {mode === "jobs" ? "Training Jobs" : "Model Versions"}
            </button>
          ))}
        </div>
        {isTenantAdmin && view === "jobs" && (
          <button
            type="button"
            onClick={() => setSubmitOpen(true)}
            className="font-display font-bold text-white"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "11px 17px",
              borderRadius: 12,
              background: "var(--primary)",
              fontSize: 14,
              boxShadow: "0 8px 20px -8px var(--primary)",
            }}
          >
            + Submit job
          </button>
        )}
      </div>

      {view === "jobs" ? (
        <div className="flex flex-1 overflow-hidden">
          {/* Left: List */}
          <div className="flex w-80 flex-col" style={{ borderRight: "1px solid var(--line)" }}>
            <div className="p-3">
              <JobFilterTabs selected={currentTab} onChange={handleTabChange} />
            </div>
            <div className="flex-1 overflow-y-auto px-3 pb-3">
              <JobList
                jobs={listData?.items ?? []}
                selectedId={selectedJobId}
                onSelect={handleSelect}
                isLoading={listLoading}
              />
            </div>
          </div>

          {/* Right: Detail */}
          <div className="flex flex-1 flex-col overflow-y-auto">
            <div className="flex-1 p-6">
              <JobDetailPanel
                job={selectedJob}
                isLoading={detailLoading}
                isError={detailError}
                hasSelection={!!selectedJobId}
                viewerRole={user?.role}
              />
            </div>

            {/* Actions */}
            {selectedJob && (
              <div
                className="flex flex-wrap items-center gap-2 px-6 py-3"
                style={{ borderTop: "1px solid var(--line)" }}
              >
                <JobActions
                  jobId={selectedJob.id}
                  status={selectedJob.status}
                  tenantId={selectedJob.tenant_id}
                />
                <ModelActions model={selectedJobModel} />
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="flex flex-1 overflow-hidden">
          {/* Left: Model version list */}
          <div className="flex w-80 flex-col overflow-y-auto" style={{ borderRight: "1px solid var(--line)" }}>
            <div className="flex flex-col gap-2 p-3">
              {modelsLoading && (
                <>
                  {[0, 1, 2].map((i) => (
                    <div
                      key={i}
                      className="h-16 w-full animate-pulse rounded-lg"
                      style={{ background: "var(--surface-3)" }}
                    />
                  ))}
                </>
              )}

              {!modelsLoading &&
                sortedModels.map((model) => (
                  <ModelVersionCard
                    key={model.id}
                    model={model}
                    isActive={activeModel?.id === model.id}
                    isSelected={selectedModelId === model.id}
                    onClick={() => handleSelectModel(model.id)}
                  />
                ))}

              {!modelsLoading && showBaseModel && (
                <BaseModelCard
                  isActive={activeModel?.version_number === 0}
                  isSelected={isBaseSelected}
                  onClick={() => handleSelectModel(BASE_MODEL_ID)}
                />
              )}
            </div>
          </div>

          {/* Right: Model detail */}
          <div className="flex flex-1 flex-col overflow-y-auto">
            <div className="flex-1 p-6">
              {isBaseSelected ? <BaseModelPanel /> : <ModelDetailPanel model={selectedModel} />}
            </div>

            {!isBaseSelected && selectedModel && (
              <div
                className="flex flex-wrap items-center gap-2 px-6 py-3"
                style={{ borderTop: "1px solid var(--line)" }}
              >
                <ModelActions model={selectedModel} />
              </div>
            )}
          </div>
        </div>
      )}

      {/* Submit Slide-over */}
      {isTenantAdmin && <SubmitJobSlideover open={submitOpen} onClose={() => setSubmitOpen(false)} />}
    </div>
  );
}
