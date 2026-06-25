"use client";

import type { StatItem } from "@/types/dashboard";

interface StatCardProps {
  item: StatItem;
}

const deltaPill: Record<string, { bg: string; fg: string }> = {
  up: { bg: "var(--good-soft, rgba(21,128,61,0.10))", fg: "var(--color-delta-up, #16a34a)" },
  warn: { bg: "var(--warn-soft, rgba(180,83,9,0.10))", fg: "var(--color-delta-warn, #d97706)" },
};

export function StatCard({ item }: StatCardProps) {
  const displayValue = item.value === null ? "\u2014" : String(item.value);
  const pill = item.dir ? deltaPill[item.dir] : null;

  return (
    <div
      style={{
        background: "var(--color-surface-raised)",
        border: "1px solid var(--color-border)",
        borderRadius: 16,
        padding: "20px 22px",
        display: "flex",
        flexDirection: "column",
        gap: 6,
        minWidth: 0,
        transition: "transform 0.15s ease, border-color 0.15s ease",
        cursor: "default",
      }}
      onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.transform = "translateY(-2px)"; (e.currentTarget as HTMLElement).style.borderColor = "var(--primary-line)"; }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.transform = ""; (e.currentTarget as HTMLElement).style.borderColor = "var(--color-border)"; }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span
          style={{
            fontFamily: "var(--font-body, Inter, sans-serif)",
            fontSize: 12,
            fontWeight: 500,
            color: "var(--color-text-secondary)",
            textTransform: "uppercase",
            letterSpacing: "0.06em",
          }}
        >
          {item.label}
        </span>
        {item.delta && (
          pill ? (
            <span
              style={{
                fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                fontSize: 10,
                fontWeight: 600,
                padding: "2px 7px",
                borderRadius: 20,
                background: pill.bg,
                color: pill.fg,
              }}
            >
              {item.delta}
            </span>
          ) : (
            <span
              style={{
                fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                fontSize: 10,
                color: "var(--color-text-secondary)",
              }}
            >
              {item.delta}
            </span>
          )
        )}
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
        <span
          style={{
            fontFamily: "var(--font-display, 'Hanken Grotesk', sans-serif)",
            fontSize: 30,
            fontWeight: 800,
            color: "var(--color-text-primary)",
            lineHeight: 1,
          }}
        >
          {displayValue}
        </span>
        {item.unit && item.value !== null && (
          <span
            style={{
              fontFamily: "var(--font-body, Inter, sans-serif)",
              fontSize: 14,
              color: "var(--color-text-secondary)",
            }}
          >
            {item.unit}
          </span>
        )}
      </div>
      <div
        style={{
          fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
          fontSize: 10.5,
          color: "var(--color-text-secondary)",
        }}
      >
        {item.sub}
      </div>
    </div>
  );
}
