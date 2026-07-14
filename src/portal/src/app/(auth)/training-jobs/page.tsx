"use client";

import { useState, useCallback, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useTrainingJobs } from "@/hooks/use-training-jobs";
import { useTrainingJob } from "@/hooks/use-training-job";
import { JobList } from "@/components/training-jobs/job-list";
import { JobFilterTabs } from "@/components/training-jobs/job-filter-tabs";
import type { FilterTab } from "@/components/training-jobs/job-filter-tabs";
import { JobDetailPanel } from "@/components/training-jobs/job-detail-panel";
import { JobActions } from "@/components/training-jobs/job-actions";
import { SubmitJobSlideover } from "@/components/training-jobs/submit-job-slideover";

export default function TrainingJobsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { user } = useAuth();

  const statusParam = searchParams.get("status");
  const selectedParam = searchParams.get("selected");

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

  useEffect(() => {
    if (!listLoading && !selectedJobId && listData?.items.length) {
      handleSelect(listData.items[0].id);
    }
  }, [listLoading, selectedJobId, listData, handleSelect]);

  const isTenantAdmin = user?.role === "tenant_admin";

  return (
    <div className="animate-fade-up flex h-full flex-col">
      {/* Header */}
      <div
        className="flex items-center justify-between px-6 py-3"
        style={{ borderBottom: "1px solid var(--line)" }}
      >
        <div>
          <p
            className="font-mono"
            style={{ fontSize: 11, letterSpacing: "0.06em", color: "var(--ink-3)", marginBottom: 8 }}
          >
            /api/v1/training-jobs
          </p>
          <h1
            className="font-display font-extrabold"
            style={{ fontSize: 34, letterSpacing: "-0.03em", color: "var(--ink)" }}
          >
            Training Jobs
          </h1>
        </div>
        {isTenantAdmin && (
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

      {/* Split panel */}
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
            <div className="px-6 py-3" style={{ borderTop: "1px solid var(--line)" }}>
              <JobActions
                jobId={selectedJob.id}
                status={selectedJob.status}
                tenantId={selectedJob.tenant_id}
              />
            </div>
          )}
        </div>
      </div>

      {/* Submit Slide-over */}
      {isTenantAdmin && <SubmitJobSlideover open={submitOpen} onClose={() => setSubmitOpen(false)} />}
    </div>
  );
}
