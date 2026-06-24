import { useQuery } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import type { TrainingJob } from "@/types/training-jobs";

export function useTrainingJob(id: string | null) {
  return useQuery<TrainingJob>({
    queryKey: ["training-job", id],
    queryFn: async () => {
      if (!id) throw new Error("No job ID provided");
      const res = await authFetch(`/api/v1/training-jobs/${id}`);
      if (!res.ok) throw new Error(`Failed to fetch training job: ${res.status}`);
      return res.json();
    },
    refetchInterval: (query) => {
      const job = query.state.data;
      return job?.status === "running" ? 5000 : false;
    },
    enabled: !!id,
  });
}
