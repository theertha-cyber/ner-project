import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import UsersPage from "./page";

const mockAuthFetch = vi.fn();
vi.mock("@/lib/auth-fetch", () => ({
  authFetch: (...args: unknown[]) => mockAuthFetch(...args),
}));

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

describe("UsersPage (Tenant Admin onboarding)", () => {
  beforeEach(() => {
    mockAuthFetch.mockReset();
    mockAuthFetch.mockResolvedValue(jsonResponse({ users: [] }));
  });

  it("shows a 'Create User' button (not 'Add User')", async () => {
    render(<UsersPage />);
    await waitFor(() => expect(mockAuthFetch).toHaveBeenCalled());
    expect(screen.getByRole("button", { name: "Create User" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add User" })).not.toBeInTheDocument();
  });

  it("opening the form shows the 'New User' heading with no tenant label", async () => {
    render(<UsersPage />);
    await waitFor(() => expect(mockAuthFetch).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: "Create User" }));

    expect(screen.getByText("New User")).toBeInTheDocument();
    expect(screen.queryByText(/Tenant:/)).not.toBeInTheDocument();
  });

  it("submits to POST /api/v1/users and prepends the created user to the list", async () => {
    render(<UsersPage />);
    await waitFor(() => expect(mockAuthFetch).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: "Create User" }));

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "new@acme.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "StrongPass1" } });

    mockAuthFetch.mockResolvedValueOnce(
      jsonResponse({ user: { id: "u-1", email: "new@acme.com", role: "annotator", status: "active", created_at: "2026-01-01" } }, 201)
    );

    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(screen.getByText("new@acme.com")).toBeInTheDocument());
    const call = mockAuthFetch.mock.calls.find(
      (c) => String(c[0]).endsWith("/api/v1/users") && (c[1] as { method?: string })?.method === "POST"
    );
    expect(call).toBeTruthy();
  });

  it("surfaces a 429 quota error inline without adding a row", async () => {
    render(<UsersPage />);
    await waitFor(() => expect(mockAuthFetch).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: "Create User" }));
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "over@acme.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "StrongPass1" } });

    mockAuthFetch.mockResolvedValueOnce(jsonResponse({ error: { message: "limit reached" } }, 429));

    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(screen.getByText(/Quota exceeded/)).toBeInTheDocument());
    expect(screen.queryByText("over@acme.com")).not.toBeInTheDocument();
  });
});
