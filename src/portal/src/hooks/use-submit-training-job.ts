import { useMutation, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import type { SubmitJobPayload, TrainingJob } from "@/types/training-jobs";

export function useSubmitTrainingJob() {
  const queryClient = useQueryClient();

  return useMutation<TrainingJob, Error, SubmitJobPayload>({
    mutationFn: async (payload) => {
      const res = await authFetch("/api/v1/training-jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `Submission failed: ${res.status}`);
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["training-jobs"] });
    },
  });
}
