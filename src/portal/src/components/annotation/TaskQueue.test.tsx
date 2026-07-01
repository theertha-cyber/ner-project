import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { TaskQueue } from "./TaskQueue";
import type { AnnotationTask } from "./TaskQueue";

const tasks: AnnotationTask[] = [
  {
    id: "t1",
    document_id: "doc-1",
    annotator_user_id: "u1",
    status: "in-progress",
    created_at: "2026-01-01",
    updated_at: null,
    filename: "invoice-2026-00417.pdf",
    document_status: "processed",
    span_count: 12,
  },
  {
    id: "t2",
    document_id: "doc-2",
    annotator_user_id: "u1",
    status: "unannotated",
    created_at: "2026-01-02",
    updated_at: null,
    filename: "contract-northwind.pdf",
    document_status: "processed",
    span_count: 0,
  },
];

// ── Scenario 5, 7, 8: Task rows show document filename and metadata ───────────

describe("Scenario 5/7/8 — Task rows show document filename and metadata", () => {
  it("renders document filenames as primary labels", () => {
    render(
      <TaskQueue
        tasks={tasks}
        selectedTaskId={null}
        taskStatuses={{}}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText("invoice-2026-00417.pdf")).toBeInTheDocument();
    expect(screen.getByText("contract-northwind.pdf")).toBeInTheDocument();

    // Ordinal labels must not appear
    expect(screen.queryByText("Task 1")).not.toBeInTheDocument();
    expect(screen.queryByText("Task 2")).not.toBeInTheDocument();
  });

  it("renders subtitle as '<document_status> · <span_count> spans'", () => {
    render(
      <TaskQueue
        tasks={tasks}
        selectedTaskId={null}
        taskStatuses={{}}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText("processed · 12 spans")).toBeInTheDocument();
    expect(screen.getByText("processed · 0 spans")).toBeInTheDocument();
  });

  it("falls back to task status when document_status is absent", () => {
    const tasksNoDocStatus: AnnotationTask[] = [
      {
        id: "t3",
        document_id: "doc-3",
        annotator_user_id: "u1",
        status: "in-progress",
        created_at: "2026-01-03",
        updated_at: null,
        filename: "fallback.pdf",
      },
    ];
    render(
      <TaskQueue
        tasks={tasksNoDocStatus}
        selectedTaskId={null}
        taskStatuses={{}}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText("fallback.pdf")).toBeInTheDocument();
    expect(screen.getByText("in progress")).toBeInTheDocument();
  });
});

// ── Scenario 12: Active task row is highlighted ───────────────────────────────

describe("Scenario 12 — Active task row is highlighted", () => {
  it("selected row has primary left border; others do not", () => {
    const { container } = render(
      <TaskQueue
        tasks={tasks}
        selectedTaskId="t1"
        taskStatuses={{}}
        onSelect={vi.fn()}
      />,
    );

    const buttons = container.querySelectorAll("button");
    const activeBtn = buttons[0];
    const inactiveBtn = buttons[1];

    expect(activeBtn.style.borderLeft).toContain("3px solid");
    expect(inactiveBtn.style.borderLeft).toBe("3px solid transparent");
  });

  it("calls onSelect with the clicked task", () => {
    const onSelect = vi.fn();
    render(
      <TaskQueue
        tasks={tasks}
        selectedTaskId={null}
        taskStatuses={{}}
        onSelect={onSelect}
      />,
    );

    fireEvent.click(screen.getByText("invoice-2026-00417.pdf"));
    expect(onSelect).toHaveBeenCalledWith(tasks[0]);
  });
});

// ── Scenario 11: Empty queue shows contextual message ────────────────────────

describe("Scenario 11 — Empty queue shows 'No tasks assigned'", () => {
  it("shows 'No tasks assigned' when task list is empty", () => {
    render(
      <TaskQueue
        tasks={[]}
        selectedTaskId={null}
        taskStatuses={{}}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText("No tasks assigned")).toBeInTheDocument();
  });
});
