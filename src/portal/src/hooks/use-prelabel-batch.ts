"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import type { PrelabelBatch } from "@/types/seed-bootstrap";

async function errorMessage(res: Response, fallback: string): Promise<string> {
  const body = await res.json().catch(() => null);
  const detail = body?.detail ?? body?.error;
  if (typeof detail === "string") return detail;
  return detail?.message ?? `${fallback}: ${res.status}`;
}

/**
 * Submit a document set for batch pre-labeling.
 *
 * One request for the whole set. This is the endpoint change 2's browser loop was deferred to:
 * the loop had no backpressure, no resumability, and lost its progress if the user navigated
 * away, none of which is survivable at 200 documents.
 */
export function useCreatePrelabelBatch() {
  const queryClient = useQueryClient();

  return useMutation<{ batch_id: string; document_count: number }, Error, string[]>({
    mutationFn: async (documentIds) => {
      const res = await authFetch("/api/v1/prelabel-batches", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_ids: documentIds }),
      });
      if (!res.ok) throw new Error(await errorMessage(res, "Batch request failed"));
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prelabel-batch"] });
    },
  });
}

export function usePrelabelBatch(batchId: string | null) {
  return useQuery<PrelabelBatch>({
    queryKey: ["prelabel-batch", batchId],
    enabled: !!batchId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "completed" || status === "failed" ? false : 3000;
    },
    queryFn: async () => {
      const res = await authFetch(`/api/v1/prelabel-batches/${batchId}`);
      if (!res.ok) throw new Error(await errorMessage(res, "Failed to load batch"));
      return res.json();
    },
  });
}
