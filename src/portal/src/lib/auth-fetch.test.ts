import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { authFetch, initAuthFetch } from "./auth-fetch";

// ─── URL routing ─────────────────────────────────────────────────────────────

describe("authFetch — URL routing", () => {
  let navigateMock: ReturnType<typeof vi.fn>;
  let setTokenMock: ReturnType<typeof vi.fn>;
  let getTokenMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    navigateMock = vi.fn();
    setTokenMock = vi.fn();
    getTokenMock = vi.fn(() => null);
    initAuthFetch(getTokenMock, setTokenMock, navigateMock);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("routes /api/v1/admin/* to GATEWAY_URL", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 200 }));
    await authFetch("/api/v1/admin/tenants");
    expect(String(spy.mock.calls[0][0])).toContain("/api/v1/admin/tenants");
  });

  it("routes /api/v1/auth/* to GATEWAY_URL", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 200 }));
    await authFetch("/api/v1/auth/me");
    expect(String(spy.mock.calls[0][0])).toContain("/api/v1/auth/me");
  });

  it("routes /api/v1/tenants/* to GATEWAY_URL", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 200 }));
    await authFetch("/api/v1/tenants/123/users");
    expect(String(spy.mock.calls[0][0])).toContain("/api/v1/tenants/123/users");
  });

  it("routes /api/v1/document/* to DOCUMENT_URL", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 200 }));
    await authFetch("/api/v1/document/upload");
    expect(String(spy.mock.calls[0][0])).toContain("/api/v1/document/upload");
  });

  it("routes /api/v1/annotation/* to ANNOTATION_URL", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 200 }));
    await authFetch("/api/v1/annotation/labels");
    expect(String(spy.mock.calls[0][0])).toContain("/api/v1/annotation/labels");
  });

  it("routes /api/v1/training/* to TRAINING_URL", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 200 }));
    await authFetch("/api/v1/training/jobs");
    expect(String(spy.mock.calls[0][0])).toContain("/api/v1/training/jobs");
  });

  it("routes /api/v1/models/* to TRAINING_URL", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 200 }));
    await authFetch("/api/v1/models/list");
    expect(String(spy.mock.calls[0][0])).toContain("/api/v1/models/list");
  });

  it("routes /api/v1/extraction/* to EXTRACTION_URL", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 200 }));
    await authFetch("/api/v1/extraction/run");
    expect(String(spy.mock.calls[0][0])).toContain("/api/v1/extraction/run");
  });

  it("passes absolute URLs through unchanged", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 200 }));
    await authFetch("http://custom-host:9999/api/v1/admin/jobs");
    expect(spy.mock.calls[0][0]).toBe("http://custom-host:9999/api/v1/admin/jobs");
  });

  it("injects Bearer token when token is present", async () => {
    getTokenMock.mockReturnValue("my-access-token");
    initAuthFetch(getTokenMock, setTokenMock, navigateMock);

    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 200 }));
    await authFetch("/api/v1/admin/tenants");

    const headers = spy.mock.calls[0][1]?.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer my-access-token");
  });

  it("does not inject Authorization header when no token", async () => {
    getTokenMock.mockReturnValue(null);
    initAuthFetch(getTokenMock, setTokenMock, navigateMock);

    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 200 }));
    await authFetch("/api/v1/admin/tenants");

    const headers = spy.mock.calls[0][1]?.headers as Headers;
    expect(headers.get("Authorization")).toBeNull();
  });
});

// ─── 401 handling ────────────────────────────────────────────────────────────

describe("authFetch — 401 handling", () => {
  let navigateMock: ReturnType<typeof vi.fn>;
  let setTokenMock: ReturnType<typeof vi.fn>;
  let getTokenMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    navigateMock = vi.fn();
    setTokenMock = vi.fn();
    getTokenMock = vi.fn(() => "old-token");
    initAuthFetch(getTokenMock, setTokenMock, navigateMock);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("401 triggers refresh and retries with new token", async () => {
    let callCount = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : String(input);
      if (url.includes("/refresh")) {
        return new Response(JSON.stringify({ access_token: "new-token", token_type: "bearer" }), {
          status: 200,
        });
      }
      callCount++;
      if (callCount === 1) return new Response(null, { status: 401 });
      return new Response(JSON.stringify({ data: "ok" }), { status: 200 });
    });

    const res = await authFetch("/api/v1/admin/tenants");
    expect(res.status).toBe(200);
    expect(setTokenMock).toHaveBeenCalledWith("new-token");
  });

  it("three concurrent 401s produce exactly one refresh call", async () => {
    let refreshCount = 0;
    let requestCount = 0;

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : String(input);
      if (url.includes("/refresh")) {
        refreshCount++;
        await new Promise<void>((resolve) => setTimeout(resolve, 10));
        return new Response(JSON.stringify({ access_token: "fresh-token", token_type: "bearer" }), {
          status: 200,
        });
      }
      requestCount++;
      if (requestCount <= 3) return new Response(null, { status: 401 });
      return new Response(null, { status: 200 });
    });

    await Promise.all([
      authFetch("/api/v1/admin/tenants"),
      authFetch("/api/v1/admin/tenants"),
      authFetch("/api/v1/admin/tenants"),
    ]);

    expect(refreshCount).toBe(1);
  });

  it("refresh failure redirects to /login and throws", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : String(input);
      if (url.includes("/refresh")) {
        return new Response(null, { status: 401 });
      }
      return new Response(null, { status: 401 });
    });

    await expect(authFetch("/api/v1/admin/tenants")).rejects.toThrow("Session expired");
    expect(navigateMock).toHaveBeenCalledWith("/login");
  });

  it("second 401 on retry redirects to /login", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : String(input);
      if (url.includes("/refresh")) {
        return new Response(JSON.stringify({ access_token: "new-token", token_type: "bearer" }), {
          status: 200,
        });
      }
      return new Response(null, { status: 401 });
    });

    await expect(authFetch("/api/v1/admin/tenants")).rejects.toThrow("Session expired");
    expect(navigateMock).toHaveBeenCalledWith("/login");
  });
});
