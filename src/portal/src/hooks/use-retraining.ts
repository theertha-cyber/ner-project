"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import type {
  PromotionEvidence,
  RetrainRequestResult,
  RetrainingDecision,
} from "@/types/human-gated-retraining";

async function errorMessage(res: Response, fallback: string): Promise<string> {
  const body = await res.json().catch(() => null);
  const detail = body?.detail ?? body?.error;
  if (typeof detail === "string") return detail;
  return detail?.message ?? `${fallback}: ${res.status}`;
}

/**
 * Evidence for the retrain decision: how much has accumulated, against which version, and
 * whether a run is already under way.
 *
 * Separate from `useReviewAccumulation`, which backs the card on the review queue screen. Same
 * underlying figure, different question: that card tells a reviewer their work is being counted,
 * this one gives a Tenant Admin what a retrain decision needs. Fetching one and deriving the
 * other would tie a screen's refresh policy to another screen's.
 */
export function useRetrainingDecision() {
  return useQuery<RetrainingDecision>({
    queryKey: ["retraining-decision"],
    queryFn: async () => {
      const res = await authFetch("/api/v1/retraining-decision");
      if (!res.ok) throw new Error(await errorMessage(res, "Failed to load retraining decision"));
      return res.json();
    },
  });
}

/**
 * Request a retrain.
 *
 * Creates an ordinary training job awaiting System Admin approval. Nothing is queued and nothing
 * trains until a System Admin approves it and sets the hyperparameters — this button asks, it
 * does not start.
 *
 * The zero-accumulation warning arrives as a header rather than in the body, because the body is
 * the ordinary training job and the warning is about the decision, not about the job.
 */
export function useRequestRetrain() {
  const queryClient = useQueryClient();

  return useMutation<RetrainRequestResult, Error, void>({
    mutationFn: async () => {
      const res = await authFetch("/api/v1/training-retrain-requests", { method: "POST" });
      if (!res.ok) throw new Error(await errorMessage(res, "Could not request a retrain"));
      const job = await res.json();
      return {
        ...job,
        warnedNoAccumulation: res.headers.get("X-Retrain-Warning") === "no-accumulated-spans",
      };
    },
    onSuccess: () => {
      // The new job is in flight, which the decision surface reports.
      queryClient.invalidateQueries({ queryKey: ["retraining-decision"] });
      queryClient.invalidateQueries({ queryKey: ["training-jobs"] });
    },
  });
}

/**
 * A completed version's metrics beside the serving version's.
 *
 * Read-only, and it promotes nothing. Promotion remains the existing control on the models
 * screen, unchanged; this only gives that decision something to be made on beyond the fact that
 * a run finished.
 */
export function usePromotionEvidence(versionNumber: number | null) {
  return useQuery<PromotionEvidence>({
    queryKey: ["promotion-evidence", versionNumber],
    enabled: versionNumber !== null,
    queryFn: async () => {
      const res = await authFetch(`/api/v1/training-promotion-evidence/${versionNumber}`);
      if (!res.ok) throw new Error(await errorMessage(res, "Failed to load promotion evidence"));
      return res.json();
    },
  });
}
