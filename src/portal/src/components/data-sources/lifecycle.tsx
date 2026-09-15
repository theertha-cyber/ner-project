"use client";

import { useEffect, useState } from "react";
import { SlideOver } from "@/components/ui/slide-over";
import {
  PROVIDER_LABELS,
  REQUIRED_ACTIVATION_EVIDENCE,
  buildBlobPayload,
  buildPostgresPayload,
  type ConnectionProvider,
  type SafeConnection,
} from "@/lib/data-sources";
import { SafeApiHttpError, useManualSyncMutation, type LifecycleAction } from "@/hooks/use-data-sources";
import { SafeOutcomeNotice } from "./status";
import { DataPlanePanel } from "@/components/data-plane/data-plane-panel";

/* CMP-6 — Provider Configuration Form (closed schema, write-only values) */

export interface ConfigPayload {
  provider: ConnectionProvider;
  configuration: Record<string, string | number>;
  secret_references: Record<string, string>;
}

function Field({
  id,
  label,
  hint,
  error,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium tracking-[0.02em]" style={{ color: "var(--ink)" }}>
        {label}
      </label>
      {children}
      {hint && !error && (
        <span id={`${id}-hint`} className="text-xs" style={{ color: "var(--ink-2)" }}>
          {hint}
        </span>
      )}
      {error && (
        <span id={`${id}-error`} role="alert" className="text-xs font-medium" style={{ color: "var(--bad)" }}>
          {error}
        </span>
      )}
    </div>
  );
}

function TextInput({
  id,
  value,
  error,
  hint,
  onChange,
  onBlur,
  inputMode,
  autoComplete,
}: {
  id: string;
  value: string;
  error?: string;
  hint?: string;
  onChange: (v: string) => void;
  onBlur: () => void;
  inputMode?: "text" | "numeric";
  autoComplete?: string;
}) {
  return (
    <input
      id={id}
      type="text"
      value={value}
      inputMode={inputMode}
      autoComplete={autoComplete}
      aria-invalid={Boolean(error)}
      aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
      onChange={(e) => onChange(e.target.value)}
      onBlur={onBlur}
      className="rounded-md border px-3 py-1.5 text-sm outline-none focus-visible:ring-2"
      style={{ borderColor: error ? "var(--bad)" : "var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}
    />
  );
}

export function ProviderConfigForm({
  provider,
  submitting,
  serverError,
  submitLabel,
  onSubmit,
}: {
  provider: ConnectionProvider;
  submitting: boolean;
  serverError: SafeApiHttpError | null;
  submitLabel: string;
  onSubmit: (payload: ConfigPayload) => void;
}) {
  const isBlob = provider === "azure_blob";
  const [values, setValues] = useState({ account: "", container: "", prefix: "", connection_string_ref: "", host: "", database: "", username: "", port: "", password_ref: "" });
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [summaryError, setSummaryError] = useState<string | null>(null);

  const set = (k: keyof typeof values) => (v: string) => setValues((prev) => ({ ...prev, [k]: v }));
  const touch = (k: string) => () => setTouched((prev) => ({ ...prev, [k]: true }));

  function fieldError(key: keyof typeof values, label: string): string | undefined {
    if (!touched[key]) return undefined;
    if (!values[key].trim()) return `${label} is required.`;
    if (key === "port" && !/^\d{1,5}$/.test(values[key].trim())) return "Port must be a number from 1 to 65535.";
    return undefined;
  }

  const errors: Record<string, string | undefined> = isBlob
    ? {
        account: fieldError("account", "Storage account"),
        container: fieldError("container", "Container"),
        connection_string_ref: fieldError("connection_string_ref", "Connection string reference"),
      }
    : {
        host: fieldError("host", "Host"),
        database: fieldError("database", "Database"),
        username: fieldError("username", "Username"),
        port: fieldError("port", "Port"),
        password_ref: fieldError("password_ref", "Password reference"),
      };
  const visibleErrors = Object.entries(errors).filter(([, e]) => e);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const all = Object.keys(errors);
    setTouched(Object.fromEntries(all.map((k) => [k, true])));
    const missing = all.filter((k) => {
      if (!values[k as keyof typeof values].trim()) return true;
      if (k === "port" && !/^\d{1,5}$/.test(values.port.trim())) return true;
      return false;
    });
    if (missing.length > 0) {
      setSummaryError(`${missing.length} field${missing.length > 1 ? "s need" : " needs"} attention before saving.`);
      document.getElementById("config-error-summary")?.focus();
      return;
    }
    setSummaryError(null);
    onSubmit(
      isBlob
        ? { provider, ...buildBlobPayload({ account: values.account, container: values.container, prefix: values.prefix, connection_string_ref: values.connection_string_ref }) }
        : { provider, ...buildPostgresPayload({ host: values.host, database: values.database, username: values.username, port: values.port, password_ref: values.password_ref }) },
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate={false} aria-label={`${PROVIDER_LABELS[provider]} configuration`}>
      {summaryError && (
        <div id="config-error-summary" tabIndex={-1} role="status" className="mb-4 rounded-md border p-3 text-sm" style={{ borderColor: "var(--bad)", background: "var(--bad-soft)", color: "var(--ink)" }}>
          {summaryError}
        </div>
      )}
      {serverError && (
        <div className="mb-4">
          <SafeOutcomeNotice variant="error" title="Save failed" code={serverError.code} requestId={serverError.requestId}>
            Your entries were kept. Correct the highlighted fields and try again.
          </SafeOutcomeNotice>
        </div>
      )}
      <div className="grid gap-4">
        {isBlob ? (
          <>
            <Field id="cfg-account" label="Storage account" error={errors.account}>
              <TextInput id="cfg-account" value={values.account} error={errors.account} onChange={set("account")} onBlur={touch("account")} autoComplete="off" />
            </Field>
            <Field id="cfg-container" label="Container" error={errors.container}>
              <TextInput id="cfg-container" value={values.container} error={errors.container} onChange={set("container")} onBlur={touch("container")} autoComplete="off" />
            </Field>
            <Field id="cfg-prefix" label="Prefix (optional)" hint="Limit sync to one blob prefix. Leave empty for the whole container.">
              <TextInput id="cfg-prefix" value={values.prefix} onChange={set("prefix")} onBlur={touch("prefix")} autoComplete="off" />
            </Field>
            <Field id="cfg-conn-ref" label="Connection string reference" hint="Names a stored secret. Values are write-only and never shown again." error={errors.connection_string_ref}>
              <TextInput id="cfg-conn-ref" value={values.connection_string_ref} error={errors.connection_string_ref} hint="Names a stored secret." onChange={set("connection_string_ref")} onBlur={touch("connection_string_ref")} autoComplete="off" />
            </Field>
          </>
        ) : (
          <>
            <Field id="cfg-host" label="Host" error={errors.host}>
              <TextInput id="cfg-host" value={values.host} error={errors.host} onChange={set("host")} onBlur={touch("host")} autoComplete="off" />
            </Field>
            <Field id="cfg-database" label="Database" error={errors.database}>
              <TextInput id="cfg-database" value={values.database} error={errors.database} onChange={set("database")} onBlur={touch("database")} autoComplete="off" />
            </Field>
            <Field id="cfg-username" label="Username" error={errors.username}>
              <TextInput id="cfg-username" value={values.username} error={errors.username} onChange={set("username")} onBlur={touch("username")} autoComplete="username" />
            </Field>
            <Field id="cfg-port" label="Port" error={errors.port}>
              <TextInput id="cfg-port" value={values.port} error={errors.port} onChange={set("port")} onBlur={touch("port")} inputMode="numeric" autoComplete="off" />
            </Field>
            <Field id="cfg-pass-ref" label="Password reference" hint="Names a stored secret. TLS verified with sslmode verify-full. Values are write-only." error={errors.password_ref}>
              <TextInput id="cfg-pass-ref" value={values.password_ref} error={errors.password_ref} hint="Names a stored secret." onChange={set("password_ref")} onBlur={touch("password_ref")} autoComplete="off" />
            </Field>
          </>
        )}
      </div>
      <button
        type="submit"
        disabled={submitting}
        className="mt-4 rounded-md px-4 py-2 text-sm font-semibold outline-none focus-visible:ring-2 disabled:opacity-60"
        style={{ background: "var(--primary)", color: "#fff" }}
      >
        {submitting ? "Saving…" : submitLabel}
      </button>
      {visibleErrors.length > 0 && (
        <p className="mt-2 text-xs" style={{ color: "var(--ink-2)" }} role="status">
          {visibleErrors.length} field{visibleErrors.length > 1 ? "s" : ""} need{visibleErrors.length > 1 ? "" : "s"} attention.
        </p>
      )}
    </form>
  );
}

/* CMP-7 — Connection Lifecycle Panel */

const EVIDENCE_LABELS: Record<string, string> = {
  network_approved: "Private connectivity or approved public-egress path has been reviewed and approved.",
  governance_approved: "Data-residency and retention has been reviewed and approved.",
};

export function LifecyclePanel({
  connection,
  pendingAction,
  actionError,
  actionResult,
  onAction,
}: {
  connection: SafeConnection;
  pendingAction: LifecycleAction | null;
  actionError: SafeApiHttpError | null;
  actionResult: { replayed: boolean } | null;
  onAction: (action: LifecycleAction, body: unknown) => void;
}) {
  const [evidence, setEvidence] = useState<string[]>([]);
  const [confirming, setConfirming] = useState<null | "pause" | "replace" | "retire">(null);
  const busy = pendingAction !== null;

  const testPassed = connection.last_test.outcome === "passed";
  const evidenceComplete = REQUIRED_ACTIVATION_EVIDENCE.every((e) => evidence.includes(e));
  const canActivate = testPassed && evidenceComplete && !busy;
  const canTest = ["draft", "paused", "error"].includes(connection.status) && !busy;
  const isActive = connection.status === "active";
  const isRetired = connection.status === "retired";
  const testing = pendingAction === "test";
  const testFailed = connection.last_test.outcome === "failed";
  const showAttestation = (testPassed || isActive) && !testFailed;

  useEffect(() => {
    if (testFailed) setEvidence([]);
  }, [testFailed]);

  function toggleEvidence(name: string) {
    setEvidence((prev) => (prev.includes(name) ? prev.filter((e) => e !== name) : [...prev, name]));
  }

  function confirmBody(action: "pause" | "replace" | "retire"): unknown {
    if (action === "retire") return { confirm: true };
    return {};
  }

  return (
    <section aria-label="Connection lifecycle" className="flex flex-col gap-4">
      <div className="rounded-md border p-4" style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}>
        <h2 className="text-base font-semibold" style={{ color: "var(--ink)" }}>
          Lifecycle
        </h2>
        <p className="mt-1 text-sm" style={{ color: "var(--ink-2)" }}>
          Last test: {connection.last_test.outcome.replace("_", " ")} · {connection.last_test.reason_code}
        </p>

        {!isActive && (
          <button
            type="button"
            disabled={!canTest}
            onClick={() => onAction("test", {})}
            className="mt-3 rounded-md border px-4 py-2 text-sm font-semibold outline-none focus-visible:ring-2 disabled:opacity-50"
            style={{ borderColor: "var(--primary)", background: "var(--surface-2)", color: "var(--primary-2)" }}
          >
            {testing ? "Testing…" : testFailed ? "Retry test" : "Test connection"}
          </button>
        )}

        {!showAttestation && !isActive && !testPassed && !testing && (
          <div className="mt-3">
            <SafeOutcomeNotice variant="blocked" title="Activation unavailable" code="TEST_REQUIRED">
              Run a successful secure test first. No secrets or provider details are shown here.
            </SafeOutcomeNotice>
          </div>
        )}

        {showAttestation && (
          <>
            <fieldset className="mt-3 flex flex-col gap-2">
              <legend className="text-sm font-medium" style={{ color: "var(--ink)" }}>
                Required attestations
              </legend>
              {REQUIRED_ACTIVATION_EVIDENCE.map((name) => (
                <div key={name} className="flex flex-col gap-0.5">
                  <label className="flex items-center gap-2 text-sm" style={{ color: "var(--ink)" }}>
                    <input
                      type="checkbox"
                      checked={isActive || evidence.includes(name)}
                      disabled={isActive}
                      onChange={() => toggleEvidence(name)}
                      aria-describedby={`${name}-hint`}
                      className="size-4 accent-[var(--primary)]"
                    />
                    {name}
                  </label>
                  <span id={`${name}-hint`} className="ml-6 text-xs" style={{ color: "var(--ink-2)" }}>
                    {EVIDENCE_LABELS[name]}
                  </span>
                </div>
              ))}
            </fieldset>
            <button
              type="button"
              disabled={isActive || !canActivate}
              onClick={() => onAction("activate", { activation_evidence: [...REQUIRED_ACTIVATION_EVIDENCE].sort() })}
              aria-describedby={!canActivate && !isActive ? "activate-hint" : undefined}
              className="mt-3 rounded-md px-4 py-2 text-sm font-semibold outline-none focus-visible:ring-2 disabled:opacity-50"
              style={{ background: "var(--primary)", color: "#fff" }}
            >
              {isActive ? "Activated" : pendingAction === "activate" ? "Activating…" : "Activate"}
            </button>
            {!canActivate && !isActive && (
              <p id="activate-hint" className="mt-1 text-xs" style={{ color: "var(--ink-2)" }}>
                Available after a passed secure test and both attestations.
              </p>
            )}
          </>
        )}
      </div>

      <div className="rounded-md border p-4" style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}>
        <h2 className="text-base font-semibold" style={{ color: "var(--ink)" }}>
          Manage connection
        </h2>
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" disabled={isActive || isRetired || busy} onClick={() => setConfirming("pause")} className="rounded-md border px-4 py-2 text-sm font-semibold outline-none focus-visible:ring-2 disabled:opacity-50" style={{ borderColor: "var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}>
            Pause source
          </button>
          <button type="button" disabled={isRetired || busy} onClick={() => setConfirming("replace")} className="rounded-md border px-4 py-2 text-sm font-semibold outline-none focus-visible:ring-2 disabled:opacity-50" style={{ borderColor: "var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}>
            Replace source
          </button>
          <button type="button" disabled={isRetired || busy} onClick={() => setConfirming("retire")} className="rounded-md border px-4 py-2 text-sm font-semibold outline-none focus-visible:ring-2 disabled:opacity-50" style={{ borderColor: "var(--bad)", background: "var(--surface-2)", color: "var(--bad)" }}>
            {pendingAction === "retire" ? "Retiring…" : "Retire source"}
          </button>
        </div>
        {isActive && (
          <p className="mt-2 text-xs" style={{ color: "var(--ink-2)" }}>
            An active connection must be paused before retirement.
          </p>
        )}
      </div>

      {actionError && (
        <SafeOutcomeNotice variant="error" title="Action failed" code={actionError.code} requestId={actionError.requestId} replayed={actionError.replayed}>
          Nothing was changed. Review the safe reason above and try again.
        </SafeOutcomeNotice>
      )}
      {actionResult?.replayed && !actionError && (
        <SafeOutcomeNotice variant="success" title="Already applied" code="IDEMPOTENT_REPLAY" replayed>
          This action was already applied. The safe result is shown again with no duplicate effect.
        </SafeOutcomeNotice>
      )}

      <SlideOver open={confirming !== null} onClose={() => setConfirming(null)}>
        <div role="alertdialog" aria-modal="true" aria-labelledby="lifecycle-confirm-title" className="flex h-full flex-col gap-4 p-6">
          <h2 id="lifecycle-confirm-title" className="text-lg font-semibold" style={{ color: "var(--ink)" }}>
            Confirm {confirming === "pause" ? "pause" : confirming === "replace" ? "replacement" : "retirement"}
          </h2>
          <p className="text-sm" style={{ color: "var(--ink-2)" }}>
            {confirming === "retire"
              ? "Retirement is terminal. The connection stops serving and cannot be reactivated."
              : confirming === "pause"
                ? "Pausing stops sync and serving until the connection is tested and reactivated."
                : "Replacement creates a successor draft linked to this connection."}
          </p>
          <div className="mt-auto flex gap-2">
            <button type="button" onClick={() => setConfirming(null)} className="rounded-md border px-4 py-2 text-sm font-semibold outline-none focus-visible:ring-2" style={{ borderColor: "var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}>
              Cancel
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                if (confirming) onAction(confirming, confirmBody(confirming));
                setConfirming(null);
              }}
              className="rounded-md px-4 py-2 text-sm font-semibold outline-none focus-visible:ring-2 disabled:opacity-50"
              style={{ background: "var(--primary)", color: "#fff" }}
            >
              Confirm
            </button>
          </div>
        </div>
      </SlideOver>
    </section>
  );
}

/* CMP-9 — Sync Activity Summary */

export function SyncActivitySummary({ connection }: { connection: SafeConnection }) {
  const manualSync = useManualSyncMutation();
  // Lease-held is only meaningful as the answer to a trigger made here; a stale
  // lease-held last run on page load must not claim a sync is running now.
  const [triggered, setTriggered] = useState(false);

  if (connection.provider === "azure_postgresql_data_plane") {
    return <DataPlanePanel />;
  }

  if (connection.provider === "azure_postgresql") {
    return (
      <section aria-label="Sync activity" className="rounded-md border p-4" style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}>
        <h2 className="text-base font-semibold" style={{ color: "var(--ink)" }}>
          Sync activity
        </h2>
        <p className="mt-1 text-sm" style={{ color: "var(--ink-2)" }}>
          Sync scheduling does not apply to PostgreSQL connections. Contract state governs direct chat.
        </p>
      </section>
    );
  }
  const sync = connection.last_sync;
  const isActive = connection.status === "active";
  const pending = manualSync.isPending;
  const syncError = (manualSync.error as SafeApiHttpError | null) ?? null;
  const leaseHeld = triggered && sync?.outcome === "lease_held";

  function handleSync() {
    if (!isActive || pending) return;
    setTriggered(false);
    manualSync.mutate({ connectionId: connection.id }, { onSuccess: () => setTriggered(true) });
  }

  return (
    <section aria-label="Sync activity" className="rounded-md border p-4" style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold" style={{ color: "var(--ink)" }}>
          Sync activity
        </h2>
        <button
          type="button"
          disabled={!isActive || pending}
          onClick={handleSync}
          className="rounded-md border px-4 py-2 text-sm font-semibold outline-none focus-visible:ring-2 disabled:opacity-50"
          style={{ borderColor: "var(--primary)", background: "var(--surface-2)", color: "var(--primary-2)" }}
        >
          {pending ? "Starting sync…" : "Sync now"}
        </button>
      </div>
      <dl className="mt-2 grid gap-1 text-sm">
        <div className="flex gap-2">
          <dt style={{ color: "var(--ink-2)" }}>Schedule:</dt>
          <dd style={{ color: "var(--ink)" }}>{connection.schedule.enabled ? `Active${connection.schedule.cadence_minutes ? ` · every ${connection.schedule.cadence_minutes} minutes` : ""}` : "Paused"}</dd>
        </div>
        <div className="flex gap-2">
          <dt style={{ color: "var(--ink-2)" }}>Last run:</dt>
          <dd style={{ color: "var(--ink)" }}>
            {sync ? `${sync.outcome.replace(/_/g, " ")}${sync.completed_at ? ` · ${new Date(sync.completed_at).toLocaleString()}` : ""}` : "No run yet"}
          </dd>
        </div>
      </dl>
      <div className="mt-3 flex flex-col gap-2">
        {!isActive && (
          <SafeOutcomeNotice variant="blocked" title="Sync unavailable" code="INACTIVE_CONNECTION">
            Activate the connection before triggering a sync.
          </SafeOutcomeNotice>
        )}
        {pending && (
          <p role="status" aria-label="Sync pending" className="text-sm" style={{ color: "var(--ink-2)" }}>
            Queuing a manual sync…
          </p>
        )}
        {!pending && syncError && (
          <SafeOutcomeNotice variant="error" title="Sync not started" code={syncError.code} requestId={syncError.requestId} replayed={syncError.replayed}>
            Nothing was queued. Review the safe reason above and try again.
          </SafeOutcomeNotice>
        )}
        {!pending && manualSync.isSuccess && leaseHeld && (
          <SafeOutcomeNotice variant="warning" title="Sync already running">
            A sync for this connection is already in progress. Try again after it finishes.
          </SafeOutcomeNotice>
        )}
        {!pending && manualSync.isSuccess && !leaseHeld && (
          <SafeOutcomeNotice variant="success" title="Sync queued" replayed={manualSync.data.replayed}>
            A manual sync was queued. Last-run status refreshes here when it completes.
          </SafeOutcomeNotice>
        )}
      </div>
    </section>
  );
}
