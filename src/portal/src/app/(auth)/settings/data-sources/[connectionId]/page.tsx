"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { RequireAuth } from "@/components/require-auth";
import { ProviderConfigForm, LifecyclePanel, SyncActivitySummary, type ConfigPayload } from "@/components/data-sources/lifecycle";
import { SafeOutcomeNotice, SafeStatusBadge } from "@/components/data-sources/status";
import { SafeApiHttpError, useDataSource, useDataSourceMutation, type LifecycleAction } from "@/hooks/use-data-sources";
import { PROVIDER_LABELS, type SafeConnection } from "@/lib/data-sources";

const UPDATABLE = ["draft", "paused", "error"];

export default function DataSourceDetailPage() {
  return (
    <RequireAuth roles={["tenant_admin"]}>
      <DetailContent />
    </RequireAuth>
  );
}

function DetailContent() {
  const params = useParams<{ connectionId: string }>();
  const router = useRouter();
  const connectionId = params.connectionId;
  const [replacing, setReplacing] = useState(false);

  const { data: connection, isLoading, isError, error, refetch } = useDataSource(connectionId);
  const mutation = useDataSourceMutation();
  const [lastResult, setLastResult] = useState<{ replayed: boolean } | null>(null);

  function runAction(action: LifecycleAction, body: unknown) {
    if (action === "replace") {
      setReplacing(true);
      setLastResult(null);
      requestAnimationFrame(() => document.getElementById("replacement-draft")?.focus({ preventScroll: false }));
      return;
    }
    setLastResult(null);
    mutation.mutate(
      { action, connectionId, body },
      { onSuccess: (result) => setLastResult({ replayed: result.replayed }) },
    );
  }

  function handleUpdate(payload: ConfigPayload) {
    mutation.mutate(
      {
        action: "update",
        connectionId,
        body: { provider: payload.provider, configuration: payload.configuration, secret_references: payload.secret_references },
      },
      { onSuccess: (result) => setLastResult({ replayed: result.replayed }) },
    );
  }

  function handleReplace(payload: ConfigPayload) {
    mutation.mutate(
      {
        action: "replace",
        connectionId,
        body: { provider: payload.provider, configuration: payload.configuration, secret_references: payload.secret_references },
      },
      {
        onSuccess: (result) => {
          setReplacing(false);
          router.push(`/settings/data-sources/${result.connection.id}`);
        },
      },
    );
  }

  return (
    <div className="animate-fade-up mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 py-8">
      <Link href="/settings/data-sources" className="w-fit rounded-sm text-sm font-medium underline outline-none focus-visible:ring-2" style={{ color: "var(--primary)" }}>
        Back to data sources
      </Link>

      {isLoading && (
        <div role="status" aria-label="Loading connection" className="flex flex-col gap-3">
          {[0, 1, 2].map((i) => (
            <span key={i} className="block h-6 w-2/3 animate-pulse rounded-sm" style={{ background: "var(--line-2)" }} />
          ))}
        </div>
      )}

      {isError && (
        <SafeOutcomeNotice
          variant="error"
          title="Connection unavailable"
          code={(error as SafeApiHttpError)?.code ?? "INTERNAL_ERROR"}
          requestId={(error as SafeApiHttpError)?.requestId}
        >
          <button type="button" onClick={() => refetch()} className="mt-2 rounded-md border px-3 py-1.5 text-sm font-medium outline-none focus-visible:ring-2" style={{ borderColor: "var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}>
            Retry
          </button>
        </SafeOutcomeNotice>
      )}

      {connection && (
        <>
          <DetailHeader connection={connection} />
          <SafeFacts connection={connection} />
          {connection.provider === "azure_postgresql" && (
            <Link href={`/settings/data-sources/${connection.id}/schema-contracts`} className="w-fit rounded-md border px-4 py-2 text-sm font-semibold outline-none focus-visible:ring-2" style={{ borderColor: "var(--primary)", background: "var(--surface-2)", color: "var(--primary-2)" }}>
              Manage schema contracts
            </Link>
          )}
          {UPDATABLE.includes(connection.status) && !replacing && (
            <section aria-label="Connection configuration" className="rounded-md border p-4 shadow-card" style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}>
              <h2 className="mb-3 text-base font-semibold" style={{ color: "var(--ink)" }}>
                Connection configuration
              </h2>
              <ProviderConfigForm
                provider={connection.provider}
                submitting={mutation.isPending}
                serverError={(mutation.error as SafeApiHttpError | null) ?? null}
                submitLabel="Save draft"
                onSubmit={handleUpdate}
              />
            </section>
          )}
          {replacing && (
            <section id="replacement-draft" aria-label="Replacement draft" className="rounded-md border p-4 shadow-card" style={{ borderColor: "var(--primary-line)", background: "var(--surface-2)" }} tabIndex={-1}>
              <h2 className="mb-1 text-base font-semibold" style={{ color: "var(--ink)" }}>
                Replacement draft
              </h2>
              <p className="mb-3 text-sm" style={{ color: "var(--ink-2)" }}>
                The replacement links to this connection. Values stay write-only.
              </p>
              <ProviderConfigForm
                provider={connection.provider}
                submitting={mutation.isPending}
                serverError={(mutation.error as SafeApiHttpError | null) ?? null}
                submitLabel="Create replacement"
                onSubmit={handleReplace}
              />
              <button type="button" onClick={() => setReplacing(false)} className="mt-2 rounded-sm text-sm underline outline-none focus-visible:ring-2" style={{ color: "var(--ink-2)" }}>
                Cancel replacement
              </button>
            </section>
          )}
          <SyncActivitySummary connection={connection} />
          <LifecyclePanel
            connection={connection}
            pendingAction={mutation.isPending ? (mutation.variables?.action ?? null) : null}
            actionError={(mutation.error as SafeApiHttpError | null) ?? null}
            actionResult={lastResult}
            onAction={runAction}
          />
        </>
      )}
    </div>
  );
}

function DetailHeader({ connection }: { connection: SafeConnection }) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <h1 className="text-2xl font-semibold tracking-[-0.01em]" style={{ color: "var(--ink)" }}>
        {PROVIDER_LABELS[connection.provider]}
      </h1>
      <SafeStatusBadge status={connection.status} />
    </div>
  );
}

function SafeFacts({ connection }: { connection: SafeConnection }) {
  const rows: [string, string][] = [
    ["Configured fields", connection.configured_fields.length > 0 ? connection.configured_fields.join(", ") : "None yet"],
    ["Secret references", connection.secret_reference_fields.length > 0 ? connection.secret_reference_fields.join(", ") : "None yet"],
    ["Test", `${connection.last_test.outcome.replace("_", " ")} · ${connection.last_test.reason_code}`],
  ];
  if (connection.replaces_connection_id) rows.push(["Replaces", connection.replaces_connection_id]);
  if (connection.replaced_by_connection_id) rows.push(["Replaced by", connection.replaced_by_connection_id]);
  return (
    <section aria-label="Connection facts" className="rounded-md border p-4" style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}>
      <dl className="grid gap-2 text-sm sm:grid-cols-2">
        {rows.map(([term, value]) => (
          <div key={term} className="flex gap-2">
            <dt className="shrink-0 font-medium" style={{ color: "var(--ink-2)" }}>{term}:</dt>
            <dd style={{ color: "var(--ink)" }}>{value}</dd>
          </div>
        ))}
        <div className="flex gap-2">
          <dt className="shrink-0 font-medium" style={{ color: "var(--ink-2)" }}>Updated:</dt>
          <dd style={{ color: "var(--ink)" }}><time dateTime={connection.updated_at}>{new Date(connection.updated_at).toLocaleString()}</time></dd>
        </div>
      </dl>
    </section>
  );
}
