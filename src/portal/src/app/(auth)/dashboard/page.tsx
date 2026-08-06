"use client";

import { useDashboardData } from "@/hooks/use-dashboard-data";
import { useAuth } from "@/lib/auth";
import { heroVariant } from "@/lib/dashboard";
import { DashboardHero } from "@/components/dashboard/DashboardHero";
import { StatCard } from "@/components/dashboard/StatCard";
import { StatCardSkeleton } from "@/components/dashboard/StatCardSkeleton";
import { ActivityPanel } from "@/components/dashboard/ActivityPanel";
import { MetricsPanel } from "@/components/dashboard/MetricsPanel";
import { ResponseQualityCard } from "@/components/dashboard/ResponseQualityCard";
import { ActiveModelCard } from "@/components/dashboard/ActiveModelCard";

export default function DashboardPage() {
  const { data, isLoading } = useDashboardData();
  const { user } = useAuth();
  const variant = heroVariant(user?.role ?? "annotator");
  const isTenantAdmin = user?.role === "tenant_admin";

  return (
    <div
      className="animate-fade-up"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 28,
        padding: "28px 32px 60px",
        maxWidth: 1240,
        width: "100%",
        margin: "0 auto",
      }}
    >
      {/* Hero */}
      <div>
        {data ? (
          <DashboardHero
            kicker={data.kicker}
            title={data.title}
            line={data.line}
            variant={variant}
          />
        ) : (
          <DashboardHero
            kicker="Loading…"
            title=""
            line=""
            variant={variant}
          />
        )}
      </div>

      {/* Two-column panel grid: stat cards + pipeline activity (1.5fr), active model + quota (1fr) */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1.5fr 1fr",
          gap: 16,
        }}
      >
        {data ? (
          <>
            <div style={{ display: "flex", flexDirection: "column", gap: 14, minWidth: 0 }}>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: `repeat(${data.stats.length}, 1fr)`,
                  gap: 14,
                }}
              >
                {data.stats.map((stat, i) => <StatCard key={i} item={stat} />)}
              </div>
              <ActivityPanel
                pTitle={data.pTitle}
                pMeta={data.pMeta}
                pRows={data.pRows}
                expandable={isTenantAdmin}
              />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 14, minWidth: 0 }}>
              {isTenantAdmin ? (
                <ActiveModelCard data={data.activeModel} />
              ) : (
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
              )}
              {isTenantAdmin && data.responseQuality && (
                <ResponseQualityCard data={data.responseQuality} />
              )}
            </div>
          </>
        ) : (
          <>
            <div style={{ display: "flex", flexDirection: "column", gap: 14, minWidth: 0 }}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}>
                {Array.from({ length: 3 }).map((_, i) => <StatCardSkeleton key={i} />)}
              </div>
              <div
                style={{
                  background: "var(--color-surface-raised)",
                  border: "1px solid var(--color-border)",
                  borderRadius: "var(--radius-lg, 12px)",
                  height: 220,
                  animation: "sk-shimmer 1.4s ease infinite",
                }}
              />
            </div>
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
