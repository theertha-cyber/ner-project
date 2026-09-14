"use client";

interface TrainModelBannerProps {
  annotatedCount: number;
  onTrain: () => void;
}

export function TrainModelBanner({ annotatedCount, onTrain }: TrainModelBannerProps) {
  if (annotatedCount === 0) return null;

  return (
    <div
      style={{
        marginTop: 20,
        border: "1px solid var(--primary-line, rgba(166,0,0,0.22))",
        borderRadius: 12,
        background: "var(--surface-2)",
        padding: "16px 20px",
        display: "flex",
        alignItems: "center",
        gap: 16,
      }}
    >
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13.5, fontWeight: 600, color: "var(--ink)" }}>
          {annotatedCount} document{annotatedCount === 1 ? "" : "s"} annotated and ready for training.
        </div>
        <div style={{ fontSize: 12, color: "var(--ink-2)", marginTop: 2 }}>
          Kick off a training run once you&apos;re happy with coverage across your entity types.
        </div>
      </div>
      <button
        onClick={onTrain}
        style={{
          flexShrink: 0,
          padding: "9px 16px",
          borderRadius: 9,
          border: "none",
          background: "var(--primary)",
          color: "#fff",
          fontSize: 13,
          fontWeight: 600,
          cursor: "pointer",
          whiteSpace: "nowrap",
        }}
      >
        Train model →
      </button>
    </div>
  );
}
