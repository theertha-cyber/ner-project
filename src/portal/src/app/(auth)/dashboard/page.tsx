"use client";

import { useDashboardData } from "@/hooks/use-dashboard-data";
import { useAuth } from "@/lib/auth";
import { heroVariant } from "@/lib/dashboard";
import { DashboardHero } from "@/components/dashboard/DashboardHero";
import { StatCard } from "@/components/dashboard/StatCard";
import { StatCardSkeleton } from "@/components/dashboard/StatCardSkeleton";
import { ActivityPanel } from "@/components/dashboard/ActivityPanel";
import { MetricsPanel } from "@/components/dashboard/MetricsPanel";

function formatRoleLabel(role: string): string {
  return role.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function DashboardPage() {
  const { data, isLoading } = useDashboardData();
  const { user } = useAuth();
  const variant = heroVariant(user?.role ?? "annotator");
  const roleLabel = formatRoleLabel(user?.role ?? "annotator");

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
      {/* Breadcrumb */}
      <div
        style={{
          fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
          fontSize: 11,
          color: "var(--color-text-secondary)",
          letterSpacing: "0.06em",
        }}
      >
        DASHBOARD ◦ {roleLabel}
      </div>

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

      {/* Stat card strip */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14 }}>
        {isLoading || !data
          ? Array.from({ length: 4 }).map((_, i) => <StatCardSkeleton key={i} />)
          : data.stats.map((stat, i) => <StatCard key={i} item={stat} />)}
      </div>

      {/* Two-column panel grid: activity 1.5fr, metrics 1fr */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1.5fr 1fr",
          gap: 16,
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
