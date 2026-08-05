import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "@/hooks";
import { ModelActions } from "./model-actions";
import type { ModelVersion } from "@/types/model-registry";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

const mockUser = { role: "tenant_admin", tenantId: "t1", userId: "u1", email: "a@b.com", tenantSlug: "acme" };

vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(() => ({ user: mockUser })),
}));

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={qc}>
        <ToastProvider>{children}</ToastProvider>
      </QueryClientProvider>
    );
  };
}

const completedModel: ModelVersion = {
  id: "mv-3",
  version_number: 3,
  status: "completed",
  training_job_id: "job-1",
  created_at: "2026-06-23T10:00:00Z",
  metrics: null,
  mlflow_run_id: null,
  mlflow_run_url: null,
  artifact_path: null,
  run_number: 3,
  run_name: "run-003-20260623",
};

describe("ModelActions", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValue(new Response(JSON.stringify(completedModel), { status: 200 }));
    mockUser.role = "tenant_admin";
  });

  it("renders nothing without a model version", () => {
    const { container } = render(<ModelActions model={null} />, { wrapper: createWrapper() });
    expect(container.textContent).toBe("");
  });

  it("hides actions for non tenant_admin roles", () => {
    mockUser.role = "system_admin";
    const { container } = render(<ModelActions model={completedModel} />, { wrapper: createWrapper() });
    expect(container.textContent).toBe("");
  });

  it("hides actions for the base model", () => {
    const { container } = render(
      <ModelActions model={{ ...completedModel, version_number: 0 }} />,
      { wrapper: createWrapper() },
    );
    expect(container.textContent).toBe("");
  });

  it("promotes a completed model version", async () => {
    render(<ModelActions model={completedModel} />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByText("Promote"));
    await waitFor(() => {
      expect(String(mockFetch.mock.calls[0][0])).toContain("/api/v1/models/mv-3/promote");
    });
  });

  it("demotes a promoted model version", async () => {
    render(<ModelActions model={{ ...completedModel, status: "promoted" }} />, { wrapper: createWrapper() });
    expect(screen.queryByText("Promote")).toBeNull();
    fireEvent.click(screen.getByText("Demote"));
    await waitFor(() => {
      expect(String(mockFetch.mock.calls[0][0])).toContain("/api/v1/models/mv-3/demote");
    });
  });

  it("triggers warmup for any non-base version", async () => {
    render(<ModelActions model={completedModel} />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByText("Warmup"));
    await waitFor(() => {
      expect(String(mockFetch.mock.calls[0][0])).toContain("/api/v1/models/mv-3/warmup");
    });
  });
});
