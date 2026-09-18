"use client";

import Link from "next/link";
import { FilterSelect } from "@/components/ui/filter-select";
import {
  PROVIDER_LABELS,
  STATUS_LABELS,
  type ConnectionProvider,
  type ConnectionStatus,
  type ListOrder,
  type ListSort,
  type SafeConnection,
} from "@/lib/data-sources";
import { SafeStatusBadge } from "./status";

/* CMP-4 — Source Filters */

export interface FilterState {
  q: string;
  provider: ConnectionProvider | "all";
  status: ConnectionStatus | "all";
}

export function SourceFilters({
  filters,
  onChange,
  disabled,
}: {
  filters: FilterState;
  onChange: (next: FilterState) => void;
  disabled?: boolean;
}) {
  const hasActive = filters.q !== "" || filters.provider !== "all" || filters.status !== "all";
  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="flex flex-col gap-1">
        <label htmlFor="ds-search" className="text-xs font-medium tracking-[0.02em]" style={{ color: "var(--ink-2)" }}>
          Search connections
        </label>
        <input
          id="ds-search"
          type="search"
          value={filters.q}
          maxLength={100}
          disabled={disabled}
          placeholder="Search by provider or status"
          onChange={(e) => onChange({ ...filters, q: e.target.value })}
          className="rounded-md border px-3 py-1.5 text-sm outline-none focus-visible:ring-2"
          style={{ borderColor: "var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}
        />
      </div>
      <div className="flex flex-col gap-1">
        <span id="ds-provider-label" className="text-xs font-medium tracking-[0.02em]" style={{ color: "var(--ink-2)" }}>
          Provider
        </span>
        <FilterSelect<ConnectionProvider | "all">
          value={filters.provider}
          ariaLabel="Filter by provider"
          options={[
            { value: "all", label: "All providers" },
            { value: "azure_blob", label: PROVIDER_LABELS.azure_blob },
            { value: "azure_postgresql", label: PROVIDER_LABELS.azure_postgresql },
          ]}
          onChange={(provider) => onChange({ ...filters, provider })}
        />
      </div>
      <div className="flex flex-col gap-1">
        <span id="ds-status-label" className="text-xs font-medium tracking-[0.02em]" style={{ color: "var(--ink-2)" }}>
          Status
        </span>
        <FilterSelect<ConnectionStatus | "all">
          value={filters.status}
          ariaLabel="Filter by status"
          options={[
            { value: "all", label: "All statuses" },
            ...(Object.keys(STATUS_LABELS) as ConnectionStatus[]).map((s) => ({ value: s as ConnectionStatus | "all", label: STATUS_LABELS[s] })),
          ]}
          onChange={(status) => onChange({ ...filters, status })}
        />
      </div>
      {hasActive && (
        <button
          type="button"
          onClick={() => onChange({ q: "", provider: "all", status: "all" })}
          disabled={disabled}
          className="rounded-md border px-3 py-1.5 text-sm font-medium outline-none focus-visible:ring-2"
          style={{ borderColor: "var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}
        >
          Clear filters
        </button>
      )}
    </div>
  );
}

/* CMP-2 — Source Table */

const SORT_COLUMNS: { key: ListSort; label: string }[] = [
  { key: "provider", label: "Provider" },
  { key: "status", label: "Status" },
  { key: "last_activity", label: "Last activity" },
  { key: "created_at", label: "Created" },
];

export function SourceTable({
  items,
  sort,
  order,
  onSort,
  loading,
}: {
  items: SafeConnection[];
  sort: ListSort;
  order: ListOrder;
  onSort: (sort: ListSort) => void;
  loading: boolean;
}) {
  return (
    <div className="overflow-x-auto rounded-md border shadow-card" style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}>
      <table className="w-full border-collapse text-left text-sm" aria-busy={loading}>
        <caption className="sr-only">Tenant data-source connections</caption>
        <thead>
          <tr style={{ background: "var(--surface-3)" }}>
            {SORT_COLUMNS.map((col) => {
              const active = sort === col.key;
              return (
                <th key={col.key} scope="col" aria-sort={active ? (order === "asc" ? "ascending" : "descending") : "none"} className="px-4 py-3 text-xs font-semibold tracking-[0.06em] uppercase" style={{ color: "var(--ink-2)" }}>
                  <button
                    type="button"
                    onClick={() => onSort(col.key)}
                    aria-label={`Sort by ${col.label}${active ? `, currently ${order === "asc" ? "ascending" : "descending"}` : ""}`}
                    className="rounded-sm outline-none focus-visible:ring-2"
                  >
                    {col.label}
                    {active && <span aria-hidden="true">{order === "asc" ? " ▲" : " ▼"}</span>}
                  </button>
                </th>
              );
            })}
            <th scope="col" className="px-4 py-3 text-xs font-semibold tracking-[0.06em] uppercase" style={{ color: "var(--ink-2)" }}>
              Actions
            </th>
          </tr>
        </thead>
        <tbody>
          {loading &&
            Array.from({ length: 3 }).map((_, i) => (
              <tr key={`skeleton-${i}`} className="border-t" style={{ borderColor: "var(--line-2)" }}>
                <td colSpan={5} className="px-4 py-4" role="status" aria-label="Loading connections">
                  <span className="block h-4 w-2/3 animate-pulse rounded-sm" style={{ background: "var(--line-2)" }} />
                </td>
              </tr>
            ))}
          {!loading &&
            items.map((item) => (
              <tr key={item.id} className="border-t" style={{ borderColor: "var(--line-2)" }}>
                <td className="px-4 py-3 font-medium" style={{ color: "var(--ink)" }}>
                  {PROVIDER_LABELS[item.provider]}
                </td>
                <td className="px-4 py-3">
                  <SafeStatusBadge status={item.status} />
                </td>
                <td className="px-4 py-3" style={{ color: "var(--ink-2)" }}>
                  <time dateTime={item.updated_at}>{new Date(item.updated_at).toLocaleString()}</time>
                </td>
                <td className="px-4 py-3" style={{ color: "var(--ink-2)" }}>
                  <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleDateString()}</time>
                </td>
                <td className="px-4 py-3">
                  <Link
                    href={`/settings/data-sources/${item.id}`}
                    className="rounded-sm font-medium underline outline-none focus-visible:ring-2"
                    style={{ color: "var(--primary)" }}
                    aria-label={`Manage ${PROVIDER_LABELS[item.provider]} connection`}
                  >
                    Manage
                  </Link>
                </td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}

/* CMP-5 — Pagination */

export function Pagination({
  page,
  pageSize,
  total,
  totalPages,
  onPage,
}: {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
  onPage: (page: number) => void;
}) {
  if (total === 0) return null;
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  const window = 2;
  const pages: number[] = [];
  for (let p = Math.max(1, page - window); p <= Math.min(totalPages, page + window); p++) pages.push(p);
  const go = (p: number) => () => onPage(Math.min(Math.max(1, p), Math.max(1, totalPages)));
  const btn = (label: string, target: number, extra?: { current?: boolean; disabled?: boolean; ariaLabel?: string }) => (
    <button
      key={`${label}-${target}`}
      type="button"
      onClick={go(target)}
      disabled={extra?.disabled}
      aria-label={extra?.ariaLabel ?? `Go to page ${target}`}
      aria-current={extra?.current ? "page" : undefined}
      className="min-h-[24px] min-w-[24px] rounded-sm border px-2 py-1 text-sm font-medium outline-none focus-visible:ring-2 disabled:opacity-50"
      style={{
        borderColor: "var(--line)",
        background: extra?.current ? "var(--primary-soft)" : "var(--surface-2)",
        color: extra?.current ? "var(--primary-2)" : "var(--ink)",
      }}
    >
      {label}
    </button>
  );
  return (
    <nav aria-label="Connection pages" className="flex flex-wrap items-center gap-2">
      <p className="mr-2 text-sm" style={{ color: "var(--ink-2)" }} role="status">
        Showing {start}–{end} of {total}
      </p>
      {btn("First", 1, { disabled: page <= 1, ariaLabel: "Go to first page" })}
      {btn("Previous", page - 1, { disabled: page <= 1, ariaLabel: "Go to previous page" })}
      {pages.map((p) => btn(String(p), p, { current: p === page }))}
      {btn("Next", page + 1, { disabled: page >= totalPages, ariaLabel: "Go to next page" })}
      {btn("Last", totalPages, { disabled: page >= totalPages, ariaLabel: "Go to last page" })}
    </nav>
  );
}
