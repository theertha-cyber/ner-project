import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { ReactNode } from "react";
import { AuthProvider, useAuth } from "./auth";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
}));

vi.mock("./auth-fetch", () => ({
  initAuthFetch: vi.fn(),
}));

const wrapper = ({ children }: { children: ReactNode }) => <AuthProvider>{children}</AuthProvider>;

const MOCK_RAW_USER = {
  id: "user-1",
  email: "test@example.com",
  role: "tenant_admin",
  tenant_id: "tenant-1",
  tenant_slug: "acme",
};

const MOCK_RESPONSE = {
  access_token: "access-token-123",
  token_type: "bearer",
  user: MOCK_RAW_USER,
};

describe("useAuth — outside provider", () => {
  it("throws when used outside AuthProvider", () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => renderHook(() => useAuth())).toThrow("useAuth must be used within AuthProvider");
    consoleSpy.mockRestore();
  });
});

describe("AuthProvider", () => {
  beforeEach(() => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 401 }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("starts with null user when on-mount refresh fails", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => {
      expect(result.current.user).toBeNull();
      expect(result.current.getAccessToken()).toBeNull();
    });
  });

  it("on-mount refresh success sets token ref and user", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(MOCK_RESPONSE), { status: 200 }),
    );

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.user?.userId).toBe("user-1");
      expect(result.current.user?.email).toBe("test@example.com");
      expect(result.current.user?.role).toBe("tenant_admin");
      expect(result.current.user?.tenantSlug).toBe("acme");
    });
    expect(result.current.getAccessToken()).toBe("access-token-123");
  });

  it("login sets user and token without writing to localStorage", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(MOCK_RESPONSE), { status: 200 }));
    const setItemSpy = vi.spyOn(Storage.prototype, "setItem");

    const { result } = renderHook(() => useAuth(), { wrapper });

    await act(async () => {
      await result.current.login("test@example.com", "password");
    });

    expect(result.current.user?.userId).toBe("user-1");
    expect(result.current.getAccessToken()).toBe("access-token-123");
    expect(setItemSpy).not.toHaveBeenCalled();
  });

  it("login throws the API error message on 401", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ error: { message: "Invalid credentials" } }), {
          status: 401,
        }),
      );

    const { result } = renderHook(() => useAuth(), { wrapper });

    await expect(
      act(async () => {
        await result.current.login("bad@example.com", "wrong");
      }),
    ).rejects.toThrow("Invalid credentials");
    expect(result.current.user).toBeNull();
  });

  it("logout calls logout API and clears token and user", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(MOCK_RESPONSE), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ message: "ok" }), { status: 200 }));

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.user).not.toBeNull();
    });

    await act(async () => {
      await result.current.logout();
    });

    expect(result.current.user).toBeNull();
    expect(result.current.getAccessToken()).toBeNull();
  });

  it("setAccessToken updates subsequent getAccessToken reads", () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    act(() => {
      result.current.setAccessToken("new-token-xyz");
    });
    expect(result.current.getAccessToken()).toBe("new-token-xyz");
  });

  it("getAccessToken is synchronous", () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    const token = result.current.getAccessToken();
    expect(typeof token === "string" || token === null).toBe(true);
  });
});
