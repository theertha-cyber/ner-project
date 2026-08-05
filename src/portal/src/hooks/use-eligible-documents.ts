import { useQuery } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import type { EligibleDocumentListResponse } from "@/types/extraction";

export function useEligibleDocuments(enabled: boolean) {
  const query = useQuery<EligibleDocumentListResponse>({
    queryKey: ["extract-batch", "eligible-documents"],
    queryFn: async () => {
      const res = await authFetch("/api/v1/extract-batch/eligible-documents");
      if (!res.ok) throw new Error(`Failed to fetch eligible documents: ${res.status}`);
      return res.json();
    },
    enabled,
  });

  return {
    documents: query.data?.documents ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
  };
}
