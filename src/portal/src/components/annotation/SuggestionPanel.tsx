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
        No suggestions — click ✦ Pre-label to generate
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
            data-testid={`suggestion-card-${s.id}`}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "10px 12px",
              border: "1px dashed var(--color-border)",
              borderRadius: 12,
              background: color + "08",
            }}
          >
            {/* Colored dot */}
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: color,
                flexShrink: 0,
              }}
            />

            {/* Text + type + confidence */}
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
                data-testid={`suggestion-text-${s.id}`}
              >
                {s.text}
              </span>
              <span
                style={{
                  fontSize: 11,
                  color,
                  fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                }}
                data-testid={`suggestion-meta-${s.id}`}
              >
                {s.entityType} · conf {s.confidence.toFixed(2)}
              </span>
            </div>

            {/* Promote button */}
            <button
              onClick={() => onPromote(s.id)}
              data-testid={`promote-btn-${s.id}`}
              style={{
                padding: "4px 10px",
                background: "var(--color-brand-primary)",
                color: "#fff",
                border: "none",
                borderRadius: 6,
                fontSize: 12,
                cursor: "pointer",
                fontWeight: 600,
                whiteSpace: "nowrap",
                flexShrink: 0,
              }}
            >
              Promote
            </button>

            {/* Dismiss button */}
            <button
              onClick={() => onDismiss(s.id)}
              data-testid={`dismiss-btn-${s.id}`}
              style={{
                padding: "4px 8px",
                background: "none",
                color: "var(--color-text-secondary)",
                border: "1px solid var(--color-border)",
                borderRadius: 6,
                fontSize: 12,
                cursor: "pointer",
                flexShrink: 0,
              }}
              aria-label="Dismiss suggestion"
            >
              ✕
            </button>
          </div>
        );
      })}
    </div>
  );
}
