import { useQuery, useMutation } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import type { DashboardWidgets, QueryResponse, AnalyticsFilters } from "@/types/analytics";

export function useDashboardWidgets() {
  return useQuery<DashboardWidgets>({
    queryKey: ["analytics-dashboard"],
    queryFn: async () => {
      const res = await authFetch("/api/v1/analytics/dashboard");
      if (!res.ok) throw new Error(`Dashboard fetch failed: ${res.status}`);
      return res.json();
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
    retry: 2,
  });
}

export function useAnalyticsQuery(filters: AnalyticsFilters, enabled: boolean) {
  return useQuery<QueryResponse>({
    queryKey: ["analytics-query", filters],
    queryFn: async () => {
      const body: Record<string, unknown> = {};
      if (filters.entity_types.length > 0) body.entity_types = filters.entity_types;
      if (filters.date_from) body.date_from = filters.date_from;
      if (filters.date_to) body.date_to = filters.date_to;
      if (filters.confidence_min || filters.confidence_max) {
        body.confidence = {};
        if (filters.confidence_min) (body.confidence as Record<string, number>).min = parseFloat(filters.confidence_min);
        if (filters.confidence_max) (body.confidence as Record<string, number>).max = parseFloat(filters.confidence_max);
      }
      const res = await authFetch("/api/v1/analytics/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`Query failed: ${res.status}`);
      return res.json();
    },
    enabled,
    retry: 1,
  });
}

export function useExportAnalytics() {
  return useMutation({
    mutationFn: async ({ filters, format }: { filters: AnalyticsFilters; format: "csv" | "json" }) => {
      const body: Record<string, unknown> = { format };
      if (filters.entity_types.length > 0) body.entity_types = filters.entity_types;
      if (filters.date_from) body.date_from = filters.date_from;
      if (filters.date_to) body.date_to = filters.date_to;
      if (filters.confidence_min || filters.confidence_max) {
        body.confidence = {};
        if (filters.confidence_min) (body.confidence as Record<string, number>).min = parseFloat(filters.confidence_min);
        if (filters.confidence_max) (body.confidence as Record<string, number>).max = parseFloat(filters.confidence_max);
      }
      const res = await authFetch("/api/v1/analytics/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`Export failed: ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `analytics-export.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    },
  });
}

export function useRefreshDashboard() {
  return useMutation({
    mutationFn: async () => {
      const res = await authFetch("/api/v1/analytics/refresh", { method: "POST" });
      if (!res.ok) throw new Error(`Refresh failed: ${res.status}`);
      return res.json();
    },
  });
}
