"use client";

import type { StatItem } from "@/types/dashboard";

interface StatCardProps {
  item: StatItem;
}

export function StatCard({ item }: StatCardProps) {
  const displayValue = item.value === null ? "—" : String(item.value);

  return (
    <div
      style={{
        background: "var(--color-surface-raised)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-lg, 12px)",
        padding: "20px 22px",
        display: "flex",
        flexDirection: "column",
        gap: 6,
        flex: 1,
        minWidth: 0,
      }}
    >
      <div
        style={{
          fontFamily: "var(--font-body, Inter, sans-serif)",
          fontSize: 11,
          fontWeight: 500,
          color: "var(--color-text-secondary)",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
        }}
      >
        {item.label}
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
        <span
          style={{
            fontFamily: "var(--font-display, 'Hanken Grotesk', sans-serif)",
            fontSize: 28,
            fontWeight: 700,
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
          fontFamily: "var(--font-body, Inter, sans-serif)",
          fontSize: 12,
          color: "var(--color-text-secondary)",
        }}
      >
        {item.sub}
      </div>
      {item.delta && (
        <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 2 }}>
          {item.dir === "up" && (
            <span style={{ color: "var(--color-delta-up)", fontSize: 12 }}>↑</span>
          )}
          {item.dir === "warn" && (
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                background: "var(--color-delta-warn)",
                display: "inline-block",
                flexShrink: 0,
              }}
            />
          )}
          <span
            style={{
              fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
              fontSize: 11,
              color:
                item.dir === "warn"
                  ? "var(--color-delta-warn)"
                  : item.dir === "up"
                  ? "var(--color-delta-up)"
                  : "var(--color-text-secondary)",
            }}
          >
            {item.delta}
          </span>
        </div>
      )}
    </div>
  );
}
