export type FilterTab = "all" | "running" | "pending_approval" | "completed" | "failed";

export interface JobFilterTabsProps {
  selected: FilterTab;
  onChange: (tab: FilterTab) => void;
}

const TABS: FilterTab[] = ["all", "running", "pending_approval", "completed", "failed"];

export function JobFilterTabs({ selected, onChange }: JobFilterTabsProps) {
  return (
    <div className="flex flex-wrap gap-1.5 font-body">
      {TABS.map((tab) => {
        const active = tab === selected;
        return (
          <button
            key={tab}
            type="button"
            onClick={() => onChange(tab)}
            className="rounded-md px-2.5 py-1.5 text-xs font-semibold transition-colors"
            style={{
              background: active ? "var(--ink)" : "var(--surface-2)",
              color: active ? "var(--surface-2)" : "var(--ink-2)",
              border: "1px solid var(--line)",
            }}
          >
            {tab.replace("_", " ")}
          </button>
        );
      })}
    </div>
  );
}
