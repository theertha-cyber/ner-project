import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  SafeApiHttpError,
  publishContract,
  uploadContract,
  useDataSource,
  useDataSourceCollection,
  useDataSourceMutation,
} from "./use-data-sources";

const mockAuthFetch = vi.fn();

vi.mock("@/lib/auth-fetch", () => ({
  authFetch: (...args: unknown[]) => mockAuthFetch(...args),
}));

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

const CONNECTION = {
  id: "conn-1",
  provider: "azure_blob",
  status: "draft",
  configured_fields: ["account", "container"],
  secret_reference_fields: ["connection_string_ref"],
  last_test: { outcome: "not_run", reason_code: "none", tested_at: null },
  activation: { outcome: "inactive", reason_code: "none", activated_at: null },
  schedule: { enabled: false, cadence_minutes: null },
  replaces_connection_id: null,
  replaced_by_connection_id: null,
  created_at: "2026-09-10T00:00:00Z",
  updated_at: "2026-09-10T00:00:00Z",
};

describe("useDataSourceCollection", () => {
  beforeEach(() => mockAuthFetch.mockReset());

  it("requests only allowlisted parameters with contract defaults", async () => {
    mockAuthFetch.mockResolvedValue(
      new Response(JSON.stringify({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 }), { status: 200 }),
    );
    const { result } = renderHook(() => useDataSourceCollection({}), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const url = String(mockAuthFetch.mock.calls[0][0]);
    expect(url).toMatch(/^\/api\/v1\/data-sources\?/);
    const keys = [...new URLSearchParams(url.split("?")[1]).keys()].sort();
    expect(keys).toEqual(["order", "page", "page_size", "sort"]);
  });

  it("surfaces finite safe error codes with the request ID", async () => {
    mockAuthFetch.mockResolvedValue(
      new Response(
        JSON.stringify({ code: "INVALID_REQUEST", message: "Bad sort.", request_id: "req-9" }),
        { status: 422 },
      ),
    );
    const { result } = renderHook(() => useDataSourceCollection({}), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));
    const err = result.current.error as SafeApiHttpError;
    expect(err).toBeInstanceOf(SafeApiHttpError);
    expect(err.code).toBe("INVALID_REQUEST");
    expect(err.requestId).toBe("req-9");
  });
});

describe("useDataSource", () => {
  beforeEach(() => mockAuthFetch.mockReset());

  it("fetches the safe detail shape", async () => {
    mockAuthFetch.mockResolvedValue(new Response(JSON.stringify(CONNECTION), { status: 200 }));
    const { result } = renderHook(() => useDataSource("conn-1"), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockAuthFetch.mock.calls[0][0]).toBe("/api/v1/data-sources/conn-1");
    expect(result.current.data?.configured_fields).toEqual(["account", "container"]);
  });
});

describe("useDataSourceMutation", () => {
  beforeEach(() => mockAuthFetch.mockReset());

  it("sends an Idempotency-Key and surfaces replay", async () => {
    mockAuthFetch.mockResolvedValue(
      new Response(JSON.stringify(CONNECTION), { status: 200, headers: { "Idempotent-Replay": "true" } }),
    );
    const { result } = renderHook(() => useDataSourceMutation(), { wrapper: createWrapper() });
    let outcome: unknown;
    await result.current.mutateAsync(
      { action: "activate", connectionId: "conn-1", body: { activation_evidence: ["governance_approved", "network_approved"] } },
      { onSuccess: (r) => { outcome = r; } },
    );
    const init = mockAuthFetch.mock.calls[0][1] as RequestInit;
    const headers = new Headers(init.headers);
    expect(headers.get("Idempotency-Key")).toMatch(/^[\x20-\x7E]{1,128}$/);
    expect((outcome as { replayed: boolean }).replayed).toBe(true);
  });

  it("carries 409 prerequisite blocks as safe errors", async () => {
    mockAuthFetch.mockResolvedValue(
      new Response(
        JSON.stringify({ code: "ACTIVATION_PREREQUISITE_MISSING", message: "Evidence missing.", request_id: "req-2" }),
        { status: 409 },
      ),
    );
    const { result } = renderHook(() => useDataSourceMutation(), { wrapper: createWrapper() });
    await expect(
      result.current.mutateAsync({ action: "activate", connectionId: "conn-1", body: { activation_evidence: [] } }),
    ).rejects.toMatchObject({ code: "ACTIVATION_PREREQUISITE_MISSING", requestId: "req-2" });
  });
});

describe("contracts", () => {
  beforeEach(() => mockAuthFetch.mockReset());

  it("uploads raw JSON with an idempotency key", async () => {
    mockAuthFetch.mockResolvedValue(
      new Response(JSON.stringify({ id: "c-1", version: 3, fingerprint: "abc" }), { status: 201 }),
    );
    const draft = await uploadContract("conn-2", { version: 3, relations: [] });
    const [url, init] = mockAuthFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/data-sources/conn-2/contracts");
    expect(new Headers(init.headers).get("Idempotency-Key")).toBeTruthy();
    expect(draft.version).toBe(3);
  });

  it("publishes through the versioned route and keeps field errors", async () => {
    mockAuthFetch.mockResolvedValue(
      new Response(
        JSON.stringify({
          code: "INVALID_CONTRACT",
          message: "Not valid.",
          request_id: "req-3",
          field_errors: [{ field: "relations", message: "At least one relation is required." }],
        }),
        { status: 422 },
      ),
    );
    await expect(uploadContract("conn-2", { version: 4 })).rejects.toMatchObject({
      code: "INVALID_CONTRACT",
      fieldErrors: [{ field: "relations", message: "At least one relation is required." }],
    });
    mockAuthFetch.mockResolvedValue(new Response(JSON.stringify({ version: 3 }), { status: 200 }));
    const published = await publishContract("conn-2", 3);
    expect(mockAuthFetch.mock.calls[1][0]).toBe("/api/v1/data-sources/conn-2/contracts/3/publish");
    expect(published.version).toBe(3);
  });
});
