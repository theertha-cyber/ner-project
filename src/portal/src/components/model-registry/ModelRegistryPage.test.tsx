import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ModelRegistryPage } from "./ModelRegistryPage";

vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/hooks/use-model-versions", () => ({
  useModelVersions: vi.fn(),
}));

vi.mock("@/hooks", () => ({
  useToast: vi.fn(),
}));

vi.mock("@/hooks/use-promote-model", () => ({
  usePromoteModel: vi.fn(),
}));

vi.mock("@/hooks/use-demote-model", () => ({
  useDemoteModel: vi.fn(),
}));

vi.mock("@/hooks/use-warmup-model", () => ({
  useWarmupModel: vi.fn(),
}));

import { useAuth } from "@/lib/auth";
import { useModelVersions } from "@/hooks/use-model-versions";
import { useToast } from "@/hooks";
import { usePromoteModel } from "@/hooks/use-promote-model";
import { useDemoteModel } from "@/hooks/use-demote-model";
import { useWarmupModel } from "@/hooks/use-warmup-model";

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

const noopMutation = { mutate: vi.fn(), isPending: false };

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue({
    user: { role: "tenant_admin", tenantId: "t1", userId: "u1", email: "a@b.com", tenantSlug: "acme" },
    getAccessToken: vi.fn(),
    setAccessToken: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
  });
  vi.mocked(useToast).mockReturnValue({ toast: vi.fn() });
  vi.mocked(usePromoteModel).mockReturnValue(noopMutation as ReturnType<typeof usePromoteModel>);
  vi.mocked(useDemoteModel).mockReturnValue(noopMutation as ReturnType<typeof useDemoteModel>);
  vi.mocked(useWarmupModel).mockReturnValue(noopMutation as ReturnType<typeof useWarmupModel>);
});

describe("ModelRegistryPage", () => {
  it("renders header", () => {
    vi.mocked(useModelVersions).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      activeModel: null,
      isActiveLoading: false,
    });
    render(<ModelRegistryPage />, { wrapper: createWrapper() });
    expect(screen.getByText("Model Registry")).toBeDefined();
    expect(screen.getByText("GET /api/v1/models")).toBeDefined();
  });

  it("renders skeleton cards while loading", () => {
    vi.mocked(useModelVersions).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      activeModel: null,
      isActiveLoading: true,
    });
    const { container } = render(<ModelRegistryPage />, { wrapper: createWrapper() });
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBe(3);
  });

  it("always shows base model card even with no fine-tuned models", () => {
    vi.mocked(useModelVersions).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      activeModel: null,
      isActiveLoading: false,
    });
    render(<ModelRegistryPage />, { wrapper: createWrapper() });
    expect(screen.getByText("Base Model")).toBeDefined();
  });

  it("shows base model as promoted when activeModel is version 0", () => {
    vi.mocked(useModelVersions).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      activeModel: {
        id: "v0", version_number: 0, status: "promoted",
        training_job_id: "", created_at: "",
        metrics: null, mlflow_run_id: null, mlflow_run_url: null, artifact_path: null,
      },
      isActiveLoading: false,
    });
    render(<ModelRegistryPage />, { wrapper: createWrapper() });
    expect(screen.getByText("Base Model")).toBeDefined();
    expect(screen.getByText("promoted")).toBeDefined();
  });

  it("renders fine-tuned model cards alongside base model", () => {
    vi.mocked(useModelVersions).mockReturnValue({
      data: [
        {
          id: "mv-1", version_number: 1, status: "archived", training_job_id: "tj-1",
          created_at: "2026-06-01T00:00:00Z", metrics: null,
          mlflow_run_id: null, mlflow_run_url: null, artifact_path: null,
        },
        {
          id: "mv-2", version_number: 2, status: "promoted", training_job_id: "tj-2",
          created_at: "2026-06-10T00:00:00Z",
          metrics: { eval_f1: 0.88, eval_precision: 0.90, eval_recall: 0.86, eval_loss: 0.13 },
          mlflow_run_id: null, mlflow_run_url: null, artifact_path: null,
        },
      ],
      isLoading: false,
      isError: false,
      activeModel: null,
      isActiveLoading: false,
    });
    render(<ModelRegistryPage />, { wrapper: createWrapper() });
    expect(screen.getByText("v1")).toBeDefined();
    expect(screen.getByText("v2")).toBeDefined();
    expect(screen.getByText("Base Model")).toBeDefined();
  });

  it("selecting a fine-tuned card updates the detail panel", () => {
    vi.mocked(useModelVersions).mockReturnValue({
      data: [
        {
          id: "mv-3", version_number: 3, status: "completed", training_job_id: "tj-3",
          created_at: "2026-06-20T00:00:00Z",
          metrics: { eval_f1: 0.89, eval_precision: 0.91, eval_recall: 0.87, eval_loss: 0.12 },
          mlflow_run_id: null, mlflow_run_url: null, artifact_path: null,
        },
      ],
      isLoading: false,
      isError: false,
      activeModel: null,
      isActiveLoading: false,
    });
    render(<ModelRegistryPage />, { wrapper: createWrapper() });

    expect(screen.getByText("Select a model version to view details")).toBeDefined();

    fireEvent.click(screen.getByText("v3"));
    expect(screen.queryByText("Select a model version to view details")).toBeNull();
    expect(screen.getByText("0.8900")).toBeDefined();
  });

  it("selecting base model card shows base model detail", () => {
    vi.mocked(useModelVersions).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      activeModel: null,
      isActiveLoading: false,
    });
    render(<ModelRegistryPage />, { wrapper: createWrapper() });

    fireEvent.click(screen.getByText("Base Model"));
    expect(screen.getAllByText("dslim/bert-base-NER").length).toBeGreaterThan(0);
    expect(screen.getByText("PER")).toBeDefined();
  });
});
