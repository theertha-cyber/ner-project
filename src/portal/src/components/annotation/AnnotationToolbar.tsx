"use client";

import type { AnnotationTask } from "./TaskQueue";

type LayoutMode = "3pane" | "focus";
type TaskStatus = AnnotationTask["status"];

const STATUS_LABELS: Record<TaskStatus, string> = {
  unannotated: "pending",
  "in-progress": "in_progress",
  completed: "completed",
};

interface AnnotationToolbarProps {
  task: AnnotationTask | null;
  filename: string;
  currentStatus: TaskStatus | null;
  confirmedCount: number;
  suggestedCount: number;
  layoutMode: LayoutMode;
  isPrelabeling: boolean;
  onLayoutChange: (mode: LayoutMode) => void;
  onPrelabel: () => void;
}

export function AnnotationToolbar({
  task,
  filename,
  currentStatus,
  confirmedCount,
  suggestedCount,
  layoutMode,
  isPrelabeling,
  onLayoutChange,
  onPrelabel,
}: AnnotationToolbarProps) {
  const resolvedStatus = currentStatus;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "10px 16px",
        borderBottom: "1px solid var(--color-border)",
        flexShrink: 0,
      }}
      data-testid="annotation-toolbar"
    >
      {/* Filename / task label + status badge */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
        <span
          style={{
            fontSize: 13,
            fontWeight: 600,
            fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
            color: "var(--color-text-primary)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            maxWidth: 180,
          }}
        >
          {task ? filename : "No task selected"}
        </span>
        {resolvedStatus && (
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              padding: "2px 6px",
              borderRadius: 4,
              background: resolvedStatus === "completed"
                ? "rgba(16,185,129,0.12)"
                : resolvedStatus === "in-progress"
                ? "rgba(59,130,246,0.12)"
                : "rgba(107,114,128,0.12)",
              color: resolvedStatus === "completed"
                ? "var(--color-success)"
                : resolvedStatus === "in-progress"
                ? "var(--color-info)"
                : "var(--color-text-secondary)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              flexShrink: 0,
            }}
            data-testid="status-badge"
          >
            {STATUS_LABELS[resolvedStatus]}
          </span>
        )}
      </div>

      {/* Flex spacer */}
      <div style={{ flex: 1 }} />

      {/* Span counter */}
      {task && (
        <span
          style={{
            fontSize: 11,
            color: "var(--color-text-secondary)",
            fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
            whiteSpace: "nowrap",
            flexShrink: 0,
          }}
          data-testid="span-counter"
        >
          {confirmedCount} confirmed · {suggestedCount} suggested
        </span>
      )}

      {/* Pre-label button */}
      <button
        onClick={onPrelabel}
        disabled={isPrelabeling || !task}
        data-testid="prelabel-btn"
        style={{
          padding: "5px 12px",
          borderRadius: 6,
          border: "1px solid var(--color-border)",
          background: "var(--color-surface-raised)",
          color: isPrelabeling || !task ? "var(--color-text-secondary)" : "var(--color-text-primary)",
          fontSize: 12,
          cursor: isPrelabeling || !task ? "not-allowed" : "pointer",
          opacity: isPrelabeling || !task ? 0.6 : 1,
          pointerEvents: isPrelabeling ? "none" : "auto",
          whiteSpace: "nowrap",
          flexShrink: 0,
        }}
      >
        ✦ Pre-label
      </button>

      {/* View-mode toggle */}
      <div
        style={{
          display: "flex",
          borderRadius: 9,
          border: "1px solid var(--color-border)",
          background: "var(--color-surface-raised)",
          padding: 3,
          gap: 2,
          flexShrink: 0,
        }}
        data-testid="layout-toggle"
      >
        {(["3pane", "focus"] as LayoutMode[]).map((mode) => {
          const isActive = layoutMode === mode;
          return (
            <button
              key={mode}
              onClick={() => onLayoutChange(mode)}
              data-testid={`layout-btn-${mode}`}
              style={{
                padding: "3px 10px",
                borderRadius: 6,
                border: "none",
                background: isActive ? "var(--color-surface-overlay)" : "transparent",
                boxShadow: isActive ? "0 1px 4px rgba(0,0,0,0.08)" : "none",
                color: isActive ? "var(--color-text-primary)" : "var(--color-text-secondary)",
                fontSize: 12,
                fontWeight: isActive ? 600 : 400,
                cursor: "pointer",
                transition: "all 0.15s",
              }}
            >
              {mode === "3pane" ? "3-pane" : "Focus"}
            </button>
          );
        })}
      </div>
    </div>
  );
}
