"use client";

export interface StatCardProps {
  label: string;
  value: string;
  unit?: string;
  delta?: string;
  deltaDir?: "up" | "warn" | "neutral";
  sub?: string;
}

const deltaDirClasses: Record<string, string> = {
  up: "text-delta-up",
  warn: "text-delta-warn",
  neutral: "text-delta-neutral",
};

export function StatCard({ label, value, unit, delta, deltaDir = "neutral", sub }: StatCardProps) {
  return (
    <div className="rounded-lg bg-surface p-4 shadow-card">
      <p className="text-xs font-medium uppercase tracking-wide text-text-secondary">{label}</p>
      <div className="mt-1 flex items-baseline gap-1">
        <span className="text-2xl font-semibold text-text-primary">{value}</span>
        {unit && <span className="text-sm text-text-secondary">{unit}</span>}
      </div>
      {delta !== undefined && (
        <p
          data-testid="delta"
          className={`mt-1 text-xs font-medium ${deltaDirClasses[deltaDir] ?? deltaDirClasses.neutral}`}
        >
          {delta}
        </p>
      )}
      {sub && <p className="mt-1 text-xs text-text-secondary">{sub}</p>}
    </div>
  );
}
