import { useQuery } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  status: string;
}

export interface TenantsResponse {
  tenants: Tenant[];
  total: number;
  page: number;
  per_page: number;
}

export function useTenants() {
  return useQuery<TenantsResponse>({
    queryKey: ["tenants", { forFilter: true }],
    queryFn: async () => {
      const res = await authFetch("/api/v1/admin/tenants?per_page=100");
      if (!res.ok) throw new Error(`Failed to fetch tenants: ${res.status}`);
      return res.json();
    },
  });
}
