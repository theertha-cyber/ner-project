import { useMutation, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import { useAuth } from "@/lib/auth";
import type { ModelVersion } from "@/types/model-registry";

export function usePromoteModel() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const tenantSlug = user?.tenantSlug ?? "";

  return useMutation<ModelVersion, Error, { modelId: string }>({
    mutationFn: async ({ modelId }) => {
      const res = await authFetch(`/api/v1/models/${modelId}/promote`, { method: "POST" });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `Promote failed: ${res.status}`);
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["models", tenantSlug] });
      queryClient.invalidateQueries({ queryKey: ["models", "active", tenantSlug] });
    },
  });
}
