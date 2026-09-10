"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import type { BatchKind, PrelabelBatch } from "@/types/seed-bootstrap";

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
export interface CreateBatchPayload {
  documentIds: string[];
  /** `initial` (≤5 docs, Tenant-Admin reviewed) or `large` (main batch, Annotator reviewed). */
  batchKind: BatchKind;
}

export function useCreatePrelabelBatch() {
  const queryClient = useQueryClient();

  return useMutation<
    { batch_id: string; document_count: number; batch_kind: BatchKind; guidance_applied: boolean },
    Error,
    CreateBatchPayload
  >({
    mutationFn: async ({ documentIds, batchKind }) => {
      const res = await authFetch("/api/v1/prelabel-batches", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_ids: documentIds, batch_kind: batchKind }),
      });
      if (!res.ok) throw new Error(await errorMessage(res, "Batch request failed"));
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prelabel-batch"] });
    },
  });
}

export interface RecordGuidancePayload {
  batchId: string;
  documentId: string;
  correctedSpans?: { text: string; entity_type: string }[];
  note?: string;
}

/** Persist a Tenant Admin's corrections/note from reviewing one document of an `initial`
 * batch; folded into the prompt when the subsequent `large` batch runs. */
export function useRecordBatchGuidance() {
  const queryClient = useQueryClient();

  return useMutation<unknown, Error, RecordGuidancePayload>({
    mutationFn: async ({ batchId, documentId, correctedSpans, note }) => {
      const res = await authFetch(`/api/v1/prelabel-batches/${batchId}/guidance`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          document_id: documentId,
          corrected_spans: correctedSpans ?? [],
          ...(note ? { note } : {}),
        }),
      });
      if (!res.ok) throw new Error(await errorMessage(res, "Could not save guidance"));
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prelabel-batch"] });
    },
  });
}

export interface PrelabelBatchSummary {
  batch_id: string;
  status: string;
  state: import("@/types/seed-bootstrap").BatchState | null;
  batch_kind: BatchKind;
  annotator_review_status: string | null;
  training_eligible_at: string | null;
  created_at: string | null;
  acceptance_decision: "in_review" | "accepted" | "rejected" | null;
}

/** Every batch for the tenant, newest first — drives the automated stepper's step states. */
export function usePrelabelBatches(enabled = true) {
  return useQuery<{ batches: PrelabelBatchSummary[] }>({
    queryKey: ["prelabel-batches"],
    enabled,
    queryFn: async () => {
      const res = await authFetch("/api/v1/prelabel-batches");
      if (!res.ok) throw new Error(`Failed to load batches: ${res.status}`);
      return res.json();
    },
  });
}

export function usePrelabelBatch(batchId: string | null) {
  return useQuery<PrelabelBatch>({
    queryKey: ["prelabel-batch", batchId],
    enabled: !!batchId,
    refetchInterval: (query) => {
      const state = query.state.data?.state;
      return state === "completed" || state === "partially_completed" || state === "failed"
        ? false
        : 3000;
    },
    queryFn: async () => {
      const res = await authFetch(`/api/v1/prelabel-batches/${batchId}`);
      if (!res.ok) throw new Error(await errorMessage(res, "Failed to load batch"));
      return res.json();
    },
  });
}
