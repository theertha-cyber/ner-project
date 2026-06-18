"use client";

export function StatCardSkeleton() {
  return (
    <div
      style={{
        background: "var(--color-surface-raised)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-lg, 12px)",
        padding: "20px 22px",
        display: "flex",
        flexDirection: "column",
        gap: 8,
        flex: 1,
        minWidth: 0,
      }}
    >
      <style>{`
        @keyframes sk-shimmer {
          0%   { opacity: 0.45; }
          50%  { opacity: 1;    }
          100% { opacity: 0.45; }
        }
        .sk-bone {
          background: var(--color-border);
          border-radius: 4px;
          animation: sk-shimmer 1.4s ease infinite;
        }
      `}</style>
      <div className="sk-bone" style={{ height: 11, width: "60%" }} />
      <div className="sk-bone" style={{ height: 28, width: "50%" }} />
      <div className="sk-bone" style={{ height: 11, width: "70%" }} />
      <div className="sk-bone" style={{ height: 11, width: "40%" }} />
    </div>
  );
}
