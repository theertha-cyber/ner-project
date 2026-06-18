"use client";

import type { SuggestedSpan } from "./span-reducer";

interface SuggestionPanelProps {
  suggestions: SuggestedSpan[];
  entityColors: Record<string, string>;
  onPromote: (suggestId: string) => void;
  onDismiss: (suggestId: string) => void;
}

export function SuggestionPanel({ suggestions, entityColors, onPromote, onDismiss }: SuggestionPanelProps) {
  if (suggestions.length === 0) {
    return (
      <div
        style={{
          padding: "12px 0",
          color: "var(--color-text-secondary)",
          fontSize: 12,
          textAlign: "center",
        }}
      >
        No suggestions — click Pre-label to generate
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {suggestions.map((s) => {
        const color = entityColors[s.entityType] ?? "#94a3b8";
        return (
          <div
            key={s.id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 10px",
              border: `1px dashed ${color}`,
              borderRadius: 6,
              background: color + "0d",
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <span
                style={{
                  fontSize: 13,
                  color: "var(--color-text-primary)",
                  fontWeight: 500,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  display: "block",
                }}
              >
                {s.text}
              </span>
              <span
                style={{
                  fontSize: 11,
                  color,
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                }}
              >
                {s.entityType}
              </span>
            </div>
            <button
              onClick={() => onPromote(s.id)}
              title="Promote to confirmed span"
              style={{
                padding: "3px 8px",
                background: color,
                color: "#fff",
                border: "none",
                borderRadius: 4,
                fontSize: 11,
                cursor: "pointer",
                fontWeight: 600,
                whiteSpace: "nowrap",
              }}
            >
              ✓ Keep
            </button>
            <button
              onClick={() => onDismiss(s.id)}
              title="Dismiss suggestion"
              style={{
                padding: "3px 8px",
                background: "none",
                color: "var(--color-text-secondary)",
                border: "1px solid var(--color-border)",
                borderRadius: 4,
                fontSize: 11,
                cursor: "pointer",
              }}
            >
              ✕
            </button>
          </div>
        );
      })}
    </div>
  );
}
