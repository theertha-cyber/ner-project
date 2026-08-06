"use client";

import Link from "next/link";
import type { ContinueWork, ContinueWorkMode } from "@/types/dashboard";

interface ContinueWorkCardProps {
  data?: ContinueWork | null;
  isLoading?: boolean;
}

const MODE_LABEL: Record<ContinueWorkMode, string> = {
  resume: "Resume",
  start: "Start",
  review: "Review",
};

// "review" describes work already submitted, so its caption must not imply
// anything is outstanding — the card is a pointer back, not a to-do.
const MODE_CAPTION: Record<ContinueWorkMode, (spans: number) => string> = {
  resume: (spans) => `${spans} ${spans === 1 ? "entity" : "entities"} so far`,
  start: () => "Not started yet",
  review: (spans) => `Submitted with ${spans} ${spans === 1 ? "entity" : "entities"}`,
};

const cardStyle: React.CSSProperties = {
  background: "var(--color-surface-raised)",
  border: "1px solid var(--color-border)",
  borderRadius: 16,
  padding: "20px 22px",
  display: "flex",
  flexDirection: "column",
  gap: 6,
  minWidth: 0,
  transition: "transform 0.15s ease, border-color 0.15s ease",
};

const labelStyle: React.CSSProperties = {
  fontFamily: "var(--font-body, Inter, sans-serif)",
  fontSize: 12,
  fontWeight: 500,
  color: "var(--color-text-secondary)",
};

export function ContinueWorkCard({ data, isLoading = false }: ContinueWorkCardProps) {
  if (isLoading) {
    return (
      <div style={cardStyle} data-testid="continue-work-skeleton">
        <style>{`
          @keyframes sk-shimmer { 0% { opacity: 0.45; } 50% { opacity: 1; } 100% { opacity: 0.45; } }
          .cw-bone { background: var(--color-border); border-radius: 4px; animation: sk-shimmer 1.4s ease infinite; }
        `}</style>
        <div className="cw-bone" style={{ height: 11, width: "60%" }} />
        <div className="cw-bone" style={{ height: 20, width: "85%" }} />
        <div className="cw-bone" style={{ height: 11, width: "45%" }} />
      </div>
    );
  }

  if (!data) {
    return (
      <div style={cardStyle} data-testid="continue-work-card">
        <span style={labelStyle}>Continue where you left off</span>
        <span
          style={{
            fontFamily: "var(--font-display, 'Hanken Grotesk', sans-serif)",
            fontSize: 18,
            fontWeight: 700,
            color: "var(--color-text-primary)",
            lineHeight: 1.2,
          }}
        >
          You&rsquo;re all caught up
        </span>
        <span
          style={{
            fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
            fontSize: 10.5,
            color: "var(--color-text-tertiary, #94a3b8)",
          }}
        >
          No tasks waiting
        </span>
      </div>
    );
  }

  const action = MODE_LABEL[data.mode] ?? "Open";
  const caption = (MODE_CAPTION[data.mode] ?? MODE_CAPTION.resume)(data.spanCount);

  return (
    <div
      style={cardStyle}
      data-testid="continue-work-card"
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.transform = "translateY(-2px)";
        (e.currentTarget as HTMLElement).style.borderColor = "var(--primary-line)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.transform = "";
        (e.currentTarget as HTMLElement).style.borderColor = "var(--color-border)";
      }}
    >
      <span style={labelStyle}>Continue where you left off</span>
      {/* The card shares a three-column row, so the filename gets one line with
          ellipsis truncation and the full name stays reachable via `title`. */}
      <span
        title={data.documentName}
        style={{
          fontFamily: "var(--font-display, 'Hanken Grotesk', sans-serif)",
          fontSize: 18,
          fontWeight: 700,
          color: "var(--color-text-primary)",
          lineHeight: 1.2,
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
          display: "block",
          maxWidth: "100%",
        }}
      >
        {data.documentName}
      </span>
      <span
        style={{
          fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
          fontSize: 10.5,
          color: "var(--color-text-tertiary, #94a3b8)",
        }}
      >
        {caption}
      </span>
      <Link
        href={`/annotation?task=${encodeURIComponent(data.taskId)}`}
        style={{
          marginTop: 4,
          alignSelf: "flex-start",
          fontFamily: "var(--font-body, Inter, sans-serif)",
          fontSize: 12,
          fontWeight: 600,
          color: "var(--color-brand-primary)",
          textDecoration: "none",
        }}
      >
        {action} &rarr;
      </Link>
    </div>
  );
}
