"use client";

export interface PlaceholderScreenProps {
  title: string;
}

export function PlaceholderScreen({ title }: PlaceholderScreenProps) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-center">
      <h1 className="text-2xl font-semibold text-text-primary">{title}</h1>
      <p className="text-sm text-text-secondary">This screen is coming soon.</p>
    </div>
  );
}
