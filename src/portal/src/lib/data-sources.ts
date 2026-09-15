"use client";

/**
 * Safe-only client contracts for the tenant data-source administration portal (CAP-5).
 *
 * These types model the safe `Connection` / `ConnectionPage` response shapes only:
 * provider, status, configured/secret field NAMES, finite outcome classes, reason
 * codes, schedule links, replacement links, and timestamps. There is deliberately
 * no member for configuration values, secret values, connection strings, endpoint
 * details, provider diagnostics, SQL, prompts, answers, or tenant content, so the
 * UI cannot render what it cannot hold.
 */

export const PROVIDERS = ["azure_blob", "azure_postgresql", "azure_postgresql_data_plane"] as const;
export type ConnectionProvider = (typeof PROVIDERS)[number];

export const PROVIDER_LABELS: Record<ConnectionProvider, string> = {
  azure_blob: "Azure Blob Storage",
  azure_postgresql: "Azure Database for PostgreSQL",
  // Labelled distinctly from the read-only `azure_postgresql` source (ADR-017,
  // task 13.1): this one *is* the tenant's data plane — every document, span,
  // chunk, and conversation for the tenant lives here, not a copy of it.
  azure_postgresql_data_plane: "Tenant-Owned PostgreSQL (Data Plane)",
};

/** Providers a `tenant_owned` tenant may configure that a `platform` tenant may
 * not (task 13.1's "shown only for tenant_owned tenants") — `PROVIDERS` minus
 * this set is what a `platform` tenant's catalog offers. */
export const TENANT_OWNED_ONLY_PROVIDERS: ReadonlySet<ConnectionProvider> = new Set([
  "azure_postgresql_data_plane",
]);

export const STATUSES = ["draft", "validated", "active", "paused", "error", "retired"] as const;
export type ConnectionStatus = (typeof STATUSES)[number];

export const STATUS_LABELS: Record<ConnectionStatus, string> = {
  draft: "Draft",
  validated: "Validated",
  active: "Active",
  paused: "Paused",
  error: "Error",
  retired: "Retired",
};

export const LIST_SORTS = ["last_activity", "created_at", "provider", "status"] as const;
export type ListSort = (typeof LIST_SORTS)[number];

export const LIST_ORDERS = ["asc", "desc"] as const;
export type ListOrder = (typeof LIST_ORDERS)[number];

export const PAGE_SIZE_DEFAULT = 20;
export const PAGE_SIZE_MIN = 1;
export const PAGE_SIZE_MAX = 100;
export const QUERY_MAX_LENGTH = 100;

export interface TestOutcome {
  outcome: "passed" | "failed" | "not_run";
  reason_code: string;
  tested_at: string | null;
}

export interface ActivationOutcome {
  outcome: "active" | "inactive" | "blocked";
  reason_code: string;
  activated_at: string | null;
}

export interface ConnectionSchedule {
  enabled: boolean;
  cadence_minutes: number | null;
}

export interface LastSync {
  outcome: "never_run" | "succeeded" | "failed" | "blocked" | "lease_held";
  completed_at: string | null;
}

/** Safe manual-sync trigger result. Identifiers and finite classes only. */
export interface ManualSyncResult {
  connection_id: string;
  trigger: "manual";
  outcome: "enqueued";
  enqueued_at: string;
}

export interface SafeConnection {
  id: string;
  provider: ConnectionProvider;
  status: ConnectionStatus;
  configured_fields: string[];
  secret_reference_fields: string[];
  last_test: TestOutcome;
  activation: ActivationOutcome;
  schedule: ConnectionSchedule;
  last_sync?: LastSync;
  replaces_connection_id: string | null;
  replaced_by_connection_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConnectionPage {
  items: SafeConnection[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ContractVersionItem {
  version: number;
  fingerprint: string;
  validation_reason: string | null;
  published: boolean;
  published_at?: string | null;
}

export interface ContractHistory {
  items: ContractVersionItem[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface ContractDraft {
  id: string;
  version: number;
  fingerprint: string;
  validation_reason?: string | null;
}

export interface ContractFieldError {
  field: string;
  message: string;
}

/** Finite safe error codes the UI may render (code + request ID only). */
export const FINITE_ERROR_CODES = [
  "UNAUTHENTICATED",
  "FORBIDDEN",
  "CONNECTION_NOT_FOUND",
  "INVALID_REQUEST",
  "INVALID_LIFECYCLE_TRANSITION",
  "TEST_REQUIRED",
  "TEST_FAILED",
  "ACTIVATION_PREREQUISITE_MISSING",
  "ACTIVE_PROVIDER_EXISTS",
  "RETIRED_CONNECTION",
  "RETIRE_CONFIRMATION_REQUIRED",
  "INACTIVE_CONNECTION",
  "UNSUPPORTED_PROVIDER",
  "SYNC_UNAVAILABLE",
  "CONNECTION_TEST_UNAVAILABLE",
  "INVALID_CONTRACT",
  "CONTRACT_VERSION_EXISTS",
  "PUBLISH_PRECONDITION_FAILED",
  "IDEMPOTENCY_KEY_REQUIRED",
  "IDEMPOTENCY_KEY_REUSED",
  "INTERNAL_ERROR",
  "TENANT_DATA_PLANE_NOT_READY",
  "TENANT_DATA_PLANE_UNAVAILABLE",
  "DATA_PLANE_NOT_TENANT_OWNED",
  "SECRET_REFERENCE_SHARED_ACROSS_PURPOSES",
] as const;

export interface SafeApiError {
  code: string;
  message: string;
  request_id: string;
  field_errors?: ContractFieldError[];
  reason?: string;
  replayed?: boolean;
  /** Carried only by `TENANT_DATA_PLANE_NOT_READY` (`data_plane_gate.py`'s
   * `_not_ready_handler` — the tenant's current `DataPlaneStatus`) and
   * `TENANT_DATA_PLANE_UNAVAILABLE` (`_unavailable_handler` — a finite
   * `HEALTH_*`-shaped reachability reason). Neither response carries `message`. */
  status_class?: string;
  reason_class?: string;
}

export const REQUIRED_ACTIVATION_EVIDENCE = ["governance_approved", "network_approved"] as const;

/** Closed configuration keys per provider. Values are write-only. */
export const BLOB_CONFIG_KEYS = ["account", "container", "prefix"] as const;
export const BLOB_SECRET_KEYS = ["connection_string_ref"] as const;
export const POSTGRES_CONFIG_KEYS = ["host", "database", "username", "port", "sslmode"] as const;
export const POSTGRES_SECRET_KEYS = ["password_ref"] as const;
// Same shape as `azure_postgresql` — the field set the backend's
// `PROVIDER_CONFIG_KEYS`/`PROVIDER_SECRET_FIELDS` declare for
// `azure_postgresql_data_plane` is identical (`providers.py`).
export const DATA_PLANE_CONFIG_KEYS = POSTGRES_CONFIG_KEYS;
export const DATA_PLANE_SECRET_KEYS = POSTGRES_SECRET_KEYS;

export interface CollectionQuery {
  q?: string;
  provider?: ConnectionProvider | "all";
  status?: ConnectionStatus | "all";
  sort?: ListSort;
  order?: ListOrder;
  page?: number;
  page_size?: number;
}

export function buildCollectionQuery(query: CollectionQuery): string {
  const params = new URLSearchParams();
  const q = (query.q ?? "").trim();
  if (q) params.set("q", q.slice(0, QUERY_MAX_LENGTH));
  if (query.provider && query.provider !== "all") params.set("provider", query.provider);
  if (query.status && query.status !== "all") params.set("status", query.status);
  params.set("sort", query.sort ?? "last_activity");
  params.set("order", query.order ?? "desc");
  params.set("page", String(Math.max(1, query.page ?? 1)));
  const size = Math.min(PAGE_SIZE_MAX, Math.max(PAGE_SIZE_MIN, query.page_size ?? PAGE_SIZE_DEFAULT));
  params.set("page_size", String(size));
  return params.toString();
}

/** A fresh idempotency key per distinct mutation intent (1–128 printable ASCII). */
export function newIdempotencyKey(): string {
  const rand = Array.from(crypto.getRandomValues(new Uint8Array(16)))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  const stamp = Date.now().toString(36);
  return `ds-${stamp}-${rand}`.slice(0, 64);
}

export function isIdempotencyKeyValid(key: string): boolean {
  return /^[\x20-\x7E]{1,128}$/.test(key);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Finite codes for framework-level refusals (`{"detail": ...}`) that carry no code of their own. */
const STATUS_FALLBACK_CODES: Record<number, string> = {
  401: "UNAUTHENTICATED",
  403: "FORBIDDEN",
};

export async function parseSafeError(res: Response): Promise<SafeApiError> {
  const requestId = res.headers.get("x-request-id") ?? "";
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  // The gateway nests the safe envelope under `error`; a top-level envelope is accepted too.
  // Anything else in the body (e.g. a framework `detail` string) is never read.
  const envelope: Record<string, unknown> = isRecord(body) ? (isRecord(body.error) ? body.error : body) : {};
  const replayed = res.headers.get("Idempotent-Replay") === "true";
  return {
    code: typeof envelope.code === "string" ? envelope.code : (STATUS_FALLBACK_CODES[res.status] ?? "INTERNAL_ERROR"),
    message: typeof envelope.message === "string" ? envelope.message : "Request failed.",
    request_id: typeof envelope.request_id === "string" && envelope.request_id ? envelope.request_id : requestId,
    field_errors: Array.isArray(envelope.field_errors)
      ? (envelope.field_errors as ContractFieldError[]).filter((e) => typeof e?.field === "string")
      : undefined,
    reason: typeof envelope.reason === "string" ? envelope.reason : undefined,
    status_class: typeof envelope.status_class === "string" ? envelope.status_class : undefined,
    reason_class: typeof envelope.reason_class === "string" ? envelope.reason_class : undefined,
    replayed,
  };
}

export function isReplayed(res: Response): boolean {
  return res.headers.get("Idempotent-Replay") === "true";
}

export function buildBlobPayload(values: {
  account: string;
  container: string;
  prefix?: string;
  connection_string_ref: string;
}): { configuration: Record<string, string>; secret_references: Record<string, string> } {
  const configuration: Record<string, string> = {
    account: values.account.trim(),
    container: values.container.trim(),
  };
  if (values.prefix?.trim()) configuration.prefix = values.prefix.trim();
  return { configuration, secret_references: { connection_string_ref: values.connection_string_ref.trim() } };
}

/* --- Tenant data plane (ADR-017) --------------------------------------------- */

export const DATA_PLANE_MODES = ["platform", "tenant_owned"] as const;
export type DataPlaneMode = (typeof DATA_PLANE_MODES)[number];

export const DATA_PLANE_STATUSES = [
  "awaiting_store",
  "provisioning",
  "provisioning_failed",
  "ready",
  "migration_required",
  "paused",
  "store_retired",
] as const;
export type DataPlaneStatus = (typeof DATA_PLANE_STATUSES)[number];

/** `GET /api/v1/data-plane`'s safe body — matches `_data_plane_body` in
 * `src/gateway/api/v1/data_sources.py`. No host, credential, or driver detail. */
export interface DataPlaneStatusResponse {
  mode: DataPlaneMode;
  status: DataPlaneStatus;
  status_reason: string;
  store_id: string | null;
  schema_revision: number | null;
}

/** States in which content pages must not render cached content (Design D9 —
 * the same set `require_data_plane_ready` treats as not-`ready`). */
export const DATA_PLANE_BLOCKING_STATUSES: ReadonlySet<DataPlaneStatus> = new Set([
  "awaiting_store",
  "provisioning",
  "provisioning_failed",
  "migration_required",
  "paused",
  "store_retired",
]);

export function buildPostgresPayload(values: {
  host: string;
  database: string;
  username: string;
  port: string;
  password_ref: string;
}): { configuration: Record<string, string | number>; secret_references: Record<string, string> } {
  return {
    configuration: {
      host: values.host.trim(),
      database: values.database.trim(),
      username: values.username.trim(),
      // The backend requires an actual integer (providers.py's port-range
      // check rejects a string outright, with no field highlighted in this
      // form since client-side validation only checks it's digits).
      port: Number(values.port.trim()),
      sslmode: "verify-full",
    },
    secret_references: { password_ref: values.password_ref.trim() },
  };
}
