"use client";

import { useRouter } from "next/navigation";
import type { ActivityRow } from "@/types/dashboard";
import { goToHref } from "@/hooks/use-dashboard-data";

const TAG_COLOURS: Record<string, [bg: string, fg: string]> = {
  pending_approval: ["rgba(245,158,11,0.15)", "var(--color-status-pending_approval)"],
  completed:        ["rgba(16,185,129,0.15)",  "var(--color-status-completed)"],
  running:          ["rgba(59,130,246,0.15)",   "var(--color-status-running)"],
  queued:           ["rgba(139,92,246,0.15)",   "var(--color-status-queued)"],
  failed:           ["rgba(239,68,68,0.15)",    "var(--color-status-failed)"],
  rejected:         ["rgba(220,38,38,0.15)",    "var(--color-status-rejected)"],
  cancelled:        ["rgba(107,114,128,0.1)",   "var(--color-status-cancelled)"],
  active:           ["rgba(34,197,94,0.15)",    "var(--color-status-active)"],
  promoted:         ["rgba(14,165,233,0.15)",   "var(--color-status-promoted)"],
};

function tagStyle(tk: string): { background: string; color: string } {
  const [bg, fg] = TAG_COLOURS[tk] ?? ["var(--color-border)", "var(--color-text-secondary)"];
  return { background: bg, color: fg };
}

interface ActivityPanelProps {
  pTitle: string;
  pMeta: string;
  pRows: ActivityRow[];
}

export function ActivityPanel({ pTitle, pMeta, pRows }: ActivityPanelProps) {
  const router = useRouter();

  return (
    <div
      style={{
        background: "var(--color-surface-raised)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-lg, 12px)",
        padding: "20px 22px",
        display: "flex",
        flexDirection: "column",
        flex: 1,
        minWidth: 0,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          marginBottom: 14,
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-display, 'Hanken Grotesk', sans-serif)",
            fontSize: 14,
            fontWeight: 700,
            color: "var(--color-text-primary)",
          }}
        >
          {pTitle}
        </span>
        <span
          style={{
            fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
            fontSize: 10,
            color: "var(--color-text-secondary)",
          }}
        >
          {pMeta}
        </span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {pRows.map((row, i) => (
          <button
            key={i}
            onClick={() => row.title !== "—" && router.push(goToHref(row.go))}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "9px 10px",
              borderRadius: "var(--radius-md, 8px)",
              border: "none",
              background: "transparent",
              cursor: row.title !== "—" ? "pointer" : "default",
              textAlign: "left",
              width: "100%",
              transition: "background 0.12s",
            }}
            onMouseEnter={(e) => {
              if (row.title !== "—")
                (e.currentTarget as HTMLElement).style.background = "var(--color-surface)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.background = "transparent";
            }}
          >
            <span
              style={{
                fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                fontSize: 10.5,
                fontWeight: 600,
                padding: "3px 9px",
                borderRadius: 20,
                whiteSpace: "nowrap",
                flexShrink: 0,
                ...tagStyle(row.tk),
              }}
            >
              {row.tag}
            </span>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div
                style={{
                  fontFamily: "var(--font-body, Inter, sans-serif)",
                  fontSize: 13,
                  fontWeight: 500,
                  color: "var(--color-text-primary)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {row.title}
              </div>
              <div
                style={{
                  fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                  fontSize: 10.5,
                  color: "var(--color-text-secondary)",
                  marginTop: 1,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {row.sub}
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
