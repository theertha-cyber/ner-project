"use client";

import type { ConfirmedSpan } from "./span-reducer";
import type { EntityTypeItem } from "./EntityPalette";

interface SpanInspectorProps {
  span: ConfirmedSpan;
  entityTypes: EntityTypeItem[];
  entityColors: Record<string, string>;
  layoutMode?: "3pane" | "focus";
  onRetype: (spanId: string, entityType: string) => void;
  onDelete: (spanId: string) => void;
  onClose: () => void;
}

export function SpanInspector({
  span,
  entityTypes,
  entityColors,
  layoutMode = "3pane",
  onRetype,
  onDelete,
  onClose,
}: SpanInspectorProps) {
  const currentColor = entityColors[span.entityType] ?? "#94a3b8";
  const baseType = entityTypes.find((et) => et.name === span.entityType)?.target_table;
  const otherTypes = entityTypes.filter((et) => et.is_active && et.name !== span.entityType);

  const focusStyle: React.CSSProperties = {
    position: "fixed",
    top: 140,
    right: 30,
    width: 290,
    backdropFilter: "blur(20px)",
    WebkitBackdropFilter: "blur(20px)",
    background: "var(--color-glass)",
    border: "1px solid var(--color-glass-border)",
    borderRadius: 14,
    boxShadow: "0 8px 32px rgba(0,0,0,0.12)",
    zIndex: 50,
    padding: "14px 16px",
    animation: "spanPopIn 0.25s ease both",
  };

  const panelStyle: React.CSSProperties = {
    border: "1px solid var(--color-border)",
    borderRadius: 14,
    background: "var(--color-surface-raised)",
    boxShadow: "0 4px 20px rgba(0,0,0,0.08)",
    padding: "14px 16px",
    animation: "spanPopIn 0.25s ease both",
  };

  return (
    <div
      style={layoutMode === "focus" ? focusStyle : panelStyle}
      data-testid="span-inspector"
      data-layout={layoutMode}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        {layoutMode === "focus" ? (
          <span
            style={{
              fontSize: 12,
              fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
              color: "var(--color-text-primary)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              flex: 1,
              marginRight: 8,
            }}
            data-testid="condensed-header"
          >
            {span.text} · [{span.charStart}, {span.charEnd}] · conf {span.confidence.toFixed(2)}
          </span>
        ) : (
          <span
            style={{
              display: "inline-block",
              padding: "3px 10px",
              borderRadius: 6,
              background: currentColor + "22",
              color: currentColor,
              fontWeight: 600,
              fontSize: 13,
              fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
              maxWidth: 180,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {span.text}
          </span>
        )}
        <button
          onClick={onClose}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            color: "var(--color-text-secondary)",
            fontSize: 16,
            lineHeight: 1,
            padding: 2,
          }}
          aria-label="Close inspector"
        >
          ✕
        </button>
      </div>

      {/* 2×2 metadata grid (3-pane only) */}
      {layoutMode !== "focus" && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "6px 12px",
            fontSize: 12,
            marginBottom: 14,
          }}
          data-testid="metadata-grid"
        >
          <MetaCell label="char_start" value={String(span.charStart)} />
          <MetaCell label="char_end" value={String(span.charEnd)} />
          <MetaCell label="confidence" value={span.confidence.toFixed(2)} />
          <MetaCell label="base" value={baseType ?? "—"} />
        </div>
      )}

      {/* Reassign chips */}
      {otherTypes.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <div
            style={{
              fontSize: 10,
              fontWeight: 600,
              color: "var(--color-text-secondary)",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              marginBottom: 6,
            }}
          >
            Reassign Type
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {otherTypes.map((et) => {
              const color = entityColors[et.name] ?? "#94a3b8";
              return (
                <button
                  key={et.id}
                  onClick={() => onRetype(span.id, et.name)}
                  data-testid={`retype-chip-${et.name}`}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 5,
                    padding: "3px 9px",
                    borderRadius: 6,
                    border: `1px solid ${color}44`,
                    background: color + "11",
                    color: "var(--color-text-primary)",
                    fontSize: 12,
                    cursor: "pointer",
                    fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                    fontWeight: 500,
                  }}
                >
                  <span
                    style={{
                      width: 7,
                      height: 7,
                      borderRadius: "50%",
                      background: color,
                      flexShrink: 0,
                    }}
                  />
                  {et.name}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Delete button */}
      <button
        onClick={() => onDelete(span.id)}
        data-testid="delete-span-btn"
        style={{
          width: "100%",
          padding: "6px 0",
          background: "rgba(239,68,68,0.08)",
          color: "var(--color-error, #ef4444)",
          border: "none",
          borderRadius: 6,
          fontSize: 13,
          cursor: "pointer",
          fontWeight: 500,
        }}
      >
        Delete span
      </button>
    </div>
  );
}

function MetaCell({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
      <span
        style={{
          fontSize: 10,
          color: "var(--color-text-secondary)",
          fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
          textTransform: "lowercase",
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontSize: 12,
          color: "var(--color-text-primary)",
          fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
          fontWeight: 600,
        }}
      >
        {value}
      </span>
    </div>
  );
}
