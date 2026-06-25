"use client";

interface ArmedBannerProps {
  entityType: string;
  description?: string | null;
  onDisarm: () => void;
}

export function ArmedBanner({ entityType, description, onDisarm }: ArmedBannerProps) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "8px 16px",
        background: "rgba(194,65,12,0.08)",
        borderBottom: "1px solid rgba(194,65,12,0.2)",
        flexShrink: 0,
      }}
      data-testid="armed-banner"
    >
      <span
        className="armed-dot"
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: "var(--color-brand-primary)",
          display: "inline-block",
          flexShrink: 0,
          animation: "pulse 1.3s infinite",
        }}
      />
      <span style={{ fontSize: 13, color: "var(--color-text-primary)", fontWeight: 500 }}>
        Labeling mode · click words to tag as <strong>{entityType}</strong>
      </span>
      <button
        onClick={onDisarm}
        style={{
          marginLeft: "auto",
          background: "none",
          border: "none",
          cursor: "pointer",
          color: "var(--color-text-secondary)",
          fontSize: 12,
          fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
          padding: "2px 8px",
          borderRadius: 4,
        }}
        aria-label="Disarm entity type"
      >
        esc · done
      </button>
    </div>
  );
}
