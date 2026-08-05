"use client";

import { FilterSelect } from "@/components/ui/filter-select";

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
  const options = TABS.map((tab) => ({
    value: tab.value,
    label: counts ? `${tab.label} (${counts[tab.value]})` : tab.label,
  }));

  return <FilterSelect value={selected} onChange={onChange} options={options} ariaLabel="Filter by status" />;
}
