"use client";

import type { ConfirmedSpan } from "./span-reducer";

export interface EntityTypeItem {
  id: string;
  name: string;
  description?: string | null;
  target_table?: string | null;
  is_active: boolean;
}

interface EntityPaletteProps {
  entityTypes: EntityTypeItem[];
  entityColors: Record<string, string>;
  confirmedSpans: ConfirmedSpan[];
  armedType: string | null;
  onArm: (name: string) => void;
  onDisarm: () => void;
}

export function EntityPalette({
  entityTypes,
  entityColors,
  confirmedSpans,
  armedType,
  onArm,
  onDisarm,
}: EntityPaletteProps) {
  const spanCounts = confirmedSpans.reduce<Record<string, number>>((acc, s) => {
    if (!s.optimistic) acc[s.entityType] = (acc[s.entityType] ?? 0) + 1;
    return acc;
  }, {});

  const active = entityTypes.filter((et) => et.is_active);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div
        style={{
          fontSize: 11,
          fontWeight: 600,
          color: "var(--color-text-secondary)",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          marginBottom: 4,
        }}
      >
        Entity Types
      </div>
      {active.map((et) => {
        const color = entityColors[et.name] ?? "#94a3b8";
        const count = spanCounts[et.name] ?? 0;
        const isArmed = armedType === et.name;

        return (
          <button
            key={et.id}
            onClick={() => (isArmed ? onDisarm() : onArm(et.name))}
            data-testid={`entity-btn-${et.name}`}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "8px 10px",
              borderRadius: 8,
              border: isArmed ? `2px solid ${color}` : "2px solid transparent",
              background: isArmed ? color + "22" : "var(--color-surface-raised)",
              cursor: "pointer",
              textAlign: "left",
              transition: "all 0.15s",
              outline: isArmed ? `2px solid ${color}` : "none",
              outlineOffset: 1,
              width: "100%",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
              {/* Colored dot */}
              <span
                style={{
                  width: 11,
                  height: 11,
                  borderRadius: 3,
                  background: color,
                  display: "inline-block",
                  flexShrink: 0,
                }}
              />
              {/* Name + base sub-label */}
              <span style={{ display: "flex", flexDirection: "column", gap: 1, minWidth: 0 }}>
                <span
                  style={{
                    fontSize: 13,
                    fontWeight: 600,
                    fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                    color: isArmed ? color : "var(--color-text-primary)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {et.name}
                </span>
                {et.target_table && (
                  <span
                    style={{
                      fontSize: 9.5,
                      color: "var(--color-text-secondary)",
                      fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                    }}
                    data-testid={`entity-base-${et.name}`}
                  >
                    base: {et.target_table}
                  </span>
                )}
              </span>
            </div>
            {/* Span count */}
            <span
              style={{
                fontSize: 12,
                color: count > 0 ? color : "var(--color-text-secondary)",
                fontWeight: count > 0 ? 600 : 400,
                fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                flexShrink: 0,
                marginLeft: 4,
              }}
            >
              {count}
            </span>
          </button>
        );
      })}
      {active.length === 0 && (
        <div style={{ fontSize: 12, color: "var(--color-text-secondary)", padding: "8px 0" }}>
          No entity types configured
        </div>
      )}
    </div>
  );
}
