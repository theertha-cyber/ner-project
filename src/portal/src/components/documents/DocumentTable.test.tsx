import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DocumentTable } from "./DocumentTable";

vi.mock("@/hooks/use-toast", () => ({
  useToast: vi.fn(() => ({ toast: vi.fn() })),
}));

vi.mock("@/lib/auth-fetch", () => ({
  authFetch: vi.fn(),
}));

const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const baseDoc = {
  id: "doc-1",
  filename: "test.pdf",
  content_type: "application/pdf",
  file_size: 102400,
  created_at: "2026-06-25T10:00:00Z",
  status: "processed" as const,
};

describe("DocumentTable", () => {
  const defaultProps = {
    data: undefined,
    isLoading: false,
    page: 1,
    perPage: 25,
    onPageChange: vi.fn(),
    currentFilter: "all" as const,
    onFilterChange: vi.fn(),
  };

  it("shows skeleton rows when loading", () => {
    const { container } = render(<DocumentTable {...defaultProps} isLoading={true} />, {
      wrapper: Wrapper,
    });
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThanOrEqual(4);
  });

  it("shows empty state when no documents", () => {
    render(
      <DocumentTable
        {...defaultProps}
        data={{ documents: [], total: 0, page: 1, per_page: 25 }}
      />,
      { wrapper: Wrapper },
    );
    expect(screen.getByText(/No documents yet/)).toBeDefined();
  });

  it("renders column headers", () => {
    render(
      <DocumentTable
        {...defaultProps}
        data={{ documents: [baseDoc], total: 1, page: 1, per_page: 25 }}
      />,
      { wrapper: Wrapper },
    );
    expect(screen.getByText("Filename")).toBeDefined();
    expect(screen.getByText("Type")).toBeDefined();
    expect(screen.getByText("Size")).toBeDefined();
    expect(screen.getByText("Status")).toBeDefined();
    expect(screen.getByText("Created")).toBeDefined();
    expect(screen.getByText("Delete")).toBeDefined();
  });

  it("shows pagination controls when total exceeds per_page", () => {
    render(
      <DocumentTable
        {...defaultProps}
        data={{
          documents: Array.from({ length: 25 }, (_, i) => ({
            ...baseDoc,
            id: `doc-${i}`,
            filename: `doc-${i}.pdf`,
          })),
          total: 30,
          page: 1,
          per_page: 25,
        }}
      />,
      { wrapper: Wrapper },
    );
    expect(screen.getByText("Next")).toBeDefined();
  });

  it("shows 25 items on page 1 of 30 total", () => {
    const items = Array.from({ length: 25 }, (_, i) => ({
      ...baseDoc,
      id: `doc-${i}`,
      filename: `doc-${i}.pdf`,
    }));
    render(
      <DocumentTable
        {...defaultProps}
        data={{ documents: items, total: 30, page: 1, per_page: 25 }}
      />,
      { wrapper: Wrapper },
    );
    const rows = screen.getAllByText(/doc-\d+\.pdf/);
    expect(rows.length).toBe(25);
  });
});
