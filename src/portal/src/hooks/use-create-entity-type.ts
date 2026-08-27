import { useMutation, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import { useAuth } from "@/lib/auth";
import type { EntityCardinality, EntityType } from "@/types/entity-types";

// `sql_identifier` is deliberately absent: it is system-assigned at create and never changed,
// so the client has nothing to say about it. `cardinality` and `value_kind` are here because
// they decide which generated relation an entity type's values land in and what type the
// column carries — without them every entity type is `multi` and `text` forever.
export interface CreateEntityTypePayload {
  name: string;
  description: string;
  examples: string[];
  base_label_mapping: Record<string, string[]>;
  required_flag: boolean;
  cardinality: EntityCardinality;
  value_kind: string;
}

export function useCreateEntityType() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const tenantSlug = user?.tenantSlug ?? "";

  return useMutation<EntityType, Error, CreateEntityTypePayload>({
    mutationFn: async (payload) => {
      const res = await authFetch(`/api/v1/tenants/${tenantSlug}/entity-types`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `Create failed: ${res.status}`);
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entity-types", tenantSlug] });
    },
  });
}
