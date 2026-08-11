"use client";

import { useState } from "react";
import { useEligibleDocuments } from "@/hooks/use-eligible-documents";

export interface BatchDocumentSelectModalProps {
  onConfirm: (documentIds: string[]) => void;
  onCancel: () => void;
}

export function BatchDocumentSelectModal({ onConfirm, onCancel }: BatchDocumentSelectModalProps) {
  const { documents, isLoading } = useEligibleDocuments(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  // Already-extracted documents are never selectable, so every selection path
  // below derives from this list rather than from `documents` — a disabled
  // document's id has no route into `selected` at all.
  const selectable = documents.filter((doc) => !doc.already_extracted);
  const selectedIds = selectable.filter((doc) => selected.has(doc.id)).map((doc) => doc.id);
  const allSelected = selectable.length > 0 && selectedIds.length === selectable.length;

  function toggle(id: string, alreadyExtracted: boolean) {
    if (alreadyExtracted) return;
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    setSelected((prev) => {
      const next = new Set(prev);
      for (const doc of selectable) {
        if (allSelected) next.delete(doc.id);
        else next.add(doc.id);
      }
      return next;
    });
  }

  function handleConfirm() {
    if (selectedIds.length === 0) return;
    onConfirm(selectedIds);
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    >
      <div className="w-full max-w-md rounded-xl border border-border bg-surface-raised p-5 flex flex-col gap-4 max-h-[80vh]">
        <h2 className="text-sm font-semibold text-text-primary">Select documents to extract</h2>

        <label
          className={[
            "flex items-center gap-2 rounded-lg px-3 py-2 text-sm",
            selectable.length === 0 ? "opacity-50 cursor-not-allowed" : "hover:bg-surface",
          ].join(" ")}
        >
          <input
            type="checkbox"
            checked={allSelected}
            disabled={selectable.length === 0}
            onChange={toggleAll}
          />
          <span className="flex-1 font-semibold text-text-primary">Select all</span>
        </label>

        <div className="flex flex-col gap-1 overflow-y-auto">
          {isLoading ? (
            <p className="py-8 text-center text-sm text-text-secondary">Loading documents…</p>
          ) : documents.length === 0 ? (
            <p className="py-8 text-center text-sm text-text-secondary">No eligible documents found.</p>
          ) : (
            documents.map((doc) => (
              <label
                key={doc.id}
                className={[
                  "flex items-center gap-2 rounded-lg px-3 py-2 text-sm",
                  doc.already_extracted ? "opacity-50 cursor-not-allowed" : "hover:bg-surface",
                ].join(" ")}
              >
                <input
                  type="checkbox"
                  checked={selected.has(doc.id) && !doc.already_extracted}
                  disabled={doc.already_extracted}
                  onChange={() => toggle(doc.id, doc.already_extracted)}
                />
                <span className="min-w-0 flex-1 truncate text-text-primary">{doc.filename}</span>
                {doc.already_extracted && (
                  <span className="shrink-0 text-xs text-text-secondary">processed</span>
                )}
              </label>
            ))
          )}
        </div>

        <div className="flex items-center justify-between gap-2">
          <p className="text-xs text-text-secondary">
            {selectedIds.length} {selectedIds.length === 1 ? "document" : "documents"} selected
          </p>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onCancel}
              className="rounded-lg border border-border px-4 py-2 text-sm font-semibold text-text-primary hover:bg-surface"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={selectedIds.length === 0}
              onClick={handleConfirm}
              className="rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white hover:bg-brand-hover disabled:opacity-50"
            >
              Run extraction
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
