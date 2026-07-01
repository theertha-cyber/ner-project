import { useQuery } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import { useAuth } from "@/lib/auth";
import type { EntityTypeListResponse } from "@/types/entity-types";

export function useEntityTypes() {
  const { user } = useAuth();
  const tenantSlug = user?.tenantSlug ?? "";

  return useQuery<EntityTypeListResponse>({
    queryKey: ["entity-types", tenantSlug],
    enabled: !!tenantSlug,
    queryFn: async () => {
      const res = await authFetch(`/api/v1/tenants/${tenantSlug}/entity-types`);
      if (!res.ok) throw new Error(`Failed to fetch entity types: ${res.status}`);
      return res.json();
    },
  });
}
