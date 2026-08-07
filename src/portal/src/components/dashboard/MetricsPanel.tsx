"use client";

import { useEffect, useRef, useState } from "react";
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

/**
 * The readiness breakdown now enumerates every entity type the tenant cares
 * about, including ones with no annotations, so a tenant with many configured
 * labels would otherwise push an unbounded list into a side panel. Rows arrive
 * least-progressed first, so truncating the tail keeps exactly the ones worth
 * acting on.
 */
const MAX_SIDE_ROWS = 6;

function GrowBar({ pct, color }: { pct: number; color?: string }) {
  const fillRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = fillRef.current;
    if (el) {
      el.style.width = "0%";
      requestAnimationFrame(() => {
        el.style.width = `${Math.min(100, Math.max(0, pct))}%`;
      });
    }
  }, [pct]);
  return (
    <div style={{ height: 8, borderRadius: 3, background: "var(--color-border)", overflow: "hidden" }}>
      <div
        ref={fillRef}
        style={{
          height: "100%",
          borderRadius: 3,
          background: color ?? "linear-gradient(90deg, var(--color-brand-primary), var(--color-brand-hover))",
          transition: "width 0.8s ease",
        }}
      />
    </div>
  );
}

function statusColor(value: string): string | undefined {
  if (value === "Online" || value === "Healthy") return "var(--color-delta-up, #15803d)";
  if (value === "Offline" || value === "Critical") return "var(--bad, #b91c1c)";
  if (value === "Degraded") return "var(--warn, #b45309)";
  return undefined;
}

function MiniGrowBar({ pct, color }: { pct: number; color: string }) {
  const fillRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = fillRef.current;
    if (el) {
      el.style.width = "0%";
      requestAnimationFrame(() => {
        el.style.width = `${Math.min(100, Math.max(0, pct))}%`;
      });
    }
  }, [pct]);
  return (
    <div style={{ height: 6, borderRadius: 3, background: "var(--color-border)", overflow: "hidden" }}>
      <div
        ref={fillRef}
        style={{
          height: "100%",
          borderRadius: 3,
          background: color,
          transition: "width 0.8s ease",
        }}
      />
    </div>
  );
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
  // Local to the panel: the expanded view is a glance, not a preference, so it
  // deliberately resets on reload rather than persisting.
  const [showAllRows, setShowAllRows] = useState(false);
  const hiddenRowCount = Math.max(sideRows.length - MAX_SIDE_ROWS, 0);
  const visibleRows = showAllRows ? sideRows : sideRows.slice(0, MAX_SIDE_ROWS);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14, flex: 1, minWidth: 0 }}>
      <div
        style={{
          background: "var(--color-surface-raised)",
          border: "1px solid var(--color-border)",
          borderRadius: 18,
          padding: "20px 22px",
          display: "flex",
          flexDirection: "column",
          gap: 14,
        }}
      >
        <div>
          <span
            style={{
              display: "block",
              fontFamily: "var(--font-display, 'Hanken Grotesk', sans-serif)",
              fontSize: 15,
              fontWeight: 700,
              color: "var(--color-text-primary)",
              marginBottom: 4,
            }}
          >
            {sideTop}
          </span>
          <span
            style={{
              display: "block",
              fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
              fontSize: 11,
              color: "var(--color-text-secondary)",
              marginBottom: 16,
            }}
          >
            {sideMeta}
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
          <span
            style={{
              fontFamily: "var(--font-display, 'Hanken Grotesk', sans-serif)",
              fontSize: 44,
              fontWeight: 800,
              color: statusColor(big) ?? "var(--color-brand-primary)",
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

        <GrowBar pct={bar} />

        <div style={{ display: "flex", flexDirection: "row", justifyContent: "space-between" }}>
          {sideMetrics.map((m, i) => (
            <div
              key={i}
              style={{ display: "flex", flexDirection: "column", gap: 2 }}
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
                  color: statusColor(m.v) ?? "var(--color-text-primary)",
                }}
              >
                {m.v}
              </span>
            </div>
          ))}
        </div>
      </div>

      {sideRows.length > 0 && (
        <div
          style={{
            background: "var(--color-surface-raised)",
            border: "1px solid var(--color-border)",
            borderRadius: 18,
            padding: "20px 22px",
            display: "flex",
            flexDirection: "column",
            gap: 14,
          }}
        >
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
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {visibleRows.map((row, i) => (
              <div key={i} style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span
                    style={{
                      fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                      fontSize: 12,
                      color: "var(--color-text-secondary)",
                    }}
                  >
                    {row.label}
                  </span>
                  <span
                    style={{
                      fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                      fontSize: 12,
                      color: statusColor(row.val) ?? "var(--color-text-secondary)",
                    }}
                  >
                    {row.val}
                  </span>
                </div>
                <MiniGrowBar pct={row.pct} color={row.c} />
              </div>
            ))}
            {hiddenRowCount > 0 && (
              <button
                type="button"
                onClick={() => setShowAllRows((v) => !v)}
                aria-expanded={showAllRows}
                style={{
                  marginTop: 2,
                  alignSelf: "flex-start",
                  background: "none",
                  border: "none",
                  padding: 0,
                  cursor: "pointer",
                  fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                  fontSize: 11,
                  color: "var(--color-brand-primary)",
                  fontWeight: 600,
                }}
              >
                {showAllRows ? "Show less" : `+${hiddenRowCount} more · View all`}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
