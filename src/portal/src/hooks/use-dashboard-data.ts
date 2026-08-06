import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import type { ActivityRow, DashboardActivityResponse, DashboardData, DashboardSummaryResponse } from "@/types/dashboard";

export const GO_HREF: Record<string, string> = {
  training: "/training-jobs",
  annotation: "/annotation",
  documents: "/documents",
  extractions: "/extractions",
  models: "/training-jobs",
  chat: "/chat",
  users: "/users",
  tenants: "/admin/tenants",
};

export function goToHref(go: string, id?: string): string {
  if (go === "chat" && id) return `/chat?conversation=${encodeURIComponent(id)}`;
  return GO_HREF[go] ?? "/dashboard";
}

export function useDashboardData() {
  const { data, isLoading, isError } = useQuery<DashboardSummaryResponse>({
    queryKey: ["dashboard-summary"],
    queryFn: async () => {
      const res = await authFetch("/api/v1/dashboard/summary");
      if (!res.ok) throw new Error(`Dashboard fetch failed: ${res.status}`);
      return res.json();
    },
    refetchInterval: 30_000,
    staleTime: 15_000,
    placeholderData: keepPreviousData,
  });

  return {
    data: data?.data as DashboardData | undefined,
    isLoading,
    isError,
    sources: data?.sources,
  };
}

export function useDashboardActivity(enabled: boolean) {
  const { data, isLoading, isError } = useQuery<DashboardActivityResponse>({
    queryKey: ["dashboard-activity"],
    queryFn: async () => {
      const res = await authFetch("/api/v1/dashboard/activity");
      if (!res.ok) throw new Error(`Dashboard activity fetch failed: ${res.status}`);
      return res.json();
    },
    enabled,
  });

  return {
    rows: (data?.rows as ActivityRow[] | undefined) ?? [],
    isLoading,
    isError,
  };
}
