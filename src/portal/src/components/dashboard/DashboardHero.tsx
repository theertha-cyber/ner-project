"use client";

interface DashboardHeroProps {
  kicker: string;
  title: string;
  line: string;
  variant?: "a" | "b";
}

const VARIANT_B_ORBS = [
  {
    style: { top: "-20%", left: "-10%", width: "60%", height: "160%" },
    background: "radial-gradient(circle, #c2410c, transparent 60%)",
    animation: "meshDrift 18s ease-in-out infinite alternate",
  },
  {
    style: { bottom: "-20%", right: "-10%", width: "60%", height: "160%" },
    background: "radial-gradient(circle, #475569, transparent 60%)",
    animation: "meshDrift 23s ease-in-out infinite alternate-reverse",
  },
];

export function DashboardHero({ kicker, title, line, variant = "a" }: DashboardHeroProps) {
  if (variant === "b") {
    return (
      <div
        style={{
          position: "relative",
          overflow: "hidden",
          background: "#0f172a",
          borderRadius: 24,
          padding: "28px 32px",
          isolation: "isolate",
        }}
      >
        {VARIANT_B_ORBS.map((orb, i) => (
          <div
            key={i}
            style={{
              position: "absolute",
              borderRadius: "50%",
              filter: "blur(60px)",
              pointerEvents: "none",
              background: orb.background,
              animation: orb.animation,
              ...orb.style,
            }}
          />
        ))}

        <div style={{ position: "relative", zIndex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
          <span
            style={{
              fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
              fontSize: 11,
              fontWeight: 600,
              color: "#fff",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
            }}
          >
            {kicker}
          </span>
          <h1
            style={{
              fontFamily: "var(--font-display, 'Hanken Grotesk', sans-serif)",
              fontSize: 38,
              fontWeight: 800,
              color: "#fff",
              margin: 0,
              lineHeight: 1.02,
            }}
          >
            {title}
          </h1>
          <p
            style={{
              fontFamily: "var(--font-body, Inter, sans-serif)",
              fontSize: 15,
              color: "rgba(255,255,255,0.85)",
              margin: 0,
              lineHeight: 1.6,
              maxWidth: "560px",
            }}
          >
            {line}
          </p>
        </div>
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
          fontSize: 38,
          fontWeight: 800,
          color: "var(--color-text-primary)",
          margin: 0,
          lineHeight: 1.02,
        }}
      >
        {title}
      </h1>
      <p
        style={{
          fontFamily: "var(--font-body, Inter, sans-serif)",
          fontSize: 15,
          color: "var(--color-text-secondary)",
          margin: 0,
          lineHeight: 1.6,
          maxWidth: "560px",
        }}
      >
        {line}
      </p>
    </div>
  );
}
