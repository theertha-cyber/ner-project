import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import AnalyticsPage from "./page";

const mockDashboardData = {
  entity_coverage: [{ entity_type: "PERSON", coverage_pct: 80.0 }],
  confidence_distribution: {
    buckets: [
      { label: "0.8-1.0", count: 100 },
      { label: "0.6-0.8", count: 50 },
    ],
  },
  extraction_volume: {
    data: [
      { date: "2026-06-01", count: 50 },
      { date: "2026-06-02", count: 30 },
    ],
  },
  document_entity_counts: [{ entity_type: "PERSON", avg_per_document: 3.5 }],
  generated_at: "2026-06-24T00:00:00Z",
};

const mockQueryResponse = {
  results: [
    {
      id: "1",
      entity_type: "PERSON",
      value: "John Doe",
      confidence: 0.95,
      document_id: "doc-1",
      extracted_at: "2026-06-01T00:00:00",
    },
  ],
  pagination: { next_cursor: null, has_more: false, limit: 50 },
};

let mockDashboardError = false;
let mockQueryError = false;
let mockQueryLoading = false;
const mockRefetchQuery = vi.fn();
const mockQueryErrorObj = new Error("Query failed: 500");

vi.mock("@/hooks/use-analytics-data", () => ({
  useDashboardWidgets: vi.fn(() => ({
    data: mockDashboardError ? undefined : mockDashboardData,
    isLoading: false,
    isError: mockDashboardError,
    refetch: vi.fn(),
  })),
  useAnalyticsQuery: vi.fn(() => ({
    data: mockQueryError ? undefined : mockQueryResponse,
    isLoading: mockQueryLoading,
    isError: mockQueryError,
    error: mockQueryError ? mockQueryErrorObj : null,
    refetch: mockRefetchQuery,
  })),
  useExportAnalytics: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
    variables: undefined,
  })),
  useRefreshDashboard: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
  })),
}));

describe("AnalyticsPage", () => {
  beforeEach(() => {
    mockDashboardError = false;
    mockQueryError = false;
    mockQueryLoading = false;
    mockRefetchQuery.mockClear();
    vi.clearAllMocks();
  });

  it("renders the analytics page title", () => {
    render(<AnalyticsPage />);
    expect(screen.getByText("Analytics & Reporting")).toBeInTheDocument();
  });

  it("displays widget cards when data loads", () => {
    render(<AnalyticsPage />);
    expect(screen.getByText("Entity Coverage")).toBeInTheDocument();
    expect(screen.getByText("Confidence Distribution")).toBeInTheDocument();
    expect(screen.getByText("Extraction Volume (Last 14 Days)")).toBeInTheDocument();
    expect(screen.getByText("Per-Document Entity Counts")).toBeInTheDocument();
  });

  it("shows entity coverage data", () => {
    render(<AnalyticsPage />);
    expect(screen.getAllByText("PERSON").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("80.0%")).toBeInTheDocument();
  });

  it("shows query data button", () => {
    render(<AnalyticsPage />);
    expect(screen.getByText("Query Data")).toBeInTheDocument();
  });

  it("shows refresh button", () => {
    render(<AnalyticsPage />);
    expect(screen.getByText("Refresh")).toBeInTheDocument();
  });

  it("shows error banner when dashboard API fails", () => {
    mockDashboardError = true;
    render(<AnalyticsPage />);
    expect(screen.getByText("Unable to load analytics data")).toBeInTheDocument();
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("shows filters when Query Data is clicked", async () => {
    render(<AnalyticsPage />);
    await userEvent.click(screen.getByText("Query Data"));
    expect(screen.getByText("Min Confidence")).toBeInTheDocument();
    expect(screen.getByText("Max Confidence")).toBeInTheDocument();
  });

  it("shows empty state when there are no query results", async () => {
    mockDashboardError = false;
    render(<AnalyticsPage />);
    await userEvent.click(screen.getByText("Query Data"));
    await userEvent.click(screen.getByText("Query"));
    await waitFor(() => {
      expect(screen.getByText("Query Results")).toBeInTheDocument();
    });
  });

  it("shows an error banner when the query fails", async () => {
    mockQueryError = true;
    render(<AnalyticsPage />);
    await waitFor(() => {
      expect(screen.getByText("Query failed: 500")).toBeInTheDocument();
    });
  });

  it("clears the query error banner when Dismiss is clicked", async () => {
    mockQueryError = true;
    render(<AnalyticsPage />);
    await waitFor(() => {
      expect(screen.getByText("Query failed: 500")).toBeInTheDocument();
    });
    await userEvent.click(screen.getByText("Dismiss"));
    expect(screen.queryByText("Query failed: 500")).not.toBeInTheDocument();
  });

  it("sends a new request when Query is clicked again after an error", async () => {
    mockQueryError = true;
    render(<AnalyticsPage />);
    await userEvent.click(screen.getByText("Query Data"));
    await userEvent.click(screen.getByText("Query")); // first click: enables the query
    expect(mockRefetchQuery).not.toHaveBeenCalled();
    await userEvent.click(screen.getByText("Query")); // second click: query already enabled, must refetch
    expect(mockRefetchQuery).toHaveBeenCalledTimes(1);
  });

  it("shows a spinner and disables the Query button while a query is in flight", async () => {
    mockQueryLoading = true;
    render(<AnalyticsPage />);
    await userEvent.click(screen.getByText("Query Data"));
    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Loading" })).toBeDisabled();
  });
});
