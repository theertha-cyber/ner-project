"use client";

import type { StatItem } from "@/types/dashboard";

interface StatCardProps {
  item: StatItem;
}

const deltaColor: Record<string, string> = {
  up: "var(--color-delta-up, #15803d)",
  warn: "var(--color-delta-warn, #b45309)",
};

export function StatCard({ item }: StatCardProps) {
  const displayValue = item.value === null ? "\u2014" : String(item.value);
  const deltaFg = item.dir ? deltaColor[item.dir] : null;
  const [fracUsed, fracTotal] = displayValue.includes("/") ? displayValue.split("/") : [null, null];

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
          }}
        >
          {item.label}
        </span>
        {item.delta && (
          <span
            style={{
              fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
              fontSize: 10,
              fontWeight: 600,
              color: deltaFg ?? "var(--color-text-secondary)",
            }}
          >
            {item.delta}
          </span>
        )}
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
        {fracUsed !== null ? (
          <span
            style={{
              fontFamily: "var(--font-display, 'Hanken Grotesk', sans-serif)",
              fontSize: 28,
              fontWeight: 800,
              lineHeight: 1,
              display: "inline-flex",
              alignItems: "baseline",
              gap: 3,
            }}
          >
            <span style={{ color: "var(--color-text-primary)" }}>{fracUsed}</span>
            <span style={{ color: "var(--color-text-tertiary, #94a3b8)", fontSize: 18, fontWeight: 600 }}>/</span>
            <span style={{ color: "var(--color-text-secondary)", fontSize: 18, fontWeight: 600 }}>{fracTotal}</span>
          </span>
        ) : (
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
        )}
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
      {item.sub && (
        <div
          style={{
            fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
            fontSize: 10.5,
            color: "var(--color-text-tertiary, #94a3b8)",
          }}
        >
          {item.sub}
        </div>
      )}
    </div>
  );
}
