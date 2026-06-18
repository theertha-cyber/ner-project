"use client";

import { useRef, KeyboardEvent } from "react";

export interface SegmentOption {
  label: string;
  value: string;
}

export interface SegmentControlProps {
  options: SegmentOption[];
  value: string;
  onChange: (value: string) => void;
}

export function SegmentControl({ options, value, onChange }: SegmentControlProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  function handleKeyDown(e: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next = index;
    if (e.key === "ArrowRight") next = Math.min(index + 1, options.length - 1);
    else if (e.key === "ArrowLeft") next = Math.max(index - 1, 0);
    else return;

    e.preventDefault();
    const buttons = containerRef.current?.querySelectorAll("button");
    (buttons?.[next] as HTMLButtonElement | undefined)?.focus();
  }

  return (
    <div
      ref={containerRef}
      role="group"
      className="inline-flex rounded-md border border-border bg-surface-raised p-0.5"
    >
      {options.map((opt, i) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(opt.value)}
            onKeyDown={(e) => handleKeyDown(e, i)}
            className={[
              "rounded px-3 py-1 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-border-focus",
              active
                ? "bg-brand-primary text-white"
                : "text-text-secondary hover:text-text-primary",
            ].join(" ")}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
