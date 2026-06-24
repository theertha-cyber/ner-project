"use client";

import { useState, useCallback } from "react";
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

  const { data: selectedJob, isLoading: detailLoading, isError: detailError } =
    useTrainingJob(selectedJobId);

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

  const tenantId = user?.tenantId ?? "";

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-6 py-3">
        <h1 className="text-xl font-semibold text-gray-900">Training Jobs</h1>
        <button
          type="button"
          onClick={() => setSubmitOpen(true)}
          className="rounded-lg bg-brand-primary px-4 py-2 text-sm font-medium text-white hover:bg-brand-primary/80"
        >
          + Submit Job
        </button>
      </div>

      {/* Split panel */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: List */}
        <div className="flex w-80 flex-col border-r border-border">
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
            />
          </div>

          {/* Actions */}
          {selectedJob && (
            <div className="border-t border-border px-6 py-3">
              <JobActions
                jobId={selectedJob.id}
                status={selectedJob.status}
                tenantId={tenantId}
              />
            </div>
          )}
        </div>
      </div>

      {/* Submit Slide-over */}
      <SubmitJobSlideover open={submitOpen} onClose={() => setSubmitOpen(false)} />
    </div>
  );
}
