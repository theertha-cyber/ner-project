"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { authFetch } from "@/lib/auth-fetch";
import {
  DEFAULT_PROCESSING_MODE,
  type BatchRun,
  type ProcessingMode,
} from "@/types/extraction";

const POLL_INTERVAL_MS = 3000;

export function useBatchRuns() {
  const [runs, setRuns] = useState<BatchRun[]>([]);
  const intervalsRef = useRef<Record<string, ReturnType<typeof setInterval>>>({});

  function startPolling(runId: string) {
    if (intervalsRef.current[runId]) return;
    const id = setInterval(async () => {
      try {
        const res = await authFetch(`/api/v1/extract-batch/${runId}`);
        if (!res.ok) return;
        const data = await res.json();
        setRuns((prev) =>
          prev.map((r) => (r.run_id === runId ? { ...r, ...data, run_id: runId } : r))
        );
        if (data.status === "completed" || data.status === "failed") {
          clearInterval(intervalsRef.current[runId]);
          delete intervalsRef.current[runId];
        }
      } catch {
        // swallow network errors during polling
      }
    }, POLL_INTERVAL_MS);
    intervalsRef.current[runId] = id;
  }

  useEffect(() => {
    authFetch("/api/v1/extract-batch")
      .then((r) => r.json())
      .then((data) => {
        const loaded: BatchRun[] = data.runs ?? [];
        setRuns(loaded);
        loaded
          .filter((r) => r.status === "running" || r.status === "queued")
          .forEach((r) => startPolling(r.run_id));
      })
      .catch(() => {});

    return () => {
      Object.values(intervalsRef.current).forEach(clearInterval);
    };
  // startPolling is stable (defined in module scope relative to the ref) — no dep needed
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
      setRuns((prev) => [newRun, ...prev]);
      startPolling(data.run_id);
      return newRun;
    },
    []
  );

  return { runs, triggerBatch };
}
