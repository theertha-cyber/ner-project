import { describe, it, expect } from "vitest";
import {
  buildBlobPayload,
  buildCollectionQuery,
  buildPostgresPayload,
  isIdempotencyKeyValid,
  newIdempotencyKey,
  parseSafeError,
} from "./data-sources";

describe("buildCollectionQuery", () => {
  it("applies page-1, 20-item, last-activity-desc defaults", () => {
    const qs = buildCollectionQuery({});
    expect(qs).toContain("sort=last_activity");
    expect(qs).toContain("order=desc");
    expect(qs).toContain("page=1");
    expect(qs).toContain("page_size=20");
  });

  it("emits only the allowlisted parameters", () => {
    const qs = buildCollectionQuery({ q: "blob", provider: "azure_blob", status: "active", page: 3 });
    const keys = new URLSearchParams(qs);
    expect([...keys.keys()].sort()).toEqual(
      ["order", "page", "page_size", "provider", "q", "sort", "status"].sort(),
    );
  });

  it("omits the all sentinel for provider and status", () => {
    const qs = buildCollectionQuery({ provider: "all", status: "all" });
    expect(qs).not.toContain("provider=");
    expect(qs).not.toContain("status=");
  });

  it("clamps page_size to 1..100 and floors page at 1", () => {
    expect(buildCollectionQuery({ page_size: 500 })).toContain("page_size=100");
    expect(buildCollectionQuery({ page_size: 0 })).toContain("page_size=1");
    expect(buildCollectionQuery({ page: -2 })).toContain("page=1");
  });

  it("truncates overlong search to 100 chars", () => {
    const qs = buildCollectionQuery({ q: "x".repeat(250) });
    expect(new URLSearchParams(qs).get("q")).toHaveLength(100);
  });
});

describe("idempotency keys", () => {
  it("generates a fresh printable-ASCII key per call", () => {
    const a = newIdempotencyKey();
    const b = newIdempotencyKey();
    expect(a).not.toEqual(b);
    expect(isIdempotencyKeyValid(a)).toBe(true);
    expect(isIdempotencyKeyValid("")).toBe(false);
    expect(isIdempotencyKeyValid("x".repeat(129))).toBe(false);
  });
});

describe("parseSafeError", () => {
  it("keeps only the safe envelope and replay flag", async () => {
    const res = new Response(
      JSON.stringify({
        code: "ACTIVATION_PREREQUISITE_MISSING",
        message: "Provide the required activation evidence.",
        request_id: "req-123",
        provider_detail: "tls handshake failed at 10.0.0.1",
      }),
      { status: 409, headers: { "Idempotent-Replay": "true" } },
    );
    const err = await parseSafeError(res);
    expect(err.code).toBe("ACTIVATION_PREREQUISITE_MISSING");
    expect(err.request_id).toBe("req-123");
    expect(err.replayed).toBe(true);
    expect(err).not.toHaveProperty("provider_detail");
  });

  it("falls back to INTERNAL_ERROR on an empty body", async () => {
    const err = await parseSafeError(new Response(null, { status: 500 }));
    expect(err.code).toBe("INTERNAL_ERROR");
  });
});

describe("closed-schema payloads", () => {
  it("builds the Blob payload with optional prefix", () => {
    const payload = buildBlobPayload({ account: " acct ", container: " c ", connection_string_ref: " ref-1 " });
    expect(payload.configuration).toEqual({ account: "acct", container: "c" });
    expect(payload.secret_references).toEqual({ connection_string_ref: "ref-1" });
  });

  it("builds the PostgreSQL payload with verify-full sslmode", () => {
    const payload = buildPostgresPayload({
      host: "h", database: "d", username: "u", port: "5432", password_ref: "ref-2",
    });
    expect(payload.configuration.sslmode).toBe("verify-full");
    expect(payload.secret_references).toEqual({ password_ref: "ref-2" });
  });
});
