import { useMutation, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import { useAuth } from "@/lib/auth";

export function useToggleEntityType() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const tenantSlug = user?.tenantSlug ?? "";

  return useMutation<void, Error, { name: string; is_active: boolean }>({
    mutationFn: async ({ name, is_active }) => {
      const res = await authFetch(`/api/v1/tenants/${tenantSlug}/entity-types/${name}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `Toggle failed: ${res.status}`);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity-types", tenantSlug] });
    },
    onError: () => {
      queryClient.invalidateQueries({ queryKey: ["entity-types", tenantSlug] });
    },
  });
}
