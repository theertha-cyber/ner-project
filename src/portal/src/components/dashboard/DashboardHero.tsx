"use client";

interface DashboardHeroProps {
  kicker: string;
  title: string;
  line: string;
  layout: "editorial" | "command";
}

export function DashboardHero({ kicker, title, line, layout }: DashboardHeroProps) {
  if (layout === "command") {
    return (
      <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
        <span
          style={{
            fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
            fontSize: 11,
            fontWeight: 600,
            color: "var(--color-text-secondary)",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            flexShrink: 0,
          }}
        >
          {kicker}
        </span>
        <span
          style={{
            fontFamily: "var(--font-display, 'Hanken Grotesk', sans-serif)",
            fontSize: 16,
            fontWeight: 700,
            color: "var(--color-text-primary)",
          }}
        >
          {title}
        </span>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <span
        style={{
          fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
          fontSize: 11,
          fontWeight: 600,
          color: "var(--color-text-secondary)",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
        }}
      >
        {kicker}
      </span>
      <h1
        style={{
          fontFamily: "var(--font-display, 'Hanken Grotesk', sans-serif)",
          fontSize: 30,
          fontWeight: 700,
          color: "var(--color-text-primary)",
          margin: 0,
          lineHeight: 1.15,
        }}
      >
        {title}
      </h1>
      <p
        style={{
          fontFamily: "var(--font-body, Inter, sans-serif)",
          fontSize: 14,
          color: "var(--color-text-secondary)",
          margin: 0,
          lineHeight: 1.6,
          maxWidth: "72ch",
        }}
      >
        {line}
      </p>
    </div>
  );
}
