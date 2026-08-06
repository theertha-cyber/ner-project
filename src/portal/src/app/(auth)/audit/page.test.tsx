import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AuditPage from "./page";
import type { AuditLogResponse } from "@/hooks/use-audit-log";
import type { TenantsResponse } from "@/hooks/use-tenants";

const mockEvents: AuditLogResponse = {
  events: [
    {
      id: "evt-1",
      actor: "admin@test.com",
      role: "system_admin",
      action: "tenant.deactivate",
      target: "test-tenant",
      kind: "reject",
      tenant_id: null,
      created_at: "2026-07-14T10:00:00Z",
    },
    {
      id: "evt-2",
      actor: "user@test.com",
      role: "tenant_admin",
      action: "entity_type.create",
      target: "vendor_name",
      kind: "create",
      tenant_id: "test-tenant",
      created_at: "2026-07-14T09:00:00Z",
    },
    {
      id: "evt-3",
      actor: "admin@test.com",
      role: "system_admin",
      action: "training_job.approve",
      target: "job-123",
      kind: "approve",
      tenant_id: "tenant-b",
      created_at: "2026-07-13T14:00:00Z",
    },
  ],
  total: 3,
  page: 1,
  per_page: 50,
};

const mockTenants: TenantsResponse = {
  tenants: [
    { id: "test-tenant", name: "Test Tenant", slug: "test-tenant", status: "active" },
    { id: "tenant-b", name: "Tenant B", slug: "tenant-b", status: "active" },
  ],
  total: 2,
  page: 1,
  per_page: 100,
};

let mockData: AuditLogResponse | undefined = mockEvents;
let mockIsLoading = false;
let mockIsError = false;
let mockError: Error | null = null;
const mockRefetch = vi.fn();
const mockUseAuditLog = vi.fn();

vi.mock("@/hooks/use-audit-log", () => ({
  useAuditLog: (...args: unknown[]) => {
    mockUseAuditLog(...args);
    return {
      data: mockData,
      isLoading: mockIsLoading,
      isError: mockIsError,
      error: mockError,
      refetch: mockRefetch,
    };
  },
}));

vi.mock("@/hooks/use-tenants", () => ({
  useTenants: vi.fn(() => ({ data: mockTenants })),
}));

describe("AuditPage", () => {
  beforeEach(() => {
    mockData = mockEvents;
    mockIsLoading = false;
    mockIsError = false;
    mockError = null;
    mockRefetch.mockClear();
    mockUseAuditLog.mockClear();
    vi.clearAllMocks();
  });

  it("renders page header with Audit Log title", () => {
    render(<AuditPage />);
    expect(screen.getByText("Audit Log")).toBeDefined();
  });

  it("renders event count subtitle", () => {
    render(<AuditPage />);
    expect(screen.getByText(/3 events/)).toBeDefined();
  });

  it("renders event rows with action names", () => {
    render(<AuditPage />);
    expect(screen.getByText("tenant.deactivate")).toBeDefined();
    expect(screen.getByText("entity_type.create")).toBeDefined();
    expect(screen.getByText("training_job.approve")).toBeDefined();
  });

  it("renders kind badges with correct labels", () => {
    render(<AuditPage />);
    expect(screen.getByText("reject")).toBeDefined();
    expect(screen.getByText("create")).toBeDefined();
    expect(screen.getByText("approve")).toBeDefined();
  });

  it("renders actor emails", () => {
    render(<AuditPage />);
    const admins = screen.getAllByText("admin@test.com");
    expect(admins.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("user@test.com")).toBeDefined();
  });

  it("renders target resources", () => {
    render(<AuditPage />);
    expect(screen.getByText("test-tenant")).toBeDefined();
    expect(screen.getByText("vendor_name")).toBeDefined();
    expect(screen.getByText("job-123")).toBeDefined();
  });

  it("shows loading state", () => {
    mockIsLoading = true;
    mockData = undefined;
    render(<AuditPage />);
    expect(screen.getByText("Loading...")).toBeDefined();
  });

  it("shows error state", () => {
    mockIsError = true;
    mockData = undefined;
    mockError = new Error("Failed to fetch audit log: 500");
    render(<AuditPage />);
    expect(screen.getByText("Failed to fetch audit log: 500")).toBeDefined();
  });

  it("shows empty state when no events", () => {
    mockData = { events: [], total: 0, page: 1, per_page: 50 };
    render(<AuditPage />);
    expect(screen.getByText("No events recorded yet")).toBeDefined();
    expect(screen.getByText((content) => content.includes("0 events"))).toBeDefined();
  });

  it("defaults the tenant filter to All Tenants and requests unfiltered events", () => {
    render(<AuditPage />);
    expect(screen.getByRole("combobox", { name: "Filter by tenant" })).toHaveValue("All Tenants");
    expect(mockUseAuditLog).toHaveBeenCalledWith(1, 50, null);
  });

  it("selecting a tenant refetches with that tenant and resets to page 1", async () => {
    render(<AuditPage />);
    const combobox = screen.getByRole("combobox", { name: "Filter by tenant" });
    await userEvent.click(combobox);
    await userEvent.click(screen.getByRole("option", { name: "Tenant B" }));

    expect(mockUseAuditLog).toHaveBeenLastCalledWith(1, 50, "tenant-b");
  });

  it("returning to All Tenants restores the unfiltered request", async () => {
    render(<AuditPage />);
    const combobox = screen.getByRole("combobox", { name: "Filter by tenant" });
    await userEvent.click(combobox);
    await userEvent.click(screen.getByRole("option", { name: "Tenant B" }));
    await userEvent.click(combobox);
    await userEvent.click(screen.getByRole("option", { name: "All Tenants" }));

    expect(mockUseAuditLog).toHaveBeenLastCalledWith(1, 50, null);
  });

  it("shows a tenant-specific empty state and hides pagination when a filtered tenant has no events", async () => {
    mockData = { events: [], total: 0, page: 1, per_page: 50 };
    render(<AuditPage />);
    const combobox = screen.getByRole("combobox", { name: "Filter by tenant" });
    await userEvent.click(combobox);
    await userEvent.click(screen.getByRole("option", { name: "Tenant B" }));

    expect(screen.getByText("No audit events for this tenant")).toBeDefined();
    expect(screen.queryByRole("button", { name: /Previous|Next/ })).toBeNull();
  });

  it("tenant filter narrows options as the admin types", async () => {
    render(<AuditPage />);
    const combobox = screen.getByRole("combobox", { name: "Filter by tenant" });
    await userEvent.click(combobox);
    await userEvent.type(combobox, "Tenant B");

    expect(screen.getByRole("option", { name: "Tenant B" })).toBeDefined();
    expect(screen.queryByRole("option", { name: "Test Tenant" })).toBeNull();
  });
});
