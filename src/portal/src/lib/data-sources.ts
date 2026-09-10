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

export const PROVIDERS = ["azure_blob", "azure_postgresql"] as const;
export type ConnectionProvider = (typeof PROVIDERS)[number];

export const PROVIDER_LABELS: Record<ConnectionProvider, string> = {
  azure_blob: "Azure Blob Storage",
  azure_postgresql: "Azure Database for PostgreSQL",
};

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
  outcome: "never_run" | "succeeded" | "failed" | "blocked";
  completed_at: string | null;
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
  "CONNECTION_TEST_UNAVAILABLE",
  "INVALID_CONTRACT",
  "CONTRACT_VERSION_EXISTS",
  "PUBLISH_PRECONDITION_FAILED",
  "IDEMPOTENCY_KEY_REQUIRED",
  "IDEMPOTENCY_KEY_REUSED",
  "INTERNAL_ERROR",
] as const;

export interface SafeApiError {
  code: string;
  message: string;
  request_id: string;
  field_errors?: ContractFieldError[];
  reason?: string;
  replayed?: boolean;
}

export const REQUIRED_ACTIVATION_EVIDENCE = ["governance_approved", "network_approved"] as const;

/** Closed configuration keys per provider. Values are write-only. */
export const BLOB_CONFIG_KEYS = ["account", "container", "prefix"] as const;
export const BLOB_SECRET_KEYS = ["connection_string_ref"] as const;
export const POSTGRES_CONFIG_KEYS = ["host", "database", "username", "port", "sslmode"] as const;
export const POSTGRES_SECRET_KEYS = ["password_ref"] as const;

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

export async function parseSafeError(res: Response): Promise<SafeApiError> {
  const requestId = res.headers.get("x-request-id") ?? "";
  let body: Record<string, unknown> = {};
  try {
    body = (await res.json()) as Record<string, unknown>;
  } catch {
    body = {};
  }
  const replayed = res.headers.get("Idempotent-Replay") === "true";
  return {
    code: typeof body.code === "string" ? body.code : "INTERNAL_ERROR",
    message: typeof body.message === "string" ? body.message : "Request failed.",
    request_id: typeof body.request_id === "string" && body.request_id ? body.request_id : requestId,
    field_errors: Array.isArray(body.field_errors)
      ? (body.field_errors as ContractFieldError[]).filter((e) => typeof e?.field === "string")
      : undefined,
    reason: typeof body.reason === "string" ? body.reason : undefined,
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

export function buildPostgresPayload(values: {
  host: string;
  database: string;
  username: string;
  port: string;
  password_ref: string;
}): { configuration: Record<string, string>; secret_references: Record<string, string> } {
  return {
    configuration: {
      host: values.host.trim(),
      database: values.database.trim(),
      username: values.username.trim(),
      port: values.port.trim(),
      sslmode: "verify-full",
    },
    secret_references: { password_ref: values.password_ref.trim() },
  };
}
