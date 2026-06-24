import { useMutation, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import type { TrainingJob } from "@/types/training-jobs";

export function useRejectTrainingJob() {
  const queryClient = useQueryClient();

  return useMutation<TrainingJob, Error, { jobId: string; tenantId: string; reason?: string }>({
    mutationFn: async ({ jobId, tenantId, reason }) => {
      const body = reason !== undefined ? JSON.stringify({ reason }) : undefined;
      const res = await authFetch(
        `/api/v1/training-jobs/${jobId}/reject?tenant_id=${tenantId}`,
        {
          method: "POST",
          headers: body ? { "Content-Type": "application/json" } : undefined,
          body,
        },
      );
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `Reject failed: ${res.status}`);
      }
      return res.json();
    },
    onSuccess: (_data, { jobId }) => {
      queryClient.invalidateQueries({ queryKey: ["training-jobs"] });
      queryClient.invalidateQueries({ queryKey: ["training-job", jobId] });
    },
  });
}
