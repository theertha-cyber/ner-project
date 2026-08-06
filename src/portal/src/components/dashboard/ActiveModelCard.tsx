"use client";

import type { ActiveModelInfo } from "@/types/dashboard";

interface ActiveModelCardProps {
  data: ActiveModelInfo | null | undefined;
}

function MetaItem({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
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
        {label}
      </span>
      {children}
    </div>
  );
}

export function ActiveModelCard({ data }: ActiveModelCardProps) {
  const isActive = data?.status === "active";

  return (
    <div
      style={{
        background: "var(--color-surface-raised)",
        border: "1px solid var(--color-border)",
        borderRadius: 18,
        padding: "20px 22px",
        display: "flex",
        flexDirection: "column",
        gap: 16,
      }}
    >
      <span
        style={{
          fontFamily: "var(--font-display, 'Hanken Grotesk', sans-serif)",
          fontSize: 15,
          fontWeight: 700,
          color: "var(--color-text-primary)",
        }}
      >
        Active Model
      </span>

      <span
        style={{
          fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
          fontSize: 22,
          fontWeight: 700,
          color: "var(--color-text-primary)",
          lineHeight: 1.2,
          wordBreak: "break-word",
        }}
      >
        {data?.name ?? "—"}
      </span>

      <div style={{ height: 1, background: "var(--color-border)" }} />

      <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
        <MetaItem label="Status">
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: isActive ? "var(--good, #16a34a)" : "var(--color-text-secondary)",
                flexShrink: 0,
              }}
            />
            <span
              style={{
                fontFamily: "var(--font-body, Inter, sans-serif)",
                fontSize: 13,
                fontWeight: 600,
                color: isActive ? "var(--good, #16a34a)" : "var(--color-text-secondary)",
              }}
            >
              {isActive ? "Active" : "Unavailable"}
            </span>
          </span>
        </MetaItem>

        <MetaItem label="Version">
          <span
            style={{
              fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
              fontSize: 13,
              fontWeight: 600,
              color: "var(--color-text-primary)",
            }}
          >
            {data?.version ?? "—"}
          </span>
        </MetaItem>

        <MetaItem label="Deployed">
          <span
            style={{
              fontFamily: "var(--font-body, Inter, sans-serif)",
              fontSize: 13,
              fontWeight: 600,
              color: "var(--color-text-primary)",
            }}
          >
            {data?.deployedAt ?? "—"}
          </span>
        </MetaItem>
      </div>
    </div>
  );
}
