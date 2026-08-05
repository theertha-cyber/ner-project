"use client";

import { useEffect } from "react";
import { DocumentUpload } from "./DocumentUpload";

interface UploadDialogProps {
  open: boolean;
  onClose: () => void;
  allowPurposeSelection?: boolean;
}

export function UploadDialog({ open, onClose, allowPurposeSelection = true }: UploadDialogProps) {
  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-6 pt-24"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-lg border p-5 shadow-xl"
        style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold" style={{ color: "var(--ink)" }}>Upload Documents</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 text-sm"
            style={{ color: "var(--ink-3)" }}
            aria-label="Close"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="size-5">
              <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </button>
        </div>
        <DocumentUpload allowPurposeSelection={allowPurposeSelection} />
      </div>
    </div>
  );
}
