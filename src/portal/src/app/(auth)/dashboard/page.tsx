"use client";

import { useDashboardData } from "@/hooks/use-dashboard-data";
import { useLayoutPreference } from "@/hooks/use-layout-preference";
import { DashboardHero } from "@/components/dashboard/DashboardHero";
import { StatCard } from "@/components/dashboard/StatCard";
import { StatCardSkeleton } from "@/components/dashboard/StatCardSkeleton";
import { ActivityPanel } from "@/components/dashboard/ActivityPanel";
import { MetricsPanel } from "@/components/dashboard/MetricsPanel";
import { SegmentControl } from "@/components/ui";

export default function DashboardPage() {
  const { data, isLoading } = useDashboardData();
  const [layout, setLayout] = useLayoutPreference();

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 28,
        padding: "28px 32px",
        maxWidth: 1280,
        width: "100%",
        margin: "0 auto",
      }}
    >
      {/* Hero + layout toggle */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          {data ? (
            <DashboardHero
              kicker={data.kicker}
              title={data.title}
              line={data.line}
              layout={layout}
            />
          ) : (
            <DashboardHero
              kicker="Loading…"
              title=""
              line=""
              layout={layout}
            />
          )}
        </div>
        <div style={{ flexShrink: 0 }}>
          <SegmentControl
            options={[
              { label: "Editorial", value: "editorial" },
              { label: "Command", value: "command" },
            ]}
            value={layout}
            onChange={(v) => setLayout(v as "editorial" | "command")}
          />
        </div>
      </div>

      {/* Stat card strip */}
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
        {isLoading || !data
          ? Array.from({ length: 4 }).map((_, i) => <StatCardSkeleton key={i} />)
          : data.stats.map((stat, i) => <StatCard key={i} item={stat} />)}
      </div>

      {/* Two-column panel grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 14,
        }}
      >
        {data ? (
          <>
            <ActivityPanel
              pTitle={data.pTitle}
              pMeta={data.pMeta}
              pRows={data.pRows}
            />
            <MetricsPanel
              sideTop={data.sideTop}
              sideMeta={data.sideMeta}
              big={data.big}
              bigUnit={data.bigUnit}
              bar={data.bar}
              sideMetrics={data.sideMetrics}
              sideBot={data.sideBot}
              sideRows={data.sideRows}
            />
          </>
        ) : (
          <>
            <div
              style={{
                background: "var(--color-surface-raised)",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-lg, 12px)",
                height: 220,
                animation: "sk-shimmer 1.4s ease infinite",
              }}
            />
            <div
              style={{
                background: "var(--color-surface-raised)",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-lg, 12px)",
                height: 220,
                animation: "sk-shimmer 1.4s ease infinite",
              }}
            />
          </>
        )}
      </div>
    </div>
  );
}
