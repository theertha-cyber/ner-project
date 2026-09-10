"use client";

import { useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { RequireAuth } from "@/components/require-auth";
import { Pagination, SourceFilters, SourceTable, type FilterState } from "@/components/data-sources/collection";
import { ProviderConfigForm, type ConfigPayload } from "@/components/data-sources/lifecycle";
import { SafeOutcomeNotice } from "@/components/data-sources/status";
import { useDataSourceCollection, useDataSourceMutation } from "@/hooks/use-data-sources";
import {
  LIST_ORDERS,
  LIST_SORTS,
  PROVIDER_LABELS,
  STATUSES,
  type ConnectionProvider,
  type ConnectionStatus,
  type ListOrder,
  type ListSort,
} from "@/lib/data-sources";

function isProvider(v: string | null): v is ConnectionProvider {
  return v === "azure_blob" || v === "azure_postgresql";
}

function isStatus(v: string | null): v is ConnectionStatus {
  return (STATUSES as readonly string[]).includes(v ?? "");
}

function isSort(v: string | null): v is ListSort {
  return (LIST_SORTS as readonly string[]).includes(v ?? "");
}

function isOrder(v: string | null): v is ListOrder {
  return (LIST_ORDERS as readonly string[]).includes(v ?? "");
}

export default function DataSourcesPage() {
  return (
    <RequireAuth roles={["tenant_admin"]}>
      <DataSourcesContent />
    </RequireAuth>
  );
}

function DataSourcesContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [creating, setCreating] = useState(false);
  const [createProvider, setCreateProvider] = useState<ConnectionProvider>("azure_blob");

  const providerParam = searchParams.get("provider");
  const statusParam = searchParams.get("status");
  const sortParam = searchParams.get("sort");
  const orderParam = searchParams.get("order");
  const filters: FilterState = {
    q: searchParams.get("q") ?? "",
    provider: isProvider(providerParam) ? providerParam : "all",
    status: isStatus(statusParam) ? statusParam : "all",
  };
  const sort: ListSort = isSort(sortParam) ? sortParam : "last_activity";
  const order: ListOrder = isOrder(orderParam) ? orderParam : "desc";
  const page = Math.max(1, Number(searchParams.get("page") ?? "1") || 1);

  const { data, isLoading, isError, error, refetch } = useDataSourceCollection({
    q: filters.q || undefined,
    provider: filters.provider,
    status: filters.status,
    sort,
    order,
    page,
  });
  const createMutation = useDataSourceMutation();

  function pushState(next: { q?: string; provider?: string; status?: string; sort?: string; order?: string; page?: number }, resetPage: boolean) {
    const params = new URLSearchParams(searchParams.toString());
    for (const [k, v] of Object.entries(next)) {
      if (v === undefined || v === "" || v === "all") params.delete(k);
      else params.set(k, String(v));
    }
    if (resetPage) params.delete("page");
    else if (next.page !== undefined) params.set("page", String(next.page));
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname);
  }

  function handleCreate(payload: ConfigPayload) {
    createMutation.mutate(
      { action: "create", body: { provider: payload.provider, configuration: payload.configuration, secret_references: payload.secret_references } },
      { onSuccess: (result) => router.push(`/settings/data-sources/${result.connection.id}`) },
    );
  }

  const items = data?.items ?? [];
  const hasActiveFilters = filters.q !== "" || filters.provider !== "all" || filters.status !== "all";
  const showEmpty = !isLoading && !isError && items.length === 0;

  return (
    <div className="animate-fade-up mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 py-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-[-0.01em]" style={{ color: "var(--ink)" }}>
          Data Sources
        </h1>
        <p className="mt-1 max-w-[65ch] text-sm leading-6" style={{ color: "var(--ink-2)" }}>
          Manage the two approved Azure connections for your tenant. Only safe configuration names and outcome
          classes appear here — never secrets, connection strings, or provider details.
        </p>
      </div>

      <div className="flex flex-wrap items-end justify-between gap-3">
        <SourceFilters
          filters={filters}
          disabled={isLoading}
          onChange={(next) => pushState({ q: next.q || undefined, provider: next.provider, status: next.status }, true)}
        />
        <button
          type="button"
          onClick={() => setCreating((v) => !v)}
          aria-expanded={creating}
          className="rounded-md px-4 py-2 text-sm font-semibold outline-none focus-visible:ring-2"
          style={{ background: "var(--primary)", color: "#fff" }}
        >
          {creating ? "Close creation" : "New connection"}
        </button>
      </div>

      {creating && (
        <section aria-label="Create connection" className="rounded-md border p-4 shadow-card" style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}>
          <div className="mb-3 flex flex-col gap-1">
            <label htmlFor="create-provider" className="text-sm font-medium tracking-[0.02em]" style={{ color: "var(--ink)" }}>
              Provider
            </label>
            <select
              id="create-provider"
              value={createProvider}
              onChange={(e) => setCreateProvider(e.target.value as ConnectionProvider)}
              className="max-w-xs rounded-md border px-3 py-1.5 text-sm outline-none focus-visible:ring-2"
              style={{ borderColor: "var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}
            >
              <option value="azure_blob">{PROVIDER_LABELS.azure_blob}</option>
              <option value="azure_postgresql">{PROVIDER_LABELS.azure_postgresql}</option>
            </select>
          </div>
          <ProviderConfigForm
            provider={createProvider}
            submitting={createMutation.isPending}
            serverError={createMutation.error as unknown as import("@/hooks/use-data-sources").SafeApiHttpError | null}
            submitLabel="Create draft"
            onSubmit={handleCreate}
          />
        </section>
      )}

      {isError && (
        <SafeOutcomeNotice variant="error" title="Connections unavailable" code={(error as { code?: string })?.code ?? "INTERNAL_ERROR"} requestId={(error as { requestId?: string })?.requestId}>
          <button type="button" onClick={() => refetch()} className="mt-2 rounded-md border px-3 py-1.5 text-sm font-medium outline-none focus-visible:ring-2" style={{ borderColor: "var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}>
            Retry
          </button>
        </SafeOutcomeNotice>
      )}

      {showEmpty && !hasActiveFilters && (
        <div className="rounded-md border p-8 text-center shadow-card" style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}>
          <h2 className="text-lg font-semibold" style={{ color: "var(--ink)" }}>
            No data sources yet
          </h2>
          <p className="mx-auto mt-1 max-w-[65ch] text-sm leading-6" style={{ color: "var(--ink-2)" }}>
            Connect Azure Blob Storage or Azure Database for PostgreSQL to give this tenant its own document
            source. Document upload keeps working either way.
          </p>
          <button type="button" onClick={() => setCreating(true)} className="mt-4 rounded-md px-4 py-2 text-sm font-semibold outline-none focus-visible:ring-2" style={{ background: "var(--primary)", color: "#fff" }}>
            Configure the first connection
          </button>
        </div>
      )}

      {showEmpty && hasActiveFilters && (
        <div className="rounded-md border p-8 text-center shadow-card" style={{ borderColor: "var(--line)", background: "var(--surface-2)" }} role="status">
          <h2 className="text-lg font-semibold" style={{ color: "var(--ink)" }}>
            No matches{filters.q ? ` for “${filters.q}”` : ""}
          </h2>
          <p className="mt-1 text-sm" style={{ color: "var(--ink-2)" }}>
            Try a different search or clear the filters to see every connection.
          </p>
          <button type="button" onClick={() => pushState({ q: undefined, provider: "all", status: "all" }, true)} className="mt-4 rounded-md border px-4 py-2 text-sm font-semibold outline-none focus-visible:ring-2" style={{ borderColor: "var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}>
            Clear search and filters
          </button>
        </div>
      )}

      {(!showEmpty || isLoading) && (
        <>
          <SourceTable
            items={items}
            sort={sort}
            order={order}
            loading={isLoading}
            onSort={(next) => {
              if (next === sort) pushState({ order: order === "asc" ? "desc" : "asc" }, true);
              else pushState({ sort: next, order: next === "last_activity" || next === "created_at" ? "desc" : "asc" }, true);
            }}
          />
          {data && data.total > 0 && (
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} totalPages={data.total_pages} onPage={(p) => pushState({ page: p }, false)} />
          )}
        </>
      )}
    </div>
  );
}
