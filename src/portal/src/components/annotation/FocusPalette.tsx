"use client";

import type { EntityTypeItem } from "./EntityPalette";
import type { ConfirmedSpan } from "./span-reducer";

interface FocusPaletteProps {
  entityTypes: EntityTypeItem[];
  entityColors: Record<string, string>;
  confirmedSpans: ConfirmedSpan[];
  armedType: string | null;
  isPrelabeling: boolean;
  onArm: (name: string) => void;
  onDisarm: () => void;
  onPrelabel: () => void;
}

export function FocusPalette({
  entityTypes,
  entityColors,
  confirmedSpans,
  armedType,
  isPrelabeling,
  onArm,
  onDisarm,
  onPrelabel,
}: FocusPaletteProps) {
  const spanCounts = confirmedSpans.reduce<Record<string, number>>((acc, s) => {
    if (!s.optimistic) acc[s.entityType] = (acc[s.entityType] ?? 0) + 1;
    return acc;
  }, {});

  const active = entityTypes.filter((et) => et.is_active);

  return (
    <div
      style={{
        position: "fixed",
        bottom: 28,
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 200,
        display: "flex",
        alignItems: "center",
        gap: 8,
        backdropFilter: "blur(22px) saturate(1.4)",
        WebkitBackdropFilter: "blur(22px) saturate(1.4)",
        background: "var(--color-glass)",
        border: "1px solid var(--color-glass-border)",
        borderRadius: 18,
        padding: "9px 11px",
        boxShadow: "0 8px 32px rgba(0,0,0,0.12)",
      }}
      data-testid="focus-palette"
    >
      {/* Label */}
      <span
        style={{
          fontSize: 10,
          fontWeight: 700,
          color: "var(--color-text-secondary)",
          fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          whiteSpace: "nowrap",
          flexShrink: 0,
        }}
      >
        LABEL AS
      </span>

      {/* Entity chips */}
      {active.map((et) => {
        const color = entityColors[et.name] ?? "#94a3b8";
        const count = spanCounts[et.name] ?? 0;
        const isArmed = armedType === et.name;

        return (
          <button
            key={et.id}
            onClick={() => (isArmed ? onDisarm() : onArm(et.name))}
            data-testid={`focus-entity-chip-${et.name}`}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              padding: "4px 10px",
              borderRadius: 8,
              border: isArmed ? `2px solid ${color}` : "2px solid transparent",
              background: isArmed ? color + "22" : color + "11",
              cursor: "pointer",
              transition: "all 0.15s",
              outline: isArmed ? `2px solid ${color}` : "none",
              outlineOffset: 1,
              whiteSpace: "nowrap",
              flexShrink: 0,
            }}
          >
            <span
              style={{
                width: 9,
                height: 9,
                borderRadius: 3,
                background: color,
                flexShrink: 0,
              }}
            />
            <span
              style={{
                fontSize: 12,
                fontWeight: 600,
                fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                color: isArmed ? color : "var(--color-text-primary)",
              }}
            >
              {et.name}
            </span>
            <span
              style={{
                fontSize: 11,
                color: count > 0 ? color : "var(--color-text-secondary)",
                fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                fontWeight: count > 0 ? 600 : 400,
              }}
            >
              {count}
            </span>
          </button>
        );
      })}

      {/* Vertical divider */}
      <div
        style={{
          width: 1,
          height: 20,
          background: "var(--color-border)",
          flexShrink: 0,
          marginLeft: 2,
          marginRight: 2,
        }}
      />

      {/* Pre-label button */}
      <button
        onClick={onPrelabel}
        disabled={isPrelabeling}
        data-testid="focus-prelabel-btn"
        style={{
          padding: "4px 10px",
          borderRadius: 7,
          border: "1px solid var(--color-border)",
          background: "var(--color-surface-raised)",
          color: isPrelabeling ? "var(--color-text-secondary)" : "var(--color-text-primary)",
          fontSize: 12,
          cursor: isPrelabeling ? "not-allowed" : "pointer",
          opacity: isPrelabeling ? 0.6 : 1,
          pointerEvents: isPrelabeling ? "none" : "auto",
          whiteSpace: "nowrap",
          flexShrink: 0,
        }}
      >
        ✦ Pre-label
      </button>
    </div>
  );
}
