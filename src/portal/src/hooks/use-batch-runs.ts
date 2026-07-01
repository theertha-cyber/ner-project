"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { authFetch } from "@/lib/auth-fetch";
import type { BatchRun } from "@/types/extraction";

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
    return () => {
      Object.values(intervalsRef.current).forEach(clearInterval);
    };
  }, []);

  const triggerBatch = useCallback(async () => {
    const res = await authFetch("/api/v1/extract-batch", { method: "POST" });
    if (!res.ok) throw new Error(`Batch trigger failed: ${res.status}`);
    const data = await res.json();
    const newRun: BatchRun = {
      run_id: data.run_id,
      status: data.status ?? "queued",
    };
    setRuns((prev) => [newRun, ...prev]);
    startPolling(data.run_id);
    return newRun;
  }, []);

  return { runs, triggerBatch };
}
