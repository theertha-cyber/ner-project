import { render, screen, within, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import type { AuthUser } from "@/lib/auth";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => "/dashboard",
}));

let mockUser: AuthUser | null = null;
const mockLogout = vi.fn();

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: mockUser,
    getAccessToken: () => null,
    setAccessToken: vi.fn(),
    login: vi.fn(),
    logout: mockLogout,
  }),
}));

vi.mock("@/hooks", () => ({
  useDarkMode: () => ({ dark: false, toggle: vi.fn() }),
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

  // ── Tenant pill ──────────────────────────────────────────────────────────────

  it("tenant pill contains ▾ caret", () => {
    mockUser = createUser("annotator");
    render(<Sidebar effectiveRole="annotator" />);
    // Both the tenant pill and the user strip button render ▾
    expect(screen.getAllByText("▾").length).toBeGreaterThanOrEqual(2);
  });

  // ── User strip trigger ───────────────────────────────────────────────────────

  it("chevron rotates when menu opens and closes", () => {
    mockUser = createUser("annotator");
    render(<Sidebar effectiveRole="annotator" />);

    const trigger = screen.getAllByRole("button").find(
      (b) => b.getAttribute("aria-haspopup") === "true",
    )!;

    // The chevron ▾ span lives inside the trigger button
    const getChevron = () =>
      Array.from(trigger.querySelectorAll("span")).find(
        (el) => el.textContent === "▾",
      ) as HTMLElement;

    expect(getChevron().style.transform).toBe("rotate(0deg)");

    fireEvent.click(trigger);
    expect(getChevron().style.transform).toBe("rotate(180deg)");

    fireEvent.click(trigger);
    expect(getChevron().style.transform).toBe("rotate(0deg)");
  });

  it("backdrop is rendered when menu is open", () => {
    mockUser = createUser("annotator");
    const { container } = render(<Sidebar effectiveRole="annotator" />);

    const trigger = screen.getAllByRole("button").find(
      (b) => b.getAttribute("aria-haspopup") === "true",
    )!;

    expect(
      container.querySelector('[style*="position: fixed"]'),
    ).toBeNull();

    fireEvent.click(trigger);

    expect(
      container.querySelector('[style*="position: fixed"]'),
    ).not.toBeNull();
  });

  it("Escape key closes the menu", () => {
    mockUser = createUser("annotator");
    render(<Sidebar effectiveRole="annotator" />);

    const trigger = screen.getAllByRole("button").find(
      (b) => b.getAttribute("aria-haspopup") === "true",
    )!;

    fireEvent.click(trigger);
    expect(screen.getByText("Settings")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByText("Settings")).not.toBeInTheDocument();
  });

  it("Logout menu item uses ⎋ icon", () => {
    mockUser = createUser("annotator");
    render(<Sidebar effectiveRole="annotator" />);

    const trigger = screen.getAllByRole("button").find(
      (b) => b.getAttribute("aria-haspopup") === "true",
    )!;
    fireEvent.click(trigger);

    expect(screen.getByText("⎋")).toBeInTheDocument();
  });
});

// ── Topbar — AS label (covers verification rows 12–13) ──────────────────────

describe("Topbar — AS label in demo mode", () => {
  it("shows AS label when NEXT_PUBLIC_DEMO_MODE is true", () => {
    mockUser = createUser("annotator");
    const original = process.env.NEXT_PUBLIC_DEMO_MODE;
    process.env.NEXT_PUBLIC_DEMO_MODE = "true";

    render(<Topbar demoRole={null} onDemoRoleChange={vi.fn()} />);
    expect(screen.getByText("AS")).toBeInTheDocument();

    process.env.NEXT_PUBLIC_DEMO_MODE = original;
  });

  it("hides AS label when NEXT_PUBLIC_DEMO_MODE is not true", () => {
    mockUser = createUser("annotator");
    const original = process.env.NEXT_PUBLIC_DEMO_MODE;
    process.env.NEXT_PUBLIC_DEMO_MODE = "false";

    render(<Topbar demoRole={null} onDemoRoleChange={vi.fn()} />);
    expect(screen.queryByText("AS")).not.toBeInTheDocument();

    process.env.NEXT_PUBLIC_DEMO_MODE = original;
  });
});
