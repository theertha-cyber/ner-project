"use client";

import { useState, useEffect } from "react";
import { useBatchRuns } from "@/hooks/use-batch-runs";
import { BatchRunCard } from "./BatchRunCard";
import { BatchRunDetail } from "./BatchRunDetail";
import type { BatchRun } from "@/types/extraction";

export function BatchRunsTab() {
  const { runs, triggerBatch } = useBatchRuns();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [triggering, setTriggering] = useState(false);

  // Auto-select the most recent run on mount or when runs change
  useEffect(() => {
    if (runs.length > 0 && !selectedId) {
      setSelectedId(runs[0].run_id);
    }
  }, [runs, selectedId]);

  const selectedRun: BatchRun | undefined =
    runs.find((r) => r.run_id === selectedId);

  async function handleNewBatchRun() {
    setTriggering(true);
    try {
      const newRun = await triggerBatch();
      setSelectedId(newRun.run_id);
    } finally {
      setTriggering(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Header row */}
      <div className="flex items-center justify-between gap-4">
        <span className="font-mono text-xs text-text-secondary">
          POST /api/v1/extract-batch · async via Celery
        </span>
        <button
          type="button"
          disabled={triggering}
          onClick={handleNewBatchRun}
          className="flex items-center gap-1.5 rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white hover:bg-brand-hover disabled:opacity-50 transition-colors"
        >
          ⊕ New batch run
        </button>
      </div>

      {/* Two-column layout */}
      <div style={{ display: "grid", gridTemplateColumns: "340px 1fr", gap: 18 }}>
        {/* Left: run list */}
        <div className="flex flex-col gap-2">
          {runs.length === 0 ? (
            <p className="py-12 text-center text-sm text-text-secondary">
              No batch runs yet. Click "New batch run" to start.
            </p>
          ) : (
            runs.map((run) => (
              <BatchRunCard
                key={run.run_id}
                run={run}
                isSelected={run.run_id === selectedId}
                onClick={() => setSelectedId(run.run_id)}
              />
            ))
          )}
        </div>

        {/* Right: detail panel */}
        <div>
          {selectedRun ? (
            <BatchRunDetail run={selectedRun} />
          ) : (
            <div className="flex items-center justify-center h-48 rounded-xl border border-border">
              <p className="text-sm text-text-secondary">Select a run to view details.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
