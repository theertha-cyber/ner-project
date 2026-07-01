import { useQuery } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import { useAuth } from "@/lib/auth";
import type { ModelVersionListResponse, ActiveModelResponse } from "@/types/model-registry";

export function useModelVersions() {
  const { user } = useAuth();
  const tenantSlug = user?.tenantSlug ?? "";

  const listQuery = useQuery<ModelVersionListResponse>({
    queryKey: ["models", tenantSlug],
    queryFn: async () => {
      const res = await authFetch("/api/v1/models");
      if (!res.ok) throw new Error(`Failed to fetch models: ${res.status}`);
      return res.json();
    },
  });

  const activeQuery = useQuery<ActiveModelResponse>({
    queryKey: ["models", "active", tenantSlug],
    queryFn: async () => {
      const res = await authFetch("/api/v1/models/active");
      if (!res.ok) throw new Error(`Failed to fetch active model: ${res.status}`);
      return res.json();
    },
  });

  return {
    data: listQuery.data?.items,
    isLoading: listQuery.isLoading,
    isError: listQuery.isError,
    activeModel: activeQuery.data?.model,
    isActiveLoading: activeQuery.isLoading,
  };
}
