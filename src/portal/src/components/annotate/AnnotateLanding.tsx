"use client";

import { ReactNode } from "react";
import { useRouter } from "next/navigation";

export interface GlanceStat {
  label: string;
  value: ReactNode;
  note?: string;
  href?: string;
  tone?: "default" | "warn" | "good";
}

export interface WorkCard {
  title: string;
  description: string;
  cta: string;
  href: string;
  count?: number;
}

interface AnnotateLandingProps {
  heading: string;
  intro: string;
  primaryAction?: { label: string; onClick: () => void; disabled?: boolean; disabledReason?: string };
  stats?: GlanceStat[];
  workCards?: WorkCard[];
  children?: ReactNode;
}

const toneColor: Record<NonNullable<GlanceStat["tone"]>, string> = {
  default: "var(--ink-3)",
  warn: "var(--bad)",
  good: "var(--good, #16a34a)",
};

export function AnnotateLanding({
  heading,
  intro,
  primaryAction,
  stats,
  workCards,
  children,
}: AnnotateLandingProps) {
  const router = useRouter();

  return (
    <div className="animate-fade-up" style={{ maxWidth: 960 }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: "var(--ink)", margin: 0 }}>{heading}</h1>
          <p style={{ fontSize: 13.5, color: "var(--ink-2)", marginTop: 6, maxWidth: 620, lineHeight: 1.5 }}>
            {intro}
          </p>
        </div>
        {primaryAction && (
          <div style={{ textAlign: "right" }}>
            <button
              onClick={primaryAction.onClick}
              disabled={primaryAction.disabled}
              style={{
                padding: "9px 16px",
                borderRadius: 9,
                border: "none",
                background: primaryAction.disabled ? "var(--surface-3)" : "var(--primary)",
                color: primaryAction.disabled ? "var(--ink-3)" : "#fff",
                fontSize: 13,
                fontWeight: 600,
                cursor: primaryAction.disabled ? "not-allowed" : "pointer",
                whiteSpace: "nowrap",
              }}
            >
              {primaryAction.label}
            </button>
            {primaryAction.disabled && primaryAction.disabledReason && (
              <div style={{ fontSize: 11, color: "var(--bad)", marginTop: 4 }}>
                {primaryAction.disabledReason}
              </div>
            )}
          </div>
        )}
      </div>

      {stats && stats.length > 0 && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: `repeat(${Math.min(stats.length, 3)}, 1fr)`,
            gap: 12,
            marginTop: 20,
          }}
        >
          {stats.map((s) => (
            <button
              key={s.label}
              onClick={() => s.href && router.push(s.href)}
              style={{
                textAlign: "left",
                border: "1px solid var(--line)",
                borderRadius: 12,
                background: "var(--surface-2)",
                padding: "14px 16px",
                cursor: s.href ? "pointer" : "default",
              }}
            >
              <div style={{ fontSize: 24, fontWeight: 700, color: "var(--ink)" }}>{s.value}</div>
              <div style={{ fontSize: 12, color: "var(--ink-2)", marginTop: 2 }}>{s.label}</div>
              {s.note && (
                <div style={{ fontSize: 11, color: toneColor[s.tone ?? "default"], marginTop: 4 }}>
                  {s.note}
                </div>
              )}
            </button>
          ))}
        </div>
      )}

      {workCards && workCards.length > 0 && (
        <>
          <div
            style={{
              fontFamily: "var(--font-mono, monospace)",
              fontSize: 10,
              fontWeight: 600,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              color: "var(--ink-3)",
              marginTop: 26,
              marginBottom: 10,
            }}
          >
            Where the work is
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 12 }}>
            {workCards.map((c) => (
              <div
                key={c.href}
                style={{
                  border: "1px solid var(--line)",
                  borderRadius: 12,
                  background: "var(--surface-2)",
                  padding: 16,
                  display: "flex",
                  flexDirection: "column",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 14, fontWeight: 600, color: "var(--ink)" }}>{c.title}</span>
                  {c.count != null && (
                    <span
                      style={{
                        fontFamily: "var(--font-mono, monospace)",
                        fontSize: 11,
                        fontWeight: 600,
                        padding: "1px 7px",
                        borderRadius: 20,
                        background: "var(--primary-soft)",
                        color: "var(--primary)",
                      }}
                    >
                      {c.count}
                    </span>
                  )}
                </div>
                <p style={{ fontSize: 12.5, color: "var(--ink-2)", margin: "6px 0 14px", lineHeight: 1.5, flex: 1 }}>
                  {c.description}
                </p>
                <button
                  onClick={() => router.push(c.href)}
                  style={{
                    alignSelf: "flex-start",
                    padding: "7px 13px",
                    borderRadius: 8,
                    border: "1px solid var(--line)",
                    background: "transparent",
                    color: "var(--ink)",
                    fontSize: 12.5,
                    fontWeight: 500,
                    cursor: "pointer",
                  }}
                >
                  {c.cta} →
                </button>
              </div>
            ))}
          </div>
        </>
      )}

      {children}
    </div>
  );
}
