"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  GraduationCap,
  BadgeCheck,
  Rocket,
  AlertTriangle,
  Layers,
  Database,
  Upload,
  UserPlus,
  Circle,
  type LucideIcon,
} from "lucide-react";
import type { ActivityRow } from "@/types/dashboard";
import { goToHref, useDashboardActivity } from "@/hooks/use-dashboard-data";
import { SlideOver } from "@/components/ui/slide-over";

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

const ROW_ICONS: Record<string, LucideIcon> = {
  training: GraduationCap,
  approval: BadgeCheck,
  deploy: Rocket,
  failure: AlertTriangle,
  batch: Layers,
  dataset: Database,
  upload: Upload,
  user: UserPlus,
};

function tagStyle(tk: string): { background: string; color: string } {
  const [bg, fg] = TAG_COLOURS[tk] ?? ["var(--color-border)", "var(--color-text-secondary)"];
  return { background: bg, color: fg };
}

interface ActivityRowListProps {
  rows: ActivityRow[];
}

function ActivityRowList({ rows }: ActivityRowListProps) {
  const router = useRouter();

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2, flex: 1 }}>
      {rows.map((row, i) => (
        <button
          key={i}
          onClick={() => row.title !== "\u2014" && router.push(goToHref(row.go, row.id))}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: 12,
            borderRadius: 12,
            border: "none",
            background: "transparent",
            cursor: row.title !== "\u2014" ? "pointer" : "default",
            textAlign: "left",
            width: "100%",
            transition: "background 0.12s",
          }}
          onMouseEnter={(e) => {
            if (row.title !== "\u2014")
              (e.currentTarget as HTMLElement).style.background = "var(--color-surface)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLElement).style.background = "transparent";
          }}
        >
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              flexShrink: 0,
              background: tagStyle(row.tk).background,
            }}
          />
          {row.icon && (() => {
            const Icon = ROW_ICONS[row.icon] ?? Circle;
            return (
              <Icon size={14} strokeWidth={2} style={{ flexShrink: 0, color: "var(--color-text-secondary)" }} />
            );
          })()}
          <div style={{ minWidth: 0, flex: 1 }}>
            <div
              style={{
                fontFamily: "var(--font-body, Inter, sans-serif)",
                fontSize: 13.5,
                fontWeight: 600,
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
                display: "flex",
                alignItems: "baseline",
                gap: 6,
                marginTop: 1,
              }}
            >
              {row.sub && (
                <span
                  style={{
                    fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                    fontSize: 11,
                    color: "var(--color-text-secondary)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {row.sub}
                </span>
              )}
              {row.time && (
                <span
                  style={{
                    fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                    fontSize: 10.5,
                    color: "var(--color-text-tertiary, var(--color-text-secondary))",
                    whiteSpace: "nowrap",
                    flexShrink: 0,
                  }}
                >
                  {row.sub ? `· ${row.time}` : row.time}
                </span>
              )}
            </div>
          </div>
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
        </button>
      ))}
    </div>
  );
}

interface ActivityPanelProps {
  pTitle: string;
  pMeta: string;
  pRows: ActivityRow[];
  expandable?: boolean;
}

export function ActivityPanel({ pTitle, pMeta, pRows, expandable = false }: ActivityPanelProps) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const { rows: fullRows, isLoading: historyLoading } = useDashboardActivity(expandable && historyOpen);

  return (
    <div
      style={{
        background: "var(--color-surface-raised)",
        border: "1px solid var(--color-border)",
        borderRadius: 18,
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
          borderBottom: "1px solid var(--color-border)",
          paddingBottom: 12,
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
          {pTitle}
        </span>
        <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
          <span
            style={{
              fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
              fontSize: 11,
              color: "var(--color-text-secondary)",
            }}
          >
            {pMeta}
          </span>
          {expandable && (
            <button
              onClick={() => setHistoryOpen(true)}
              style={{
                fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                fontSize: 11,
                fontWeight: 600,
                color: "var(--color-brand-primary)",
                background: "transparent",
                border: "none",
                cursor: "pointer",
                padding: 0,
              }}
            >
              View all
            </button>
          )}
        </div>
      </div>

      <ActivityRowList rows={pRows} />

      {expandable && (
        <SlideOver open={historyOpen} onClose={() => setHistoryOpen(false)} width={480}>
          <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "20px 22px",
                borderBottom: "1px solid var(--color-border)",
              }}
            >
              <span
                style={{
                  fontFamily: "var(--font-display, 'Hanken Grotesk', sans-serif)",
                  fontSize: 16,
                  fontWeight: 700,
                  color: "var(--color-text-primary)",
                }}
              >
                Full activity history
              </span>
              <button
                onClick={() => setHistoryOpen(false)}
                aria-label="Close"
                style={{
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  fontSize: 18,
                  color: "var(--color-text-secondary)",
                }}
              >
                {"\u00d7"}
              </button>
            </div>
            <div style={{ padding: "12px 22px", overflowY: "auto", flex: 1 }}>
              {historyLoading ? (
                <div style={{ color: "var(--color-text-secondary)", fontSize: 13, padding: 12 }}>
                  Loading\u2026
                </div>
              ) : fullRows.length === 0 ? (
                <div style={{ color: "var(--color-text-secondary)", fontSize: 13, padding: 12 }}>
                  No activity yet.
                </div>
              ) : (
                <ActivityRowList rows={fullRows} />
              )}
            </div>
          </div>
        </SlideOver>
      )}
    </div>
  );
}
