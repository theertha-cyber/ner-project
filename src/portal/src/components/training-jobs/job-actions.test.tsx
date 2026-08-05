import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { JobActions } from "./job-actions";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(),
}));

import { useAuth } from "@/lib/auth";

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("JobActions", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    vi.mocked(useAuth).mockReturnValue({
      user: { role: "tenant_admin", tenantId: "t1", userId: "u1", email: "a@b.com", tenantSlug: null },
      getAccessToken: vi.fn(),
      setAccessToken: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
    });
  });

  it("shows cancel button for tenant_admin on pending_approval job", () => {
    render(
      <JobActions jobId="job-1" status="pending_approval" tenantId="t1" />,
      { wrapper: createWrapper() },
    );
    expect(screen.getByText("Cancel")).toBeDefined();
  });

  it("hides cancel button for system_admin", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: { role: "system_admin", tenantId: "", userId: "u1", email: "a@b.com", tenantSlug: null },
      getAccessToken: vi.fn(),
      setAccessToken: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
    });

    const { container } = render(
      <JobActions jobId="job-1" status="pending_approval" tenantId="t1" />,
      { wrapper: createWrapper() },
    );
    expect(container.textContent).not.toContain("Cancel");
  });

  it("shows approve and reject buttons for system_admin", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: { role: "system_admin", tenantId: "", userId: "u1", email: "a@b.com", tenantSlug: null },
      getAccessToken: vi.fn(),
      setAccessToken: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <JobActions jobId="job-1" status="pending_approval" tenantId="t1" />,
      { wrapper: createWrapper() },
    );
    expect(screen.getByText("Approve")).toBeDefined();
    expect(screen.getByText("Reject")).toBeDefined();
  });

  it("opens a hyperparameter form when Approve is clicked, without approving immediately", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: { role: "system_admin", tenantId: "", userId: "u1", email: "a@b.com", tenantSlug: null },
      getAccessToken: vi.fn(),
      setAccessToken: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <JobActions jobId="job-1" status="pending_approval" tenantId="t1" />,
      { wrapper: createWrapper() },
    );

    fireEvent.click(screen.getByText("Approve"));

    expect(screen.getByText("Learning Rate")).toBeDefined();
    expect(screen.getByText(/Confirm approve & queue/)).toBeDefined();
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("disables the approve form submit until all fields are valid", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: { role: "system_admin", tenantId: "", userId: "u1", email: "a@b.com", tenantSlug: null },
      getAccessToken: vi.fn(),
      setAccessToken: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <JobActions jobId="job-1" status="pending_approval" tenantId="t1" />,
      { wrapper: createWrapper() },
    );

    fireEvent.click(screen.getByText("Approve"));
    const submitBtn = screen.getByText(/Confirm approve & queue/);
    expect(submitBtn).not.toBeDisabled();

    const learningRateInput = screen.getByDisplayValue("2e-5");
    fireEvent.change(learningRateInput, { target: { value: "not-a-number" } });
    expect(submitBtn).toBeDisabled();
  });

  it("submits the entered hyperparameters to the approve endpoint", async () => {
    vi.mocked(useAuth).mockReturnValue({
      user: { role: "system_admin", tenantId: "", userId: "u1", email: "a@b.com", tenantSlug: null },
      getAccessToken: vi.fn(),
      setAccessToken: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
    });
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ id: "job-1", status: "queued" }), { status: 200 }),
    );

    render(
      <JobActions jobId="job-1" status="pending_approval" tenantId="t1" />,
      { wrapper: createWrapper() },
    );

    fireEvent.click(screen.getByText("Approve"));
    fireEvent.click(screen.getByText(/Confirm approve & queue/));

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    const [url, options] = mockFetch.mock.calls[0];
    expect(String(url)).toContain("/approve");
    expect(JSON.parse(options.body)).toEqual({
      learning_rate: 2e-5,
      num_epochs: 3,
      batch_size: 8,
      max_seq_length: 128,
    });
  });

  it("surfaces a backend validation error on the approve form and keeps it open", async () => {
    vi.mocked(useAuth).mockReturnValue({
      user: { role: "system_admin", tenantId: "", userId: "u1", email: "a@b.com", tenantSlug: null },
      getAccessToken: vi.fn(),
      setAccessToken: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
    });
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ detail: "num_epochs must be between 1 and 50" }), { status: 422 }),
    );

    render(
      <JobActions jobId="job-1" status="pending_approval" tenantId="t1" />,
      { wrapper: createWrapper() },
    );

    fireEvent.click(screen.getByText("Approve"));
    fireEvent.click(screen.getByText(/Confirm approve & queue/));

    await waitFor(() => {
      expect(screen.getByText("num_epochs must be between 1 and 50")).toBeDefined();
    });
    expect(screen.getByText("Learning Rate")).toBeDefined();
  });

  it("hides approve/reject for non-pending jobs", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: { role: "system_admin", tenantId: "", userId: "u1", email: "a@b.com", tenantSlug: null },
      getAccessToken: vi.fn(),
      setAccessToken: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
    });

    const { container } = render(
      <JobActions jobId="job-1" status="running" tenantId="t1" />,
      { wrapper: createWrapper() },
    );
    expect(container.textContent).not.toContain("Approve");
    expect(container.textContent).not.toContain("Reject");
  });

  it("hides all buttons for tenant_admin on non-cancellable status", () => {
    const { container } = render(
      <JobActions jobId="job-1" status="completed" tenantId="t1" />,
      { wrapper: createWrapper() },
    );
    expect(container.textContent).toBe("");
  });

  it("calls cancel on confirmation", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ id: "job-1", status: "cancelled" }), { status: 200 }),
    );

    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(
      <JobActions jobId="job-1" status="pending_approval" tenantId="t1" />,
      { wrapper: createWrapper() },
    );

    fireEvent.click(screen.getByText("Cancel"));
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalled();
    });
  });

  it("does not call cancel when dialog is dismissed", () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);

    render(
      <JobActions jobId="job-1" status="pending_approval" tenantId="t1" />,
      { wrapper: createWrapper() },
    );

    fireEvent.click(screen.getByText("Cancel"));
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("approves using the job's own tenant_id, not the viewer's tenant, when they differ", async () => {
    vi.mocked(useAuth).mockReturnValue({
      user: { role: "system_admin", tenantId: "", userId: "u1", email: "a@b.com", tenantSlug: null },
      getAccessToken: vi.fn(),
      setAccessToken: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
    });
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ id: "job-1", status: "queued" }), { status: 200 }),
    );

    render(
      <JobActions jobId="job-1" status="pending_approval" tenantId="tenant-b-owns-this-job" />,
      { wrapper: createWrapper() },
    );

    fireEvent.click(screen.getByText("Approve"));
    fireEvent.click(screen.getByText(/Confirm approve & queue/));

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    const callUrl = String(mockFetch.mock.calls[0][0]);
    expect(callUrl).toContain("tenant_id=tenant-b-owns-this-job");
  });
});
