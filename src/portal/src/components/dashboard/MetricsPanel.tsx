"use client";

import { useEffect, useRef } from "react";
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
              color: "var(--color-brand-primary)",
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
                  color: "var(--color-text-primary)",
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
            {sideRows.map((row, i) => (
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
                      color: "var(--color-text-secondary)",
                    }}
                  >
                    {row.val}
                  </span>
                </div>
                <MiniGrowBar pct={row.pct} color={row.c} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
