"use client";

export interface BaseModelConfirmDialogProps {
  onConfirm: () => void;
  onCancel: () => void;
}

export function BaseModelConfirmDialog({ onConfirm, onCancel }: BaseModelConfirmDialogProps) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    >
      <div className="w-full max-w-sm rounded-xl border border-border bg-surface-raised p-5 flex flex-col gap-4">
        <p className="text-sm text-text-primary">
          A fine-tuned model isn&apos;t available yet. Use the base model for this run?
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
            onClick={onConfirm}
            className="rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white hover:bg-brand-hover"
          >
            Use base model
          </button>
        </div>
      </div>
    </div>
  );
}
