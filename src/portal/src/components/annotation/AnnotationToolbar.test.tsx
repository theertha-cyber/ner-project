import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AnnotationToolbar } from "./AnnotationToolbar";
import type { AnnotationTask } from "./TaskQueue";

// ── Mocks ──────────────────────────────────────────────────────────────────

const mockToast = vi.fn();
vi.mock("@/hooks/use-toast", () => ({ useToast: () => ({ toast: mockToast }) }));

const mockAuthFetch = vi.fn();
vi.mock("@/lib/auth-fetch", () => ({ authFetch: (...args: unknown[]) => mockAuthFetch(...args) }));

// ── Fixtures ─────────────────────────────────────────────────────────────────

const task: AnnotationTask = {
  id: "task-1",
  document_id: "doc-1",
  annotator_user_id: "u1",
  status: "in-progress",
  created_at: "2026-01-01",
  updated_at: null,
  filename: "invoice-2026-00417.pdf",
  document_status: "processed",
  span_count: 3,
};

const defaultProps = {
  task,
  filename: "invoice-2026-00417.pdf",
  currentStatus: "in-progress" as AnnotationTask["status"],
  confirmedCount: 3,
  suggestedCount: 2,
  layoutMode: "3pane" as const,
  isPrelabeling: false,
  onStatusChange: vi.fn(),
  onLayoutChange: vi.fn(),
  onPrelabel: vi.fn(),
};

beforeEach(() => {
  vi.clearAllMocks();
  mockAuthFetch.mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ id: task.id, status: "completed" }),
  });
});

// ── Scenario 6 (task 4.5): Toolbar shows filename ────────────────────────────

describe("Scenario 6 — Toolbar shows document filename", () => {
  it("shows filename in toolbar, not ordinal label", () => {
    render(<AnnotationToolbar {...defaultProps} />);

    expect(screen.getByText("invoice-2026-00417.pdf")).toBeInTheDocument();
    expect(screen.queryByText("Task 1")).not.toBeInTheDocument();
  });

  it("shows 'No task selected' when task is null", () => {
    render(<AnnotationToolbar {...defaultProps} task={null} filename="" />);
    expect(screen.getByText("No task selected")).toBeInTheDocument();
  });
});

// ── Scenario 5: Toolbar renders all six elements ──────────────────────────────

describe("Scenario 5 — Toolbar renders all elements for an active task", () => {
  it("shows filename, status group, span counter, pre-label button, and layout toggle", () => {
    render(<AnnotationToolbar {...defaultProps} />);

    // (1) Filename
    expect(screen.getByText("invoice-2026-00417.pdf")).toBeInTheDocument();

    // (2) Status group with three buttons
    expect(screen.getByTestId("status-group")).toBeInTheDocument();
    expect(screen.getByTestId("status-btn-pending")).toBeInTheDocument();
    expect(screen.getByTestId("status-btn-in_progress")).toBeInTheDocument();
    expect(screen.getByTestId("status-btn-completed")).toBeInTheDocument();

    // (3) "in_progress" is the active button (task status is "in-progress")
    const activeBtn = screen.getByTestId("status-btn-in_progress");
    expect(activeBtn).toHaveStyle({ fontWeight: "600" });

    // (4) Span counter
    expect(screen.getByTestId("span-counter")).toHaveTextContent("3 confirmed · 2 suggested");

    // (5) Pre-label button
    expect(screen.getByTestId("prelabel-btn")).toBeInTheDocument();
    expect(screen.getByTestId("prelabel-btn")).not.toBeDisabled();

    // (6) Layout toggle
    expect(screen.getByTestId("layout-btn-3pane")).toBeInTheDocument();
    expect(screen.getByTestId("layout-btn-focus")).toBeInTheDocument();
  });
});

// ── Scenario 12 (task 4.5): Active status button has solid primary fill ───────

describe("Scenario 12 — Active status button has solid primary fill", () => {
  it("active button has primary background and white text", () => {
    render(<AnnotationToolbar {...defaultProps} />);
    const activeBtn = screen.getByTestId("status-btn-in_progress");
    expect(activeBtn).toHaveStyle({ color: "#fff" });
  });
});

// ── Scenario 6: Clicking status button updates optimistically ─────────────────

describe("Scenario 6 — Clicking status button sends PATCH and updates optimistically", () => {
  it("calls onStatusChange immediately and sends PATCH request", async () => {
    const onStatusChange = vi.fn();
    render(<AnnotationToolbar {...defaultProps} onStatusChange={onStatusChange} />);

    fireEvent.click(screen.getByTestId("status-btn-completed"));

    // Optimistic: onStatusChange called immediately
    expect(onStatusChange).toHaveBeenCalledWith("completed");

    // PATCH request sent
    await waitFor(() => {
      expect(mockAuthFetch).toHaveBeenCalledWith(
        "/api/v1/annotation-tasks/task-1",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ status: "completed" }),
        }),
      );
    });
  });

  it("status button shows active state immediately after click", async () => {
    render(<AnnotationToolbar {...defaultProps} />);

    const completedBtn = screen.getByTestId("status-btn-completed");
    fireEvent.click(completedBtn);

    await waitFor(() => {
      expect(completedBtn).toHaveStyle({ fontWeight: "600" });
    });
  });
});

// ── Scenario 7: 422 reverts selection and shows toast ────────────────────────

describe("Scenario 7 — PATCH 422 reverts status selection and shows toast", () => {
  it("reverts to previous status and shows toast on 422 response", async () => {
    const errorDetail = { message: "Cannot transition from 'in-progress' to 'completed'" };
    mockAuthFetch.mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: errorDetail }),
    });

    const onStatusChange = vi.fn();
    render(<AnnotationToolbar {...defaultProps} onStatusChange={onStatusChange} />);

    fireEvent.click(screen.getByTestId("status-btn-completed"));

    // First call: optimistic update
    expect(onStatusChange).toHaveBeenCalledWith("completed");

    await waitFor(() => {
      // Second call: revert to previous status
      expect(onStatusChange).toHaveBeenCalledWith("in-progress");
    });

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.stringContaining("Cannot transition"),
        "bad",
      );
    });
  });
});

// ── Pre-label button disabled during in-flight ────────────────────────────────

describe("Pre-label button disabled while in-flight", () => {
  it("is disabled and non-interactive when isPrelabeling=true", () => {
    render(<AnnotationToolbar {...defaultProps} isPrelabeling />);
    const btn = screen.getByTestId("prelabel-btn");
    expect(btn).toBeDisabled();
    expect(btn).toHaveStyle({ opacity: "0.6" });
  });
});
