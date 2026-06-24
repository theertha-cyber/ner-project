import { useMutation, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import type { TrainingJob } from "@/types/training-jobs";

export function useCancelTrainingJob() {
  const queryClient = useQueryClient();

  return useMutation<TrainingJob, Error, string>({
    mutationFn: async (jobId) => {
      const res = await authFetch(`/api/v1/training-jobs/${jobId}/cancel`, {
        method: "POST",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `Cancel failed: ${res.status}`);
      }
      return res.json();
    },
    onSuccess: (_data, jobId) => {
      queryClient.invalidateQueries({ queryKey: ["training-jobs"] });
      queryClient.invalidateQueries({ queryKey: ["training-job", jobId] });
    },
  });
}
