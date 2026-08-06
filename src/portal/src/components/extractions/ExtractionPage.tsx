"use client";

import { useState } from "react";
import { PlaygroundTab } from "./PlaygroundTab";
import { BatchRunsTab } from "./BatchRunsTab";
import { EntityReviewTab } from "./EntityReviewTab";

type ActiveTab = "playground" | "batch" | "entities";

const TABS: { value: ActiveTab; label: string }[] = [
  { value: "playground", label: "Playground" },
  { value: "batch", label: "Batch Runs" },
  { value: "entities", label: "Entity Review" },
];

export function ExtractionPage() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("playground");

  return (
    <div
      style={{
        padding: "28px 32px 60px",
        maxWidth: 1180,
        margin: "0 auto",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        boxSizing: "border-box",
      }}
    >
      <header className="mb-6" style={{ flexShrink: 0 }}>
        <h1 className="font-display text-[34px] font-extrabold text-text-primary leading-none">
          Extraction
        </h1>
      </header>

      <div
        className="inline-flex mb-6"
        style={{
          background: "var(--surface-2)",
          border: "1px solid var(--line)",
          borderRadius: 12,
          padding: 4,
          flexShrink: 0,
          alignSelf: "flex-start",
        }}
        role="group"
        aria-label="Extraction tabs"
      >
        {TABS.map((tab) => {
          const active = tab.value === activeTab;
          return (
            <button
              key={tab.value}
              type="button"
              onClick={() => setActiveTab(tab.value)}
              aria-pressed={active}
              className={[
                "rounded-lg px-4 py-1.5 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary",
                active
                  ? "text-white"
                  : "text-text-secondary hover:text-text-primary",
              ].join(" ")}
              style={active ? { background: "var(--primary)" } : undefined}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {activeTab === "playground" && <PlaygroundTab />}
      {activeTab === "batch" && (
        <div style={{ flex: 1, minHeight: 0, display: "flex", overflow: "hidden" }}>
          <BatchRunsTab />
        </div>
      )}
      {activeTab === "entities" && <EntityReviewTab />}
    </div>
  );
}
