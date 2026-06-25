"use client";

import { useState, useMemo } from "react";
import { useDashboardWidgets, useAnalyticsQuery, useExportAnalytics, useRefreshDashboard } from "@/hooks/use-analytics-data";
import { Spinner } from "@/components/ui/spinner";
import type { AnalyticsFilters } from "@/types/analytics";

function CoverageChart({ data }: { data: { entity_type: string; coverage_pct: number }[] }) {
  if (data.length === 0) return <p className="text-sm text-text-secondary">No extraction data yet</p>;
  return (
    <div className="space-y-2">
      {data.map((item) => (
        <div key={item.entity_type}>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-text-primary font-medium">{item.entity_type}</span>
            <span className="text-text-secondary">{item.coverage_pct.toFixed(1)}%</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-border">
            <div className="h-full rounded-full bg-brand-primary transition-all" style={{ width: `${item.coverage_pct}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function ConfidenceChart({ buckets }: { buckets: { label: string; count: number }[] }) {
  if (buckets.length === 0) return <p className="text-sm text-text-secondary">No extraction data yet</p>;
  const maxCount = Math.max(...buckets.map((b) => b.count), 1);
  return (
    <div className="flex items-end gap-2 h-32">
      {buckets.map((bucket) => (
        <div key={bucket.label} className="flex flex-col items-center flex-1">
          <div className="relative w-full flex-1 flex flex-col justify-end">
            <div
              className="w-full bg-brand-primary rounded-t transition-all"
              style={{ height: `${(bucket.count / maxCount) * 100}%`, minHeight: "4px" }}
            />
          </div>
          <span className="text-[10px] text-text-secondary mt-1 truncate w-full text-center">{bucket.label}</span>
          <span className="text-[10px] text-text-primary font-medium">{bucket.count}</span>
        </div>
      ))}
    </div>
  );
}

function VolumeChart({ data }: { data: { date: string; count: number }[] }) {
  if (data.length === 0) return <p className="text-sm text-text-secondary">No extraction data yet</p>;
  const maxCount = Math.max(...data.map((d) => d.count), 1);
  const visible = data.slice(-14);
  return (
    <div className="space-y-1">
      {visible.map((point) => (
        <div key={point.date} className="flex items-center gap-2 text-xs">
          <span className="text-text-secondary w-20 shrink-0">{point.date}</span>
          <div className="flex-1 h-3 overflow-hidden rounded bg-border">
            <div className="h-full rounded bg-brand-primary transition-all" style={{ width: `${(point.count / maxCount) * 100}%` }} />
          </div>
          <span className="text-text-primary font-medium w-8 text-right">{point.count}</span>
        </div>
      ))}
    </div>
  );
}

function DocCountChart({ data }: { data: { entity_type: string; avg_per_document: number }[] }) {
  if (data.length === 0) return <p className="text-sm text-text-secondary">No extraction data yet</p>;
  const maxVal = Math.max(...data.map((d) => d.avg_per_document), 1);
  return (
    <div className="space-y-2">
      {data.map((item) => (
        <div key={item.entity_type}>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-text-primary font-medium">{item.entity_type}</span>
            <span className="text-text-secondary">{item.avg_per_document.toFixed(1)} / doc</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-border">
            <div className="h-full rounded-full bg-brand-primary transition-all" style={{ width: `${(item.avg_per_document / maxVal) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

interface ResultsTableProps {
  results: { id: string; entity_type: string; value: string; confidence: number | null; document_id: string; extracted_at: string | null }[];
}

function ResultsTable({ results }: ResultsTableProps) {
  if (results.length === 0) return <p className="text-sm text-text-secondary py-8 text-center">No matching entities found</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-text-secondary border-b border-border">
            <th className="text-left py-2 pr-3 font-medium">Type</th>
            <th className="text-left py-2 pr-3 font-medium">Value</th>
            <th className="text-right py-2 pr-3 font-medium">Confidence</th>
            <th className="text-left py-2 font-medium">Date</th>
          </tr>
        </thead>
        <tbody>
          {results.map((r) => (
            <tr key={r.id} className="border-b border-border/50">
              <td className="py-2 pr-3 text-text-primary font-medium">{r.entity_type}</td>
              <td className="py-2 pr-3 text-text-primary">{r.value}</td>
              <td className="py-2 pr-3 text-right text-text-secondary">{r.confidence !== null ? (r.confidence * 100).toFixed(0) + "%" : "-"}</td>
              <td className="py-2 text-text-secondary">{r.extracted_at?.split("T")[0] ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function WidgetCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg bg-surface p-4 shadow-card border border-border">
      <h3 className="text-sm font-semibold text-text-primary mb-3">{title}</h3>
      {children}
    </div>
  );
}

function WidgetSkeleton() {
  return (
    <div className="rounded-lg bg-surface p-4 shadow-card border border-border">
      <div className="h-4 w-32 bg-border rounded animate-pulse mb-3" />
      <div className="space-y-2">
        <div className="h-3 bg-border rounded animate-pulse" />
        <div className="h-3 w-3/4 bg-border rounded animate-pulse" />
        <div className="h-3 w-1/2 bg-border rounded animate-pulse" />
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  const { data: widgets, isLoading: widgetsLoading, isError: widgetsError, refetch: refetchWidgets } = useDashboardWidgets();
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<AnalyticsFilters>({
    entity_types: [],
    date_from: "",
    date_to: "",
    confidence_min: "",
    confidence_max: "",
  });
  const [entityTypeInput, setEntityTypeInput] = useState("");
  const [queryEnabled, setQueryEnabled] = useState(false);

  const { data: queryResult, isLoading: queryLoading } = useAnalyticsQuery(filters, queryEnabled);
  const exportMutation = useExportAnalytics();
  const refreshMutation = useRefreshDashboard();

  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const addEntityType = () => {
    if (entityTypeInput && !filters.entity_types.includes(entityTypeInput.toUpperCase())) {
      setFilters((prev) => ({ ...prev, entity_types: [...prev.entity_types, entityTypeInput.toUpperCase()] }));
      setEntityTypeInput("");
    }
  };

  const removeEntityType = (type: string) => {
    setFilters((prev) => ({ ...prev, entity_types: prev.entity_types.filter((t) => t !== type) }));
  };

  const handleQuery = () => {
    setQueryEnabled(true);
    setErrorMessage(null);
  };

  const handleExport = (format: "csv" | "json") => {
    exportMutation.mutate({ filters, format }, {
      onError: () => setErrorMessage("Export failed. Please try again."),
    });
  };

  const handleRefresh = () => {
    refreshMutation.mutate(undefined, {
      onSuccess: () => refetchWidgets(),
      onError: () => setErrorMessage("Failed to refresh dashboard data."),
    });
  };

  if (widgetsError && !widgets) {
    return (
      <div className="p-8">
        <div className="rounded-lg bg-warning/10 border border-warning/30 p-4">
          <p className="text-sm text-warning font-medium">Unable to load analytics data</p>
          <button onClick={() => refetchWidgets()} className="mt-2 text-xs text-brand-primary hover:underline">
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-up flex flex-col gap-6 p-8 max-w-7xl mx-auto w-full">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-text-primary">Analytics & Reporting</h1>
        <div className="flex gap-2">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="px-3 py-1.5 text-xs font-medium rounded-md border border-border bg-surface hover:bg-border transition-colors text-text-primary"
          >
            {showFilters ? "Hide Filters" : "Query Data"}
          </button>
          <button
            onClick={handleRefresh}
            disabled={refreshMutation.isPending}
            className="px-3 py-1.5 text-xs font-medium rounded-md bg-brand-primary text-white hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {refreshMutation.isPending ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </div>

      {errorMessage && (
        <div className="rounded-lg bg-warning/10 border border-warning/30 p-3 flex items-center justify-between">
          <p className="text-sm text-warning">{errorMessage}</p>
          <button onClick={() => setErrorMessage(null)} className="text-xs text-text-secondary hover:text-text-primary">Dismiss</button>
        </div>
      )}

      {showFilters && (
        <div className="rounded-lg bg-surface p-4 shadow-card border border-border space-y-3">
          <div className="flex flex-wrap gap-3 items-end">
            <div className="flex flex-col gap-1">
              <label className="text-[10px] uppercase tracking-wide text-text-secondary font-medium">Entity Types</label>
              <div className="flex gap-1">
                <input
                  type="text"
                  value={entityTypeInput}
                  onChange={(e) => setEntityTypeInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addEntityType()}
                  placeholder="Add type..."
                  className="px-2 py-1 text-xs rounded border border-border bg-transparent text-text-primary w-24"
                />
                <button onClick={addEntityType} className="px-2 py-1 text-xs rounded bg-brand-primary text-white">+</button>
              </div>
              <div className="flex flex-wrap gap-1 mt-1">
                {filters.entity_types.map((t) => (
                  <span key={t} className="text-[10px] px-1.5 py-0.5 rounded bg-border/50 text-text-primary flex items-center gap-1">
                    {t}
                    <button onClick={() => removeEntityType(t)} className="text-text-secondary hover:text-text-primary">&times;</button>
                  </span>
                ))}
              </div>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] uppercase tracking-wide text-text-secondary font-medium">From</label>
              <input
                type="date"
                value={filters.date_from}
                onChange={(e) => setFilters((prev) => ({ ...prev, date_from: e.target.value }))}
                className="px-2 py-1 text-xs rounded border border-border bg-transparent text-text-primary"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] uppercase tracking-wide text-text-secondary font-medium">To</label>
              <input
                type="date"
                value={filters.date_to}
                onChange={(e) => setFilters((prev) => ({ ...prev, date_to: e.target.value }))}
                className="px-2 py-1 text-xs rounded border border-border bg-transparent text-text-primary"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] uppercase tracking-wide text-text-secondary font-medium">Min Confidence</label>
              <input
                type="number"
                min="0"
                max="1"
                step="0.05"
                value={filters.confidence_min}
                onChange={(e) => setFilters((prev) => ({ ...prev, confidence_min: e.target.value }))}
                placeholder="0.0"
                className="px-2 py-1 text-xs rounded border border-border bg-transparent text-text-primary w-16"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] uppercase tracking-wide text-text-secondary font-medium">Max Confidence</label>
              <input
                type="number"
                min="0"
                max="1"
                step="0.05"
                value={filters.confidence_max}
                onChange={(e) => setFilters((prev) => ({ ...prev, confidence_max: e.target.value }))}
                placeholder="1.0"
                className="px-2 py-1 text-xs rounded border border-border bg-transparent text-text-primary w-16"
              />
            </div>
            <button
              onClick={handleQuery}
              disabled={queryLoading}
              className="px-4 py-1.5 text-xs font-medium rounded-md bg-brand-primary text-white hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {queryLoading ? <Spinner size="sm" /> : "Query"}
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {widgetsLoading ? (
          <>
            <WidgetSkeleton />
            <WidgetSkeleton />
            <WidgetSkeleton />
            <WidgetSkeleton />
          </>
        ) : widgets ? (
          <>
            <WidgetCard title="Entity Coverage">
              <CoverageChart data={widgets.entity_coverage} />
            </WidgetCard>
            <WidgetCard title="Confidence Distribution">
              <ConfidenceChart buckets={widgets.confidence_distribution.buckets} />
            </WidgetCard>
            <WidgetCard title="Extraction Volume (Last 14 Days)">
              <VolumeChart data={widgets.extraction_volume.data} />
            </WidgetCard>
            <WidgetCard title="Per-Document Entity Counts">
              <DocCountChart data={widgets.document_entity_counts} />
            </WidgetCard>
          </>
        ) : null}
      </div>

      {queryEnabled && queryResult && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-text-primary">Query Results</h2>
            <div className="flex gap-2">
              <button
                onClick={() => handleExport("csv")}
                disabled={exportMutation.isPending}
                className="px-3 py-1 text-xs font-medium rounded border border-border bg-surface hover:bg-border transition-colors text-text-primary disabled:opacity-50"
              >
                {exportMutation.isPending && exportMutation.variables?.format === "csv" ? "..." : "CSV"}
              </button>
              <button
                onClick={() => handleExport("json")}
                disabled={exportMutation.isPending}
                className="px-3 py-1 text-xs font-medium rounded border border-border bg-surface hover:bg-border transition-colors text-text-primary disabled:opacity-50"
              >
                {exportMutation.isPending && exportMutation.variables?.format === "json" ? "..." : "JSON"}
              </button>
            </div>
          </div>
          <div className="rounded-lg bg-surface shadow-card border border-border p-4">
            {queryLoading ? (
              <div className="flex justify-center py-8"><Spinner /></div>
            ) : (
              <ResultsTable results={queryResult.results} />
            )}
          </div>
          {queryResult.pagination.has_more && (
            <p className="text-xs text-text-secondary text-center">
              More results available. Refine filters for narrower results.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
