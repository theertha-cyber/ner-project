import { useMutation, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import { useAuth } from "@/lib/auth";

export function useWarmupModel() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const tenantSlug = user?.tenantSlug ?? "";

  return useMutation<void, Error, { modelId: string }>({
    mutationFn: async ({ modelId }) => {
      const res = await authFetch(`/api/v1/models/${modelId}/warmup`, { method: "POST" });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `Warmup failed: ${res.status}`);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["models", tenantSlug] });
    },
  });
}
