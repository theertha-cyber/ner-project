"use client";

import { useState, useEffect } from "react";
import { useBatchRuns } from "@/hooks/use-batch-runs";
import { useModelVersions } from "@/hooks/use-model-versions";
import { BatchRunCard } from "./BatchRunCard";
import { BatchRunDetail } from "./BatchRunDetail";
import { BaseModelConfirmDialog } from "./BaseModelConfirmDialog";
import { BatchDocumentSelectModal } from "./BatchDocumentSelectModal";
import type { BatchRun } from "@/types/extraction";

export function BatchRunsTab() {
  const { runs, triggerBatch } = useBatchRuns();
  const { activeModel, data: modelVersions } = useModelVersions();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [showBaseModelConfirm, setShowBaseModelConfirm] = useState(false);
  const [showDocumentSelect, setShowDocumentSelect] = useState(false);

  // Auto-select the most recent run on mount or when runs change
  useEffect(() => {
    if (runs.length > 0 && !selectedId) {
      setSelectedId(runs[0].run_id);
    }
  }, [runs, selectedId]);

  const selectedRun: BatchRun | undefined =
    runs.find((r) => r.run_id === selectedId);

  function modelLabelFor(modelVersion: string | null | undefined): string | null {
    if (!modelVersion) return null;
    const match = modelVersions?.find((v) => v.version_number === Number(modelVersion));
    return match?.run_name ?? `v${modelVersion}`;
  }

  async function handleRunExtraction(documentIds: string[]) {
    setTriggering(true);
    try {
      const newRun = await triggerBatch(documentIds);
      setSelectedId(newRun.run_id);
    } finally {
      setTriggering(false);
    }
  }

  function handleNewBatchRunClick() {
    if (activeModel?.version_number === 0) {
      setShowBaseModelConfirm(true);
      return;
    }
    setShowDocumentSelect(true);
  }

  return (
    <div className="flex flex-col gap-4" style={{ width: "100%", height: "100%", minHeight: 0 }}>
      {/* Header row */}
      <div className="flex items-center justify-end gap-4" style={{ flexShrink: 0 }}>
        <button
          type="button"
          disabled={triggering}
          onClick={handleNewBatchRunClick}
          className="flex items-center gap-1.5 rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white hover:bg-brand-hover disabled:opacity-50 transition-colors"
        >
          ⊕ New batch run
        </button>
      </div>

      {showBaseModelConfirm && (
        <BaseModelConfirmDialog
          onConfirm={() => {
            setShowBaseModelConfirm(false);
            setShowDocumentSelect(true);
          }}
          onCancel={() => setShowBaseModelConfirm(false)}
        />
      )}

      {showDocumentSelect && (
        <BatchDocumentSelectModal
          onConfirm={(documentIds) => {
            setShowDocumentSelect(false);
            handleRunExtraction(documentIds);
          }}
          onCancel={() => setShowDocumentSelect(false)}
        />
      )}

      {/* Two-column layout */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "340px 1fr",
          gap: 18,
          flex: 1,
          minHeight: 0,
        }}
      >
        {/* Left: run list — bounded height, scrolls independently of the page */}
        <div className="flex flex-col gap-2 overflow-y-auto" style={{ height: "100%" }}>
          {runs.length === 0 ? (
            <p className="py-12 text-center text-sm text-text-secondary">
              No batch runs yet. Click &quot;New batch run&quot; to start.
            </p>
          ) : (
            runs.map((run) => (
              <BatchRunCard
                key={run.run_id}
                run={run}
                modelLabel={modelLabelFor(run.model_version)}
                isSelected={run.run_id === selectedId}
                onClick={() => setSelectedId(run.run_id)}
              />
            ))
          )}
        </div>

        {/* Right: detail panel */}
        <div style={{ height: "100%", overflowY: "auto" }}>
          {selectedRun ? (
            <BatchRunDetail run={selectedRun} modelLabel={modelLabelFor(selectedRun.model_version)} />
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
