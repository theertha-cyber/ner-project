export type FilterTab = "all" | "pending_approval" | "running" | "completed" | "failed";

export interface JobFilterTabsProps {
  selected: FilterTab;
  onChange: (tab: FilterTab) => void;
}

const TABS: { value: FilterTab; label: string }[] = [
  { value: "all", label: "All" },
  { value: "pending_approval", label: "Pending Approval" },
  { value: "running", label: "Running" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
];

export function JobFilterTabs({ selected, onChange }: JobFilterTabsProps) {
  return (
    <div className="flex gap-1 border-b border-border pb-2">
      {TABS.map((tab) => (
        <button
          key={tab.value}
          type="button"
          onClick={() => onChange(tab.value)}
          className={[
            "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
            selected === tab.value
              ? "bg-brand-primary text-white"
              : "text-gray-600 hover:bg-gray-100",
          ].join(" ")}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
