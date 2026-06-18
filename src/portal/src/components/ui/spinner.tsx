"use client";

export interface SpinnerProps {
  size?: "sm" | "md";
}

const sizeClasses: Record<string, string> = {
  sm: "size-4 border-2",
  md: "size-6 border-2",
};

export function Spinner({ size = "md" }: SpinnerProps) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={[
        "inline-block animate-spin rounded-full border-brand-primary border-t-transparent",
        sizeClasses[size],
      ].join(" ")}
    />
  );
}
