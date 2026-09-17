"use client";

import { useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import {
  DEFAULT_PROCESSING_MODE,
  type BatchRun,
  type ProcessingMode,
} from "@/types/extraction";

const POLL_INTERVAL_MS = 3000;
const BATCH_RUNS_KEY = ["batch-runs"] as const;

export function useBatchRuns() {
  const queryClient = useQueryClient();

  // A query rather than component state, so returning to the tab renders the cached
  // list at once instead of an empty one while the refetch is in flight.
  const query = useQuery<BatchRun[]>({
    queryKey: BATCH_RUNS_KEY,
    queryFn: async () => {
      const res = await authFetch("/api/v1/extract-batch");
      if (!res.ok) throw new Error(`Failed to load batch runs: ${res.status}`);
      const data = await res.json();
      return (data.runs ?? []) as BatchRun[];
    },
    refetchInterval: (q) =>
      q.state.data?.some((r) => r.status === "running" || r.status === "queued")
        ? POLL_INTERVAL_MS
        : false,
  });

  const triggerBatch = useCallback(
    async (
      documentIds: string[],
      processingMode: ProcessingMode = DEFAULT_PROCESSING_MODE
    ) => {
      // The mode travels in the request body, not in client state: the server decides
      // what a run does and records what it did.
      const res = await authFetch("/api/v1/extract-batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ documentIds, processing_mode: processingMode }),
      });
      // A 422 means the server refused the mode — surfaced to the caller rather than
      // downgraded, and no run is added to the list, because none was created.
      if (!res.ok) {
        const detail = await res
          .json()
          .then((body) => body?.detail)
          .catch(() => null);
        throw new Error(
          typeof detail === "string" ? detail : `Batch trigger failed: ${res.status}`
        );
      }
      const data = await res.json();
      const newRun: BatchRun = {
        run_id: data.run_id,
        status: data.status ?? "queued",
        processing_mode: processingMode,
      };
      // Shown immediately; being `queued`, it also switches polling on, and the next poll
      // replaces it with the server's own record. A list fetch already in flight started
      // before this run existed, so it is cancelled rather than left to overwrite it.
      await queryClient.cancelQueries({ queryKey: BATCH_RUNS_KEY });
      queryClient.setQueryData<BatchRun[]>(BATCH_RUNS_KEY, (prev) => [newRun, ...(prev ?? [])]);
      return newRun;
    },
    [queryClient]
  );

  return {
    runs: query.data ?? [],
    isLoading: query.isLoading,
    error: query.error,
    triggerBatch,
  };
}
