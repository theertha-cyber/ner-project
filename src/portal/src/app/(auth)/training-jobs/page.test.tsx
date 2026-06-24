import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const mockReplace = vi.fn();

vi.mock("next/navigation", () => ({
  useSearchParams: vi.fn(() => new URLSearchParams()),
  useRouter: vi.fn(() => ({ replace: mockReplace })),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(() => ({
    user: { role: "tenant_admin", tenantId: "t1", userId: "u1", email: "a@b.com", tenantSlug: null },
  })),
}));

import TrainingJobsPage from "./page";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("TrainingJobsPage", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockReplace.mockReset();
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ items: [], total: 0, page: 1, per_page: 50 }), {
        status: 200,
      }),
    );
  });

  it("renders the page header", async () => {
    render(<TrainingJobsPage />, { wrapper: createWrapper() });
    expect(screen.getByText("Training Jobs")).toBeDefined();
  });

  it("renders submit job button", async () => {
    render(<TrainingJobsPage />, { wrapper: createWrapper() });
    expect(screen.getByText("+ Submit Job")).toBeDefined();
  });

  it("renders filter tabs", async () => {
    render(<TrainingJobsPage />, { wrapper: createWrapper() });
    expect(screen.getByText("All")).toBeDefined();
    expect(screen.getByText("Running")).toBeDefined();
  });
});
