import { render, screen, within } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Sidebar } from "./Sidebar";
import type { AuthUser } from "@/lib/auth";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => "/dashboard",
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

function createUser(role: AuthUser["role"], overrides?: Partial<AuthUser>): AuthUser {
  return {
    userId: "1",
    email: "user@example.com",
    role,
    tenantId: "t-1",
    tenantSlug: "acme",
    ...overrides,
  };
}

describe("Sidebar", () => {
  it("renders nav items for system_admin without Platform Settings", () => {
    mockUser = createUser("system_admin", { tenantSlug: null });
    render(<Sidebar effectiveRole="system_admin" />);
    const nav = screen.getByRole("navigation");
    expect(within(nav).getByText("Dashboard")).toBeInTheDocument();
    expect(within(nav).getByText("Tenants")).toBeInTheDocument();
    expect(within(nav).getByText("Audit Log")).toBeInTheDocument();
    expect(within(nav).queryByText("Platform Settings")).not.toBeInTheDocument();
  });

  it("renders nav items for tenant_admin without Settings", () => {
    mockUser = createUser("tenant_admin");
    render(<Sidebar effectiveRole="tenant_admin" />);
    const nav = screen.getByRole("navigation");
    expect(within(nav).getByText("Dashboard")).toBeInTheDocument();
    expect(within(nav).getByText("Documents")).toBeInTheDocument();
    expect(within(nav).getByText("Users")).toBeInTheDocument();
    expect(within(nav).queryByText("Settings")).not.toBeInTheDocument();
  });

  it("renders nav items for annotator (3 items, no Settings)", () => {
    mockUser = createUser("annotator");
    render(<Sidebar effectiveRole="annotator" />);
    const nav = screen.getByRole("navigation");
    const navItems = ["My Work", "Annotation", "Documents"];
    for (const label of navItems) {
      expect(within(nav).getByText(label)).toBeInTheDocument();
    }
    expect(within(nav).queryByText("Settings")).not.toBeInTheDocument();
  });

  it("renders nav items for business_user (4 items, no Settings)", () => {
    mockUser = createUser("business_user");
    render(<Sidebar effectiveRole="business_user" />);
    const nav = screen.getByRole("navigation");
    const navItems = ["Overview", "Documents", "Extractions", "Models"];
    for (const label of navItems) {
      expect(within(nav).getByText(label)).toBeInTheDocument();
    }
    expect(within(nav).queryByText("Settings")).not.toBeInTheDocument();
  });
});
