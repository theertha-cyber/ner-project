import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ModelDetailPanel } from "./ModelDetailPanel";
import type { ModelVersion } from "@/types/model-registry";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/hooks", () => ({
  useToast: vi.fn(),
}));

import { useAuth } from "@/lib/auth";
import { useToast } from "@/hooks";

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

const completedModel: ModelVersion = {
  id: "mv-3",
  version_number: 3,
  status: "completed",
  training_job_id: "tj-1",
  created_at: "2026-06-20T10:00:00Z",
  metrics: { eval_f1: 0.89, eval_precision: 0.91, eval_recall: 0.87, eval_loss: 0.12 },
  mlflow_run_id: "run-abc",
  mlflow_run_url: "http://mlflow:5000/#/experiments/1/runs/abc123",
  artifact_path: "tenants/acme-corp/models/v3",
};

const mockToast = vi.fn();

describe("ModelDetailPanel", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockToast.mockReset();
    vi.mocked(useAuth).mockReturnValue({
      user: { role: "tenant_admin", tenantId: "t1", userId: "u1", email: "a@b.com", tenantSlug: "acme" },
      getAccessToken: vi.fn(),
      setAccessToken: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
    });
    vi.mocked(useToast).mockReturnValue({ toast: mockToast });
  });

  it("shows empty state when no model selected", () => {
    render(<ModelDetailPanel model={null} role="tenant_admin" />, { wrapper: createWrapper() });
    expect(screen.getByText("Select a model version to view details")).toBeDefined();
  });

  it("renders metrics grid", () => {
    render(<ModelDetailPanel model={completedModel} role="tenant_admin" />, { wrapper: createWrapper() });
    expect(screen.getByText("F1")).toBeDefined();
    expect(screen.getByText("0.8900")).toBeDefined();
    expect(screen.getByText("0.9100")).toBeDefined();
    expect(screen.getByText("0.8700")).toBeDefined();
    expect(screen.getByText("0.1200")).toBeDefined();
  });

  it("renders MLflow link", () => {
    render(<ModelDetailPanel model={completedModel} role="tenant_admin" />, { wrapper: createWrapper() });
    const link = screen.getByText("View in MLflow");
    expect(link).toBeDefined();
    expect(link.getAttribute("href")).toBe("http://mlflow:5000/#/experiments/1/runs/abc123");
    expect(link.getAttribute("target")).toBe("_blank");
  });

  it("renders artifact path", () => {
    render(<ModelDetailPanel model={completedModel} role="tenant_admin" />, { wrapper: createWrapper() });
    expect(screen.getByText("tenants/acme-corp/models/v3")).toBeDefined();
  });

  it("renders per-entity metrics accordion", () => {
    const modelWithEntityMetrics: ModelVersion = {
      ...completedModel,
      metrics: {
        eval_f1: 0.89, eval_precision: 0.91, eval_recall: 0.87, eval_loss: 0.12,
        vendor_name_f1: 0.92,
        invoice_date_f1: 0.85,
      },
    };
    render(<ModelDetailPanel model={modelWithEntityMetrics} role="tenant_admin" />, { wrapper: createWrapper() });
    expect(screen.getByText("Per-Entity Metrics")).toBeDefined();
    expect(screen.getByText("vendor_name_f1")).toBeDefined();
    expect(screen.getByText("invoice_date_f1")).toBeDefined();
  });

  it("shows Promote button for tenant_admin on completed model", () => {
    render(<ModelDetailPanel model={completedModel} role="tenant_admin" />, { wrapper: createWrapper() });
    expect(screen.getByText("Promote")).toBeDefined();
  });

  it("hides Promote button for business_user", () => {
    render(<ModelDetailPanel model={completedModel} role="business_user" />, { wrapper: createWrapper() });
    expect(screen.queryByText("Promote")).toBeNull();
  });

  it("shows Demote button only for promoted model", () => {
    const promoted: ModelVersion = { ...completedModel, status: "promoted" };
    render(<ModelDetailPanel model={promoted} role="tenant_admin" />, { wrapper: createWrapper() });
    expect(screen.getByText("Demote")).toBeDefined();
    expect(screen.queryByText("Promote")).toBeNull();
  });

  it("hides Demote button for non-promoted model", () => {
    render(<ModelDetailPanel model={completedModel} role="tenant_admin" />, { wrapper: createWrapper() });
    expect(screen.queryByText("Demote")).toBeNull();
  });

  it("shows Warmup button for tenant_admin", () => {
    render(<ModelDetailPanel model={completedModel} role="tenant_admin" />, { wrapper: createWrapper() });
    expect(screen.getByText("Warmup")).toBeDefined();
  });

  it("calls promote mutation and shows success toast", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ ...completedModel, status: "promoted" }), { status: 200 }),
    );
    render(<ModelDetailPanel model={completedModel} role="tenant_admin" />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByText("Promote"));
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/models/mv-3/promote"),
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("calls demote mutation", async () => {
    const promoted: ModelVersion = { ...completedModel, status: "promoted" };
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ ...promoted, status: "completed" }), { status: 200 }),
    );
    render(<ModelDetailPanel model={promoted} role="tenant_admin" />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByText("Demote"));
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/models/mv-3/demote"),
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("calls warmup mutation", async () => {
    mockFetch.mockResolvedValue(new Response(null, { status: 200 }));
    render(<ModelDetailPanel model={completedModel} role="tenant_admin" />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByText("Warmup"));
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/models/mv-3/warmup"),
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("shows error toast on promote failure", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ detail: "Already promoted" }), { status: 422 }),
    );
    render(<ModelDetailPanel model={completedModel} role="tenant_admin" />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByText("Promote"));
    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith("Already promoted", "bad");
    });
  });

  describe("base model (version 0)", () => {
    const baseModel = {
      id: "v0-base",
      version_number: 0,
      status: "promoted" as const,
      training_job_id: "",
      created_at: "",
      metrics: null,
      mlflow_run_id: null,
      mlflow_run_url: null,
      artifact_path: null,
    };

    it("renders 'Base Model' heading", () => {
      render(<ModelDetailPanel model={baseModel} role="tenant_admin" />, { wrapper: createWrapper() });
      expect(screen.getByText("Base Model")).toBeDefined();
    });

    it("shows dslim/bert-base-NER model name", () => {
      render(<ModelDetailPanel model={baseModel} role="tenant_admin" />, { wrapper: createWrapper() });
      expect(screen.getByText("dslim/bert-base-NER")).toBeDefined();
    });

    it("shows CoNLL labels PER, ORG, LOC, MISC", () => {
      render(<ModelDetailPanel model={baseModel} role="tenant_admin" />, { wrapper: createWrapper() });
      expect(screen.getByText("PER")).toBeDefined();
      expect(screen.getByText("ORG")).toBeDefined();
      expect(screen.getByText("LOC")).toBeDefined();
      expect(screen.getByText("MISC")).toBeDefined();
    });

    it("hides Promote, Demote, Warmup buttons for tenant_admin", () => {
      render(<ModelDetailPanel model={baseModel} role="tenant_admin" />, { wrapper: createWrapper() });
      expect(screen.queryByText("Promote")).toBeNull();
      expect(screen.queryByText("Demote")).toBeNull();
      expect(screen.queryByText("Warmup")).toBeNull();
    });
  });
});
