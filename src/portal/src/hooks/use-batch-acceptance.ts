"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import type {
  AcceptanceReviewResult,
  BatchAcceptance,
  SuggestionDisposition,
} from "@/types/seed-bootstrap";

async function errorMessage(res: Response, fallback: string): Promise<string> {
  const body = await res.json().catch(() => null);
  const detail = body?.detail ?? body?.error;
  if (typeof detail === "string") return detail;
  return detail?.message ?? `${fallback}: ${res.status}`;
}

/**
 * Open the acceptance review, drawing the sample server-side.
 *
 * The client neither chooses the sample nor knows how it was drawn, and that is the point: a
 * reviewer picking which documents to check produces an agreement rate that measures the
 * reviewer, not the batch.
 */
export function useStartAcceptanceReview() {
  const queryClient = useQueryClient();

  return useMutation<BatchAcceptance, Error, string>({
    mutationFn: async (batchId) => {
      const res = await authFetch(`/api/v1/prelabel-batches/${batchId}/acceptance`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(await errorMessage(res, "Could not start review"));
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["batch-acceptance"] });
    },
  });
}

export function useBatchAcceptance(batchId: string | null, enabled = true) {
  return useQuery<BatchAcceptance>({
    queryKey: ["batch-acceptance", batchId],
    enabled: !!batchId && enabled,
    retry: false,
    queryFn: async () => {
      const res = await authFetch(`/api/v1/prelabel-batches/${batchId}/acceptance`);
      if (!res.ok) throw new Error(await errorMessage(res, "Failed to load review"));
      return res.json();
    },
  });
}

export interface SubmitReviewPayload {
  batchId: string;
  dispositions: { suggestion_id: string; disposition: SuggestionDisposition }[];
}

/**
 * Record the dispositions and read back the rate they produce.
 *
 * Separate from accepting on purpose: the reviewer sees what their own review measured, and the
 * measurement is stored, before anything is promoted or refused.
 */
export function useSubmitAcceptanceReview() {
  const queryClient = useQueryClient();

  return useMutation<AcceptanceReviewResult, Error, SubmitReviewPayload>({
    mutationFn: async ({ batchId, dispositions }) => {
      const res = await authFetch(`/api/v1/prelabel-batches/${batchId}/acceptance/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dispositions }),
      });
      if (!res.ok) throw new Error(await errorMessage(res, "Review submission failed"));
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["batch-acceptance"] });
    },
  });
}

/**
 * Accept the batch.
 *
 * A refusal here is an ordinary error, not an exception to handle specially: a sub-threshold
 * batch promotes nothing, and the message carries the measured rate so the screen can say why.
 */
export function useAcceptBatch() {
  const queryClient = useQueryClient();

  return useMutation<{ promoted_spans: number; agreement_rate: number }, Error, string>({
    mutationFn: async (batchId) => {
      const res = await authFetch(`/api/v1/prelabel-batches/${batchId}/acceptance/accept`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(await errorMessage(res, "Acceptance failed"));
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["batch-acceptance"] });
      queryClient.invalidateQueries({ queryKey: ["prelabel-batch"] });
      // Bulk promotion creates confirmed spans, which is what the readiness report counts.
      queryClient.invalidateQueries({ queryKey: ["training-readiness"] });
    },
  });
}
