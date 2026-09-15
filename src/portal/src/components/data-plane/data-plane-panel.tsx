"use client";

import { useState } from "react";
import { useDataPlaneStatus, useRetryDataPlaneProvisioning } from "@/hooks/use-data-plane";
import { newIdempotencyKey, type DataPlaneStatus } from "@/lib/data-sources";
import type { SafeApiHttpError } from "@/hooks/use-data-sources";
import { Spinner } from "@/components/ui/spinner";

/* ADR-017, task 13.2 — replaces the Sync activity panel on a data-plane
 * connection's detail page: status, provisioning outcome, revision, health,
 * and a Retry provisioning action. Residency test checks (server version,
 * vector extension, privilege, target-schema identity — the 5 checks
 * `DataPlaneSecureTester` runs) are rendered as labelled outcomes via the
 * connection's own `last_test` field, already shown elsewhere on this page —
 * this panel is the data-plane *lifecycle* state, not the connection test. */

const STATUS_LABELS: Record<DataPlaneStatus, string> = {
  awaiting_store: "Awaiting store",
  provisioning: "Provisioning",
  provisioning_failed: "Provisioning failed",
  ready: "Ready",
  migration_required: "Migration required",
  paused: "Paused",
  store_retired: "Store retired",
};

const STATUS_TONE: Record<DataPlaneStatus, string> = {
  awaiting_store: "var(--ink-2)",
  provisioning: "var(--warn, #b45309)",
  provisioning_failed: "var(--bad)",
  ready: "var(--good, #15803d)",
  migration_required: "var(--warn, #b45309)",
  paused: "var(--ink-2)",
  store_retired: "var(--ink-2)",
};

export function DataPlanePanel() {
  const { data, isLoading, isError, error, refetch } = useDataPlaneStatus({ pollIntervalMs: 5000 });
  const retry = useRetryDataPlaneProvisioning();
  const [retryError, setRetryError] = useState<SafeApiHttpError | null>(null);

  function handleRetry() {
    setRetryError(null);
    retry.mutate(newIdempotencyKey(), {
      onError: (err) => setRetryError(err as SafeApiHttpError),
    });
  }

  return (
    <section
      aria-label="Data plane"
      className="rounded-md border p-4"
      style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}
    >
      <h2 className="text-base font-semibold" style={{ color: "var(--ink)" }}>
        Data plane
      </h2>
      <p className="mt-1 text-sm" style={{ color: "var(--ink-2)" }}>
        This connection is your tenant&apos;s own PostgreSQL store — every document, span, chunk, and
        conversation lives here, not a copy of it.
      </p>

      {isLoading && (
        <div className="mt-3 flex items-center gap-2">
          <Spinner size="sm" />
          <span className="text-sm" style={{ color: "var(--ink-2)" }}>
            Loading status…
          </span>
        </div>
      )}

      {isError && (
        <div className="mt-3 text-sm" style={{ color: "var(--bad)" }}>
          Couldn&apos;t load data-plane status ({(error as SafeApiHttpError)?.code ?? "INTERNAL_ERROR"}).{" "}
          <button type="button" onClick={() => refetch()} className="underline">
            Retry
          </button>
        </div>
      )}

      {data && (
        <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <dt style={{ color: "var(--ink-2)" }}>Status</dt>
          <dd className="font-medium" style={{ color: STATUS_TONE[data.status] }}>
            {STATUS_LABELS[data.status]}
          </dd>

          <dt style={{ color: "var(--ink-2)" }}>Outcome</dt>
          <dd style={{ color: "var(--ink)" }}>{data.status_reason}</dd>

          <dt style={{ color: "var(--ink-2)" }}>Schema revision</dt>
          <dd style={{ color: "var(--ink)" }}>{data.schema_revision ?? "—"}</dd>
        </dl>
      )}

      {data?.status === "provisioning_failed" && (
        <div className="mt-4">
          <button
            type="button"
            onClick={handleRetry}
            disabled={retry.isPending}
            className="rounded-md px-3 py-1.5 text-sm font-semibold outline-none focus-visible:ring-2 disabled:opacity-60"
            style={{ background: "var(--primary)", color: "#fff" }}
          >
            {retry.isPending ? "Retrying…" : "Retry provisioning"}
          </button>
          {retryError && (
            <p className="mt-2 text-xs" style={{ color: "var(--bad)" }} role="alert">
              Retry failed ({retryError.code}).
            </p>
          )}
        </div>
      )}

      {data?.status === "store_retired" && (
        <p className="mt-3 text-xs" style={{ color: "var(--ink-2)" }}>
          Retirement leaves the underlying store untouched — this only stops the platform from using it.
        </p>
      )}
    </section>
  );
}
