import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AnnotationToolbar } from "./AnnotationToolbar";
import type { AnnotationTask } from "./TaskQueue";

// ── Mocks ──────────────────────────────────────────────────────────────────

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
  onLayoutChange: vi.fn(),
  onPrelabel: vi.fn(),
};

beforeEach(() => {
  vi.clearAllMocks();
});

// ── Scenario 6 — Toolbar shows document filename ─────────────────────────────

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

// ── Scenario 1 — Toolbar renders all elements for an active task ─────────────

describe("Scenario 1 — Toolbar renders all elements for an active task", () => {
  it("shows filename, status badge, span counter, pre-label button, and layout toggle", () => {
    render(<AnnotationToolbar {...defaultProps} />);

    expect(screen.getByText("invoice-2026-00417.pdf")).toBeInTheDocument();

    expect(screen.getByTestId("status-badge")).toHaveTextContent("in_progress");

    expect(screen.getByTestId("span-counter")).toHaveTextContent("3 confirmed · 2 suggested");

    expect(screen.getByTestId("prelabel-btn")).toBeInTheDocument();
    expect(screen.getByTestId("prelabel-btn")).not.toBeDisabled();

    expect(screen.getByTestId("layout-btn-3pane")).toBeInTheDocument();
    expect(screen.getByTestId("layout-btn-focus")).toBeInTheDocument();
  });
});

// ── Scenario 2 — Toolbar exposes no status selection control ─────────────────

describe("Scenario 2 — Toolbar exposes no status selection control", () => {
  it("renders no status button group and issues no PATCH request", () => {
    render(<AnnotationToolbar {...defaultProps} />);

    expect(screen.queryByTestId("status-group")).not.toBeInTheDocument();
    expect(screen.queryByTestId("status-btn-pending")).not.toBeInTheDocument();
    expect(screen.queryByTestId("status-btn-in_progress")).not.toBeInTheDocument();
    expect(screen.queryByTestId("status-btn-completed")).not.toBeInTheDocument();
    expect(mockAuthFetch).not.toHaveBeenCalled();
  });
});

// ── Scenario 3 — Badge reflects completed status without offering a transition ──

describe("Scenario 3 — Badge reflects completed status without offering a transition", () => {
  it("shows a completed badge and no control that transitions back to in_progress", () => {
    render(<AnnotationToolbar {...defaultProps} currentStatus="completed" />);

    expect(screen.getByTestId("status-badge")).toHaveTextContent("completed");
    expect(screen.queryByTestId("status-group")).not.toBeInTheDocument();
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
