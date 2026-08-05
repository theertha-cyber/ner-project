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

  function toggle(id: string, alreadyExtracted: boolean) {
    if (alreadyExtracted) return;
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function handleConfirm() {
    if (selected.size === 0) return;
    onConfirm(Array.from(selected));
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    >
      <div className="w-full max-w-md rounded-xl border border-border bg-surface-raised p-5 flex flex-col gap-4 max-h-[80vh]">
        <h2 className="text-sm font-semibold text-text-primary">Select documents to extract</h2>

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
                  doc.already_extracted ? "opacity-50" : "hover:bg-surface",
                ].join(" ")}
              >
                <input
                  type="checkbox"
                  checked={selected.has(doc.id)}
                  disabled={doc.already_extracted}
                  onChange={() => toggle(doc.id, doc.already_extracted)}
                />
                <span className="flex-1 text-text-primary">{doc.filename}</span>
                {doc.already_extracted && (
                  <span className="text-xs text-text-secondary">already processed</span>
                )}
              </label>
            ))
          )}
        </div>

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
            disabled={selected.size === 0}
            onClick={handleConfirm}
            className="rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white hover:bg-brand-hover disabled:opacity-50"
          >
            Run extraction
          </button>
        </div>
      </div>
    </div>
  );
}
