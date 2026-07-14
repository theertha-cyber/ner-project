import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
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
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";

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

  it("renders the h1 heading in font-display at weight >= 700", async () => {
    render(<TrainingJobsPage />, { wrapper: createWrapper() });
    const heading = screen.getByRole("heading", { level: 1, name: "Training Jobs" });
    expect(heading.className).toContain("font-display");
    expect(heading.className).toMatch(/font-(bold|extrabold|black)/);
  });

  it("renders submit job button", async () => {
    render(<TrainingJobsPage />, { wrapper: createWrapper() });
    expect(screen.getByText("+ Submit job")).toBeDefined();
  });

  it("renders the API-path breadcrumb above the heading", async () => {
    render(<TrainingJobsPage />, { wrapper: createWrapper() });
    expect(screen.getByText("/api/v1/training-jobs")).toBeDefined();
  });

  it("renders filter tabs", async () => {
    render(<TrainingJobsPage />, { wrapper: createWrapper() });
    expect(screen.getByText("all")).toBeDefined();
    expect(screen.getByText("running")).toBeDefined();
  });

  it("auto-selects the first (most recent) job when the list loads with nothing selected", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (String(url).includes("/training-jobs/job-abc")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({ id: "job-abc", tenant_id: "t1", status: "completed" }),
            { status: 200 },
          ),
        );
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({
            items: [{ id: "job-abc", tenant_id: "t1", status: "completed" }],
            total: 1,
            page: 1,
            per_page: 50,
          }),
          { status: 200 },
        ),
      );
    });

    render(<TrainingJobsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith(expect.stringContaining("selected=job-abc"));
    });
  });

  describe("system_admin cross-tenant selection", () => {
    beforeEach(() => {
      vi.mocked(useSearchParams).mockReturnValue(
        new URLSearchParams("selected=job-1") as any,
      );
      vi.mocked(useAuth).mockReturnValue({
        user: {
          role: "system_admin",
          tenantId: "",
          userId: "admin-1",
          email: "admin@x.com",
          tenantSlug: null,
        },
      } as any);

      mockFetch.mockImplementation((url: string) => {
        if (String(url).includes("/training-jobs/job-1")) {
          return Promise.resolve(
            new Response(
              JSON.stringify({
                id: "job-1",
                tenant_id: "tenant-b",
                status: "pending_approval",
              }),
              { status: 200 },
            ),
          );
        }
        return Promise.resolve(
          new Response(
            JSON.stringify({
              items: [{ id: "job-1", tenant_id: "tenant-b", status: "pending_approval" }],
              total: 1,
              page: 1,
              per_page: 50,
            }),
            { status: 200 },
          ),
        );
      });
    });

    it("fetches the selected job's detail using the job's own tenant_id, not the viewer's (empty) tenant", async () => {
      render(<TrainingJobsPage />, { wrapper: createWrapper() });

      await waitFor(() => {
        const detailCall = mockFetch.mock.calls.find(([url]) =>
          String(url).includes("/training-jobs/job-1"),
        );
        expect(detailCall).toBeDefined();
        expect(String(detailCall![0])).toContain("tenant_id=tenant-b");
      });
    });

    it("passes the job's own tenant_id to JobActions so approve/reject target the correct tenant", async () => {
      render(<TrainingJobsPage />, { wrapper: createWrapper() });

      expect(await screen.findByText("Approve & queue")).toBeDefined();

      mockFetch.mockClear();
      mockFetch.mockResolvedValue(
        new Response(JSON.stringify({ id: "job-1", status: "queued" }), { status: 200 }),
      );
      fireEvent.click(screen.getByText("Approve & queue"));

      await waitFor(() => expect(mockFetch).toHaveBeenCalled());
      const approveCall = mockFetch.mock.calls.find(([url]) =>
        String(url).includes("/approve"),
      );
      expect(approveCall).toBeDefined();
      expect(String(approveCall![0])).toContain("tenant_id=tenant-b");
    });
  });
});
