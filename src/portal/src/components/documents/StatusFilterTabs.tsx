"use client";

export type FilterTab = "all" | "pending" | "processing" | "processed" | "failed";

export interface StatusFilterTabsProps {
  selected: FilterTab;
  onChange: (tab: FilterTab) => void;
  counts?: Record<FilterTab, number>;
}

const TABS: { value: FilterTab; label: string }[] = [
  { value: "all", label: "All" },
  { value: "pending", label: "Pending" },
  { value: "processing", label: "Processing" },
  { value: "processed", label: "Processed" },
  { value: "failed", label: "Failed" },
];

export function StatusFilterTabs({ selected, onChange, counts }: StatusFilterTabsProps) {
  return (
    <div className="flex gap-1 border-b pb-2" style={{ borderColor: "var(--line)" }}>
      {TABS.map((tab) => (
        <button
          key={tab.value}
          type="button"
          onClick={() => onChange(tab.value)}
          className={[
            "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
            selected === tab.value
              ? "bg-brand-primary text-white"
              : "",
          ].join(" ")}
          style={selected !== tab.value ? { color: "var(--ink-2)" } : undefined}
        >
          {tab.label}
          {counts && (
            <span
              className={[
                "inline-flex size-5 items-center justify-center rounded-full text-xs",
                selected === tab.value
                  ? "bg-white/20 text-white"
                  : "",
              ].join(" ")}
              style={selected !== tab.value ? { background: "var(--surface-3)", color: "var(--ink-2)" } : undefined}
            >
              {counts[tab.value]}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
