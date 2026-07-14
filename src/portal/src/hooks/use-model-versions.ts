import { useQuery } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import { useAuth } from "@/lib/auth";
import type { ModelVersionListResponse, ActiveModelResponse } from "@/types/model-registry";

export function useModelVersions(role?: string, tenantId?: string | null) {
  const { user } = useAuth();
  const tenantSlug = user?.tenantSlug ?? "";
  const isSystemAdmin = role === "system_admin";
  const qs = isSystemAdmin && tenantId ? `?tenant_id=${tenantId}` : "";

  const listQuery = useQuery<ModelVersionListResponse>({
    queryKey: ["models", isSystemAdmin ? tenantId : tenantSlug],
    queryFn: async () => {
      const res = await authFetch(`/api/v1/models${qs}`);
      if (!res.ok) throw new Error(`Failed to fetch models: ${res.status}`);
      return res.json();
    },
    enabled: !isSystemAdmin || !!tenantId,
  });

  const activeQuery = useQuery<ActiveModelResponse>({
    queryKey: ["models", "active", isSystemAdmin ? tenantId : tenantSlug],
    queryFn: async () => {
      const res = await authFetch(`/api/v1/models/active${qs}`);
      if (!res.ok) throw new Error(`Failed to fetch active model: ${res.status}`);
      return res.json();
    },
    enabled: !isSystemAdmin || !!tenantId,
  });

  return {
    data: listQuery.data?.items,
    isLoading: listQuery.isLoading,
    isError: listQuery.isError,
    activeModel: activeQuery.data?.model,
    isActiveLoading: activeQuery.isLoading,
  };
}
