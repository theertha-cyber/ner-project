import { useQuery } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import type { DocumentListResponse } from "@/types/documents";

export function useDocuments(page: number, perPage: number = 25, status?: string) {
  const params = new URLSearchParams();
  params.set("page", String(page));
  params.set("per_page", String(perPage));
  if (status && status !== "all") params.set("status", status);
  const qs = params.toString();

  return useQuery<DocumentListResponse>({
    queryKey: ["documents", { page, perPage, status: status ?? "all" }],
    queryFn: async () => {
      const res = await authFetch(`/api/v1/documents?${qs}`);
      if (!res.ok) throw new Error(`Failed to fetch documents: ${res.status}`);
      return res.json();
    },
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data?.documents) return false;
      const hasInflight = data.documents.some(
        (doc) => doc.status === "pending" || doc.status === "processing",
      );
      return hasInflight ? 3000 : false;
    },
    placeholderData: (prev) => prev,
  });
}
