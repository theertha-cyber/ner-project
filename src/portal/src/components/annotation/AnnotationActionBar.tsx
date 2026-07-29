"use client";

import type { AnnotationTask } from "./TaskQueue";

export type SaveState = "idle" | "saving" | "saved";

interface AnnotationActionBarProps {
  task: AnnotationTask | null;
  saveState: SaveState;
  isCompleting: boolean;
  onMarkCompleted: () => void;
}

const SAVE_LABELS: Record<SaveState, string> = {
  idle: "",
  saving: "Saving…",
  saved: "All changes saved",
};

export function AnnotationActionBar({
  task,
  saveState,
  isCompleting,
  onMarkCompleted,
}: AnnotationActionBarProps) {
  const disabled = !task || isCompleting;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "10px 16px",
        borderTop: "1px solid var(--color-border)",
        flexShrink: 0,
      }}
      data-testid="annotation-action-bar"
    >
      <span
        style={{
          fontSize: 12,
          color: "var(--color-text-secondary)",
        }}
        data-testid="save-indicator"
      >
        {SAVE_LABELS[saveState]}
      </span>

      <div style={{ flex: 1 }} />

      <button
        onClick={onMarkCompleted}
        disabled={disabled}
        data-testid="mark-completed-btn"
        style={{
          padding: "6px 16px",
          borderRadius: 6,
          border: "none",
          background: disabled ? "var(--color-surface-raised)" : "var(--color-primary, #6366f1)",
          color: disabled ? "var(--color-text-secondary)" : "#fff",
          fontSize: 13,
          fontWeight: 600,
          cursor: disabled ? "not-allowed" : "pointer",
          opacity: disabled ? 0.6 : 1,
        }}
      >
        {isCompleting ? "Completing…" : "Mark as Completed"}
      </button>
    </div>
  );
}
