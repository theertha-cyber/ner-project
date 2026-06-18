"use client";

export interface MiniBarProps {
  used: number;
  max: number;
}

export function MiniBar({ used, max }: MiniBarProps) {
  const ratio = max > 0 ? used / max : 0;
  const pct = Math.min(Math.max(ratio * 100, 0), 100);
  const fillClass = ratio >= 0.9 ? "bg-warning" : "bg-brand-primary";

  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-border">
      <div
        data-testid="mini-bar-fill"
        className={`h-full rounded-full transition-all ${fillClass}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
