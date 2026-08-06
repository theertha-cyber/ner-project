import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import TenantDetailPage from "./page";

const mockAuthFetch = vi.fn();
vi.mock("@/lib/auth-fetch", () => ({
  authFetch: (...args: unknown[]) => mockAuthFetch(...args),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

const TENANT = {
  id: "tid-123",
  name: "Acme Corp",
  slug: "acme-corp",
  status: "active",
  max_users: 10,
  max_documents: 1000,
  max_storage_gb: 5,
  max_model_versions: 10,
  user_count: 3,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("TenantDetailPage (System Admin cross-tenant onboarding)", () => {
  beforeEach(() => {
    mockAuthFetch.mockReset();
    mockAuthFetch.mockImplementation((url: string) => {
      if (String(url).endsWith(`/api/v1/admin/tenants/${TENANT.id}`)) {
        return Promise.resolve(jsonResponse({ tenant: TENANT }));
      }
      if (String(url).endsWith(`/api/v1/admin/tenants/${TENANT.id}/users`)) {
        return Promise.resolve(jsonResponse({ users: [] }));
      }
      return Promise.resolve(jsonResponse({}));
    });
  });

  it("shows Edit Quotas, Deactivate Tenant, and Create User buttons", async () => {
    render(<TenantDetailPage params={{ id: TENANT.id }} />);
    await waitFor(() => expect(screen.getByText("Acme Corp")).toBeInTheDocument());

    expect(screen.getByRole("button", { name: "Edit Quotas" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Deactivate Tenant" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create User" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add User" })).not.toBeInTheDocument();
  });

  it("creates a user, showing the tenant label, posting to the tenant-scoped admin endpoint, and updating the list + quota without reload", async () => {
    render(<TenantDetailPage params={{ id: TENANT.id }} />);
    await waitFor(() => expect(screen.getByText("Acme Corp")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Create User" }));
    expect(screen.getByText(/Acme Corp \(acme-corp\)/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "biz@acme-corp.io" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "StrongPass1" } });

    mockAuthFetch.mockResolvedValueOnce(
      jsonResponse({ user: { id: "u-9", email: "biz@acme-corp.io", role: "business_user", status: "active" } }, 201)
    );

    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(screen.getByText("biz@acme-corp.io")).toBeInTheDocument());

    const createCall = mockAuthFetch.mock.calls.find(
      (c) => String(c[0]).endsWith(`/api/v1/admin/tenants/${TENANT.id}/users`) && (c[1] as { method?: string })?.method === "POST"
    );
    expect(createCall).toBeTruthy();

    // quota indicator increments from 3 to 4
    await waitFor(() => expect(screen.getByText("4 / 10")).toBeInTheDocument());
  });

  it("surfaces a 429 quota-exceeded error without adding a row", async () => {
    render(<TenantDetailPage params={{ id: TENANT.id }} />);
    await waitFor(() => expect(screen.getByText("Acme Corp")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Create User" }));
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "over@acme-corp.io" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "StrongPass1" } });

    mockAuthFetch.mockResolvedValueOnce(jsonResponse({ error: { message: "limit reached" } }, 429));

    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(screen.getByText(/Quota exceeded/)).toBeInTheDocument());
    expect(screen.queryByText("over@acme-corp.io")).not.toBeInTheDocument();
  });

  it("surfaces a 403 deactivated-tenant error without adding a row", async () => {
    render(<TenantDetailPage params={{ id: TENANT.id }} />);
    await waitFor(() => expect(screen.getByText("Acme Corp")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Create User" }));
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "late@acme-corp.io" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "StrongPass1" } });

    mockAuthFetch.mockResolvedValueOnce(jsonResponse({ error: { message: "tenant is deactivated" } }, 403));

    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(screen.getByText(/Tenant deactivated/)).toBeInTheDocument());
    expect(screen.queryByText("late@acme-corp.io")).not.toBeInTheDocument();
  });
});
