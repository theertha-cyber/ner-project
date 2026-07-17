import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import AuditPage from "./page";
import type { AuditLogResponse } from "@/hooks/use-audit-log";

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

let mockData: AuditLogResponse | undefined = mockEvents;
let mockIsLoading = false;
let mockIsError = false;
let mockError: Error | null = null;
const mockRefetch = vi.fn();

vi.mock("@/hooks/use-audit-log", () => ({
  useAuditLog: vi.fn(() => ({
    data: mockData,
    isLoading: mockIsLoading,
    isError: mockIsError,
    error: mockError,
    refetch: mockRefetch,
  })),
}));

describe("AuditPage", () => {
  beforeEach(() => {
    mockData = mockEvents;
    mockIsLoading = false;
    mockIsError = false;
    mockError = null;
    mockRefetch.mockClear();
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
});
