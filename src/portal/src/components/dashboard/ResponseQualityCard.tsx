"use client";

import { ThumbsUp, ThumbsDown, CheckCircle2, AlertTriangle, Info } from "lucide-react";
import type { ResponseQuality, ResponseQualityStatus } from "@/types/dashboard";

const STATUS_META: Record<
  ResponseQualityStatus,
  { label: string; color: string; soft: string; icon: "check" | "warn" | "info" }
> = {
  healthy: { label: "Healthy", color: "var(--good, #16a34a)", soft: "var(--good-soft, rgba(22, 163, 74, 0.12))", icon: "check" },
  monitor: { label: "Monitor", color: "var(--warn, #d97706)", soft: "var(--warn-soft, rgba(217, 119, 6, 0.12))", icon: "warn" },
  needs_attention: { label: "Needs Attention", color: "var(--bad, #dc2626)", soft: "var(--bad-soft, rgba(220, 38, 38, 0.12))", icon: "warn" },
  no_data: { label: "Not Enough Data", color: "var(--color-text-secondary, #6b7280)", soft: "var(--color-border, rgba(107, 114, 128, 0.12))", icon: "info" },
};

function StatusIcon({ status }: { status: ResponseQualityStatus }) {
  const meta = STATUS_META[status];
  const props = { size: 14, color: meta.color };
  if (meta.icon === "check") return <CheckCircle2 {...props} />;
  if (meta.icon === "warn") return <AlertTriangle {...props} />;
  return <Info {...props} />;
}

interface ResponseQualityCardProps {
  data: ResponseQuality;
}

export function ResponseQualityCard({ data }: ResponseQualityCardProps) {
  const meta = STATUS_META[data.status];
  const hasData = data.rated > 0;
  const positivePct = hasData ? (data.positive / data.rated) * 100 : 0;
  const negativePct = hasData ? (data.negative / data.rated) * 100 : 0;

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
      {/* Header: title + status badge */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span
          style={{
            fontFamily: "var(--font-display, 'Hanken Grotesk', sans-serif)",
            fontSize: 15,
            fontWeight: 700,
            color: "var(--color-text-primary)",
          }}
        >
          Response Quality
        </span>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 5,
            padding: "3px 10px",
            borderRadius: 999,
            background: meta.soft,
            color: meta.color,
            fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
            fontSize: 11,
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.04em",
          }}
        >
          <StatusIcon status={data.status} />
          {meta.label}
        </span>
      </div>

      {/* Headline: satisfaction % + subtext */}
      <div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
          <span
            style={{
              fontFamily: "var(--font-display, 'Hanken Grotesk', sans-serif)",
              fontSize: 36,
              fontWeight: 800,
              color: hasData ? "var(--color-text-primary)" : "var(--color-text-secondary)",
              lineHeight: 1,
            }}
          >
            {hasData ? `${Math.round(data.satisfactionPct ?? 0)}%` : "—"}
          </span>
          <span style={{ fontFamily: "var(--font-body, Inter, sans-serif)", fontSize: 14, color: "var(--color-text-secondary)" }}>
            Positive Feedback
          </span>
        </div>
        <span style={{ display: "block", marginTop: 2, fontSize: 12, color: "var(--color-text-secondary)" }}>
          {hasData
            ? `${data.positive} of ${data.rated} reviewed responses were positive`
            : "No responses have been reviewed yet"}
        </span>
      </div>

      {/* Stacked bar: positive vs negative share of rated responses */}
      <div style={{ height: 10, borderRadius: 5, background: "var(--color-border)", overflow: "hidden", display: "flex" }}>
        {hasData ? (
          <>
            <div style={{ width: `${positivePct}%`, background: "var(--good, #16a34a)", transition: "width 0.6s ease" }} />
            <div style={{ width: `${negativePct}%`, background: "var(--bad, #dc2626)", transition: "width 0.6s ease" }} />
          </>
        ) : null}
      </div>

      {/* Business User Feedback: thumb counts */}
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
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
          Business User Feedback
        </span>
        <div style={{ display: "flex", gap: 20 }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 14, fontWeight: 600, color: "var(--color-text-primary)" }}>
            <ThumbsUp size={15} color="var(--good, #16a34a)" />
            {data.positive}
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 14, fontWeight: 600, color: "var(--color-text-primary)" }}>
            <ThumbsDown size={15} color="var(--bad, #dc2626)" />
            {data.negative}
          </span>
        </div>
        <span style={{ fontSize: 12, color: "var(--color-text-secondary)" }}>
          {data.rated} of {data.total} AI responses reviewed
        </span>
      </div>

      <div style={{ height: 1, background: "var(--color-border)" }} />

      {/* Recommendation */}
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
          Recommendation
        </span>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
          <span style={{ marginTop: 2 }}>
            <StatusIcon status={data.status} />
          </span>
          <span style={{ fontSize: 13, lineHeight: 1.4, color: "var(--color-text-primary)" }}>{data.recommendation}</span>
        </div>
      </div>
    </div>
  );
}
