import { render, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { RequireAuth } from "./require-auth";
import type { AuthUser } from "@/lib/auth";

const mockReplace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
}));

let mockUser: AuthUser | null = null;

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: mockUser,
    getAccessToken: () => null,
    setAccessToken: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
  }),
}));

describe("RequireAuth", () => {
  beforeEach(() => {
    mockUser = null;
    vi.clearAllMocks();
  });

  it("unauthenticated: renders nothing and redirects to /login", async () => {
    const { container } = render(
      <RequireAuth>
        <div>Protected</div>
      </RequireAuth>,
    );
    expect(container).toBeEmptyDOMElement();
    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/login");
    });
  });

  it("authenticated without roles: renders children", () => {
    mockUser = {
      userId: "1",
      email: "user@example.com",
      role: "tenant_admin",
      tenantId: "t-1",
      tenantSlug: "acme",
    };
    const { getByText } = render(
      <RequireAuth>
        <div>Dashboard Content</div>
      </RequireAuth>,
    );
    expect(getByText("Dashboard Content")).toBeInTheDocument();
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("role match: renders children", () => {
    mockUser = {
      userId: "1",
      email: "admin@example.com",
      role: "system_admin",
      tenantId: "t-1",
      tenantSlug: null,
    };
    const { getByText } = render(
      <RequireAuth roles={["system_admin"]}>
        <div>Admin Only</div>
      </RequireAuth>,
    );
    expect(getByText("Admin Only")).toBeInTheDocument();
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("role mismatch: renders nothing and redirects to /dashboard", async () => {
    mockUser = {
      userId: "2",
      email: "annotator@example.com",
      role: "annotator",
      tenantId: "t-1",
      tenantSlug: "acme",
    };
    const { container } = render(
      <RequireAuth roles={["system_admin"]}>
        <div>Admin Only</div>
      </RequireAuth>,
    );
    expect(container).toBeEmptyDOMElement();
    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/dashboard");
    });
  });
});
