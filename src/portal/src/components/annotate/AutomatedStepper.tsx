"use client";

import { usePathname, useRouter } from "next/navigation";

export type StepState = "done" | "current" | "ready" | "blocked";

export interface StepDef {
  num: number;
  title: string;
  href: string;
  state: StepState;
  sub?: string;
}

const stateStyle: Record<StepState, { dot: string; text: string }> = {
  done: { dot: "var(--good, #16a34a)", text: "var(--ink)" },
  current: { dot: "var(--primary)", text: "var(--ink)" },
  ready: { dot: "var(--ink-3)", text: "var(--ink-2)" },
  blocked: { dot: "var(--line)", text: "var(--ink-3)" },
};

/**
 * Persistent header across the four automated step routes. Blocked steps stay
 * clickable — navigating to one shows its own "why you can't proceed" copy.
 */
export function AutomatedStepper({ steps }: { steps: StepDef[] }) {
  const router = useRouter();
  const pathname = usePathname();

  return (
    <div
      style={{
        display: "flex",
        gap: 4,
        border: "1px solid var(--line)",
        borderRadius: 12,
        background: "var(--surface-2)",
        padding: 8,
        marginBottom: 20,
        overflowX: "auto",
      }}
    >
      {steps.map((s, i) => {
        const active = pathname === s.href.split("?")[0];
        const st = stateStyle[s.state];
        return (
          <button
            key={s.num}
            onClick={() => router.push(s.href)}
            style={{
              flex: 1,
              minWidth: 150,
              display: "flex",
              flexDirection: "column",
              gap: 3,
              alignItems: "flex-start",
              padding: "8px 12px",
              borderRadius: 9,
              border: "none",
              background: active ? "var(--primary-soft)" : "transparent",
              cursor: "pointer",
              textAlign: "left",
            }}
          >
            <span style={{ display: "flex", alignItems: "center", gap: 7 }}>
              <span
                style={{
                  width: 9,
                  height: 9,
                  borderRadius: 3,
                  background: st.dot,
                  flexShrink: 0,
                }}
              />
              <span
                style={{
                  fontFamily: "var(--font-mono, monospace)",
                  fontSize: 11,
                  color: "var(--ink-3)",
                }}
              >
                {s.num} / {steps.length}
              </span>
            </span>
            <span style={{ fontSize: 13, fontWeight: active ? 600 : 500, color: st.text }}>{s.title}</span>
            {s.sub && <span style={{ fontSize: 11, color: "var(--ink-3)" }}>{s.sub}</span>}
          </button>
        );
      })}
    </div>
  );
}
