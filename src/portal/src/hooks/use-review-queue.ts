"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import type {
  AccumulationReport,
  ResolveQueuedPredictionPayload,
  ReviewOutcome,
  ReviewQueuePage,
} from "@/types/confidence-review";

async function errorMessage(res: Response, fallback: string): Promise<string> {
  const body = await res.json().catch(() => null);
  const detail = body?.detail ?? body?.error;
  if (typeof detail === "string") return detail;
  return detail?.message ?? `${fallback}: ${res.status}`;
}

/**
 * The low-confidence predictions waiting for review.
 *
 * Server-paged. The client does not filter the list: which predictions are review work is
 * decided by the review threshold at routing time, and a client-side filter would let the screen
 * disagree with the queue about what is waiting.
 */
export function useReviewQueue(limit = 50, offset = 0) {
  return useQuery<ReviewQueuePage>({
    queryKey: ["review-queue", limit, offset],
    queryFn: async () => {
      const res = await authFetch(`/api/v1/review-queue?limit=${limit}&offset=${offset}`);
      if (!res.ok) throw new Error(await errorMessage(res, "Failed to load review queue"));
      return res.json();
    },
  });
}

/**
 * Record one reviewer's decision.
 *
 * The route is not sent. This surface *is* the human route, and the server stamps it — a
 * client-supplied route would let the browser decide what the agreement comparison measures.
 */
export function useResolveQueuedPrediction() {
  const queryClient = useQueryClient();

  return useMutation<ReviewOutcome, Error, ResolveQueuedPredictionPayload>({
    mutationFn: async ({ predictionId, ...body }) => {
      const res = await authFetch(`/api/v1/review-queue/${predictionId}/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await errorMessage(res, "Could not record the review"));
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["review-queue"] });
      // A confirmed or corrected outcome creates a span, which is what accumulation counts.
      queryClient.invalidateQueries({ queryKey: ["review-accumulation"] });
    },
  });
}

/**
 * How much reviewed material has accumulated since the serving model was trained.
 *
 * Deliberately a separate query from `training-readiness`, and rendered separately. Accumulation
 * is a delta since a specific version was trained; readiness is a per-entity-type count against
 * ADR-010's threshold. Fetching them together would invite a screen that adds them up.
 */
export function useReviewAccumulation() {
  return useQuery<AccumulationReport>({
    queryKey: ["review-accumulation"],
    queryFn: async () => {
      const res = await authFetch("/api/v1/review-accumulation");
      if (!res.ok) throw new Error(await errorMessage(res, "Failed to load accumulation"));
      return res.json();
    },
  });
}
