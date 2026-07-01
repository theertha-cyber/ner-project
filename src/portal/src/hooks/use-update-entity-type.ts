import { useMutation, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import { useAuth } from "@/lib/auth";
import type { EntityType } from "@/types/entity-types";

export interface UpdateEntityTypePayload {
  description: string;
  examples: string[];
  base_label_mapping: Record<string, string[]>;
  required_flag: boolean;
}

export function useUpdateEntityType() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const tenantSlug = user?.tenantSlug ?? "";

  return useMutation<EntityType, Error, { entityTypeName: string; payload: UpdateEntityTypePayload }>({
    mutationFn: async ({ entityTypeName, payload }) => {
      const res = await authFetch(`/api/v1/tenants/${tenantSlug}/entity-types/${entityTypeName}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `Update failed: ${res.status}`);
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity-types", tenantSlug] });
    },
  });
}
