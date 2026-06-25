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
    <div className="flex gap-1 border-b border-border pb-2">
      {TABS.map((tab) => (
        <button
          key={tab.value}
          type="button"
          onClick={() => onChange(tab.value)}
          className={[
            "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
            selected === tab.value
              ? "bg-brand-primary text-white"
              : "text-gray-600 hover:bg-gray-100",
          ].join(" ")}
        >
          {tab.label}
          {counts && (
            <span
              className={[
                "inline-flex size-5 items-center justify-center rounded-full text-xs",
                selected === tab.value
                  ? "bg-white/20 text-white"
                  : "bg-gray-200 text-gray-600",
              ].join(" ")}
            >
              {counts[tab.value]}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
