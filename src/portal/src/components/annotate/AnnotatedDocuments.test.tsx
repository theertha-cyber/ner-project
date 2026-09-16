import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { AnnotatedDocuments } from "./AnnotatedDocuments";
import type { AnnotationTask } from "@/components/annotation/TaskQueue";

function task(overrides: Partial<AnnotationTask> = {}): AnnotationTask {
  return {
    id: "task-1",
    document_id: "doc-1",
    annotator_user_id: "u1",
    status: "completed",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: null,
    filename: "Contract-NDA.pdf",
    span_count: 15,
    ...overrides,
  };
}

describe("AnnotatedDocuments", () => {
  it("lists a completed task's filename and span count", () => {
    render(<AnnotatedDocuments tasks={[task()]} onView={vi.fn()} />);
    expect(screen.getByText("Contract-NDA.pdf")).toBeDefined();
    expect(screen.getByText("15")).toBeDefined();
  });

  it("calls onView with the task when its View action is activated", () => {
    const onView = vi.fn();
    const t = task({ id: "abc-123" });
    render(<AnnotatedDocuments tasks={[t]} onView={onView} />);
    fireEvent.click(screen.getByText("View →"));
    expect(onView).toHaveBeenCalledWith(t);
  });

  it("shows an empty-state message and no table when there are no completed tasks", () => {
    render(<AnnotatedDocuments tasks={[]} onView={vi.fn()} />);
    expect(screen.getByText(/nothing annotated yet/i)).toBeDefined();
    expect(screen.queryByText("Document")).toBeNull();
  });

  it("renders one row per task", () => {
    render(
      <AnnotatedDocuments
        tasks={[task({ id: "1", filename: "A.pdf" }), task({ id: "2", filename: "B.pdf" })]}
        onView={vi.fn()}
      />,
    );
    expect(screen.getByText("A.pdf")).toBeDefined();
    expect(screen.getByText("B.pdf")).toBeDefined();
    expect(screen.getAllByText("View →")).toHaveLength(2);
  });
});
