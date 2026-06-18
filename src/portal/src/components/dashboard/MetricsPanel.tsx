"use client";

import type { SideMetric, SideRow } from "@/types/dashboard";

interface MetricsPanelProps {
  sideTop: string;
  sideMeta: string;
  big: string;
  bigUnit: string;
  bar: number;
  sideMetrics: [SideMetric, SideMetric, SideMetric];
  sideBot: string;
  sideRows: SideRow[];
}

export function MetricsPanel({
  sideTop,
  sideMeta,
  big,
  bigUnit,
  bar,
  sideMetrics,
  sideBot,
  sideRows,
}: MetricsPanelProps) {
  return (
    <div
      style={{
        background: "var(--color-surface-raised)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-lg, 12px)",
        padding: "20px 22px",
        display: "flex",
        flexDirection: "column",
        gap: 14,
        flex: 1,
        minWidth: 0,
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span
          style={{
            fontFamily: "var(--font-display, 'Hanken Grotesk', sans-serif)",
            fontSize: 14,
            fontWeight: 700,
            color: "var(--color-text-primary)",
          }}
        >
          {sideTop}
        </span>
        <span
          style={{
            fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
            fontSize: 10,
            color: "var(--color-text-secondary)",
          }}
        >
          {sideMeta}
        </span>
      </div>

      {/* Big number */}
      <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
        <span
          style={{
            fontFamily: "var(--font-display, 'Hanken Grotesk', sans-serif)",
            fontSize: 36,
            fontWeight: 700,
            color: "var(--color-text-primary)",
            lineHeight: 1,
          }}
        >
          {big}
        </span>
        <span
          style={{
            fontFamily: "var(--font-body, Inter, sans-serif)",
            fontSize: 14,
            color: "var(--color-text-secondary)",
          }}
        >
          {bigUnit}
        </span>
      </div>

      {/* Progress bar */}
      <div
        style={{
          height: 6,
          borderRadius: 3,
          background: "var(--color-border)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${Math.min(100, Math.max(0, bar))}%`,
            borderRadius: 3,
            background: "var(--color-brand-primary)",
            transition: "width 0.4s ease",
          }}
        />
      </div>

      {/* Side metrics */}
      <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
        {sideMetrics.map((m, i) => (
          <div
            key={i}
            style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
          >
            <span
              style={{
                fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                fontSize: 11,
                color: "var(--color-text-secondary)",
              }}
            >
              {m.k}
            </span>
            <span
              style={{
                fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                fontSize: 11,
                fontWeight: 600,
                color: "var(--color-text-primary)",
              }}
            >
              {m.v}
            </span>
          </div>
        ))}
      </div>

      {/* Side bot section */}
      {sideRows.length > 0 && (
        <>
          <div style={{ borderTop: "1px solid var(--color-border)", paddingTop: 10 }}>
            <span
              style={{
                fontFamily: "var(--font-body, Inter, sans-serif)",
                fontSize: 11,
                fontWeight: 600,
                color: "var(--color-text-secondary)",
                textTransform: "uppercase",
                letterSpacing: "0.06em",
              }}
            >
              {sideBot}
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {sideRows.map((row, i) => (
              <div key={i} style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <span
                    style={{
                      fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                      fontSize: 10.5,
                      color: "var(--color-text-secondary)",
                    }}
                  >
                    {row.label}
                  </span>
                  <span
                    style={{
                      fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                      fontSize: 10.5,
                      color: "var(--color-text-secondary)",
                    }}
                  >
                    {row.val}
                  </span>
                </div>
                <div
                  style={{
                    height: 4,
                    borderRadius: 2,
                    background: "var(--color-border)",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      height: "100%",
                      width: `${Math.min(100, Math.max(0, row.pct))}%`,
                      borderRadius: 2,
                      background: row.c,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
