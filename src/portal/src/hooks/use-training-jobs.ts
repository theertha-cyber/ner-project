import { useQuery } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import type { TrainingJobListResponse } from "@/types/training-jobs";

export function useTrainingJobs(statusFilter?: string) {
  const params = new URLSearchParams();
  if (statusFilter) params.set("status", statusFilter);
  params.set("page", "1");
  params.set("per_page", "50");
  const qs = params.toString();

  return useQuery<TrainingJobListResponse>({
    queryKey: ["training-jobs", statusFilter ?? "all"],
    queryFn: async () => {
      const res = await authFetch(`/api/v1/training-jobs?${qs}`);
      if (!res.ok) throw new Error(`Failed to fetch training jobs: ${res.status}`);
      return res.json();
    },
  });
}
