import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AnnotationActionBar } from "./AnnotationActionBar";
import type { AnnotationTask } from "./TaskQueue";

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

// ── Scenario 8 — Action bar renders at the bottom of the workspace ───────────

describe("Scenario 8 — Action bar renders at the bottom of the workspace", () => {
  it("shows a save indicator and a Mark as Completed button", () => {
    render(
      <AnnotationActionBar
        task={task}
        saveState="saved"
        isCompleting={false}
        onMarkCompleted={vi.fn()}
      />,
    );

    expect(screen.getByTestId("annotation-action-bar")).toBeInTheDocument();
    expect(screen.getByTestId("save-indicator")).toHaveTextContent("All changes saved");
    expect(screen.getByTestId("mark-completed-btn")).toBeInTheDocument();
    expect(screen.getByTestId("mark-completed-btn")).not.toBeDisabled();
  });
});

// ── Scenario 12 — Action bar disabled with no task selected ──────────────────

describe("Scenario 12 — Action bar disabled with no task selected", () => {
  it("disables the button and sends no request on click when no task is selected", () => {
    const onMarkCompleted = vi.fn();
    render(
      <AnnotationActionBar
        task={null}
        saveState="idle"
        isCompleting={false}
        onMarkCompleted={onMarkCompleted}
      />,
    );

    const btn = screen.getByTestId("mark-completed-btn");
    expect(btn).toBeDisabled();

    fireEvent.click(btn);
    expect(onMarkCompleted).not.toHaveBeenCalled();
  });
});
