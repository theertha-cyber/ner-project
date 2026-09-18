import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import NewTenantPage from "./page";

const mockAuthFetch = vi.fn();
vi.mock("@/lib/auth-fetch", () => ({
  authFetch: (...args: unknown[]) => mockAuthFetch(...args),
}));

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function fillRequiredFields() {
  // The form's labels are not programmatically associated with their inputs
  // (no `htmlFor`/`id` pair) — a pre-existing gap in this page, unrelated to
  // this task, so these fields are found by placeholder/order instead of
  // `getByLabelText`.
  fireEvent.change(screen.getAllByRole("textbox")[0], { target: { value: "Residency Co" } });
  fireEvent.change(screen.getByPlaceholderText("admin@example.com"), { target: { value: "admin@residency.test" } });
  fireEvent.change(screen.getByPlaceholderText("Min 8 characters"), { target: { value: "StrongPass1" } });
}

// Scenario #76 (admin-console) — task 13.7.
describe("NewTenantPage (System Admin creates a tenant-owned tenant)", () => {
  beforeEach(() => {
    mockAuthFetch.mockReset();
    mockPush.mockReset();
  });

  it("defaults to Platform-hosted", () => {
    render(<NewTenantPage />);
    expect(screen.getByRole("radio", { name: /Platform-hosted/ })).toBeChecked();
    expect(screen.getByRole("radio", { name: /Tenant-owned PostgreSQL/ })).not.toBeChecked();
  });

  it("submits data_plane_mode: platform by default", async () => {
    mockAuthFetch.mockResolvedValue(jsonResponse({ tenant: { id: "tid-1" } }, 201));
    render(<NewTenantPage />);
    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: "Create Tenant" }));

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/admin/tenants/tid-1"));
    const [, init] = mockAuthFetch.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(String(init.body));
    expect(body.data_plane_mode).toBe("platform");
  });

  it("selects tenant_owned and submits data_plane_mode: tenant_owned", async () => {
    mockAuthFetch.mockResolvedValue(jsonResponse({ tenant: { id: "tid-2" } }, 201));
    render(<NewTenantPage />);
    fillRequiredFields();
    fireEvent.click(screen.getByRole("radio", { name: /Tenant-owned PostgreSQL/ }));
    expect(screen.getByRole("radio", { name: /Tenant-owned PostgreSQL/ })).toBeChecked();

    fireEvent.click(screen.getByRole("button", { name: "Create Tenant" }));

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/admin/tenants/tid-2"));
    const [, init] = mockAuthFetch.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(String(init.body));
    expect(body.data_plane_mode).toBe("tenant_owned");
  });
});
