import { useQuery } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import type { TrainingJob } from "@/types/training-jobs";

export function useTrainingJob(
  id: string | null,
  role?: string,
  tenantId?: string | null,
) {
  return useQuery<TrainingJob>({
    queryKey: ["training-job", id, role === "system_admin" ? tenantId : undefined],
    queryFn: async () => {
      if (!id) throw new Error("No job ID provided");
      const qs = role === "system_admin" && tenantId ? `?tenant_id=${tenantId}` : "";
      const res = await authFetch(`/api/v1/training-jobs/${id}${qs}`);
      if (!res.ok) throw new Error(`Failed to fetch training job: ${res.status}`);
      return res.json();
    },
    refetchInterval: (query) => {
      const job = query.state.data;
      return job?.status === "running" ? 5000 : false;
    },
    enabled: !!id && (role !== "system_admin" || !!tenantId),
  });
}
