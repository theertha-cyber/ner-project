import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ContinueWorkCard } from "./ContinueWorkCard";
import type { ContinueWork } from "@/types/dashboard";

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

function makeData(overrides: Partial<ContinueWork> = {}): ContinueWork {
  return {
    taskId: "abc123",
    documentId: "doc-1",
    documentName: "resume_01.pdf",
    status: "in-progress",
    spanCount: 12,
    mode: "resume",
    ...overrides,
  };
}

describe("ContinueWorkCard", () => {
  it("links into the annotation workspace for the task being resumed", () => {
    render(<ContinueWorkCard data={makeData()} />);
    expect(screen.getByText("resume_01.pdf")).toBeInTheDocument();
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/annotation?task=abc123");
    expect(link.textContent).toContain("Resume");
  });

  it("reads Start for a task that has not been begun", () => {
    render(<ContinueWorkCard data={makeData({ mode: "start", status: "pending", spanCount: 0 })} />);
    expect(screen.getByRole("link").textContent).toContain("Start");
  });

  it("reads Review and does not present finished work as outstanding", () => {
    render(<ContinueWorkCard data={makeData({ mode: "review", status: "completed", spanCount: 8 })} />);
    expect(screen.getByRole("link").textContent).toContain("Review");
    expect(screen.queryByText(/so far/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/not started/i)).not.toBeInTheDocument();
    expect(screen.getByText(/submitted with 8 entities/i)).toBeInTheDocument();
  });

  it("renders a caught-up state with no link when there is nothing to return to", () => {
    render(<ContinueWorkCard data={null} />);
    expect(screen.getByText(/all caught up/i)).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("truncates a long document name but keeps it reachable via title", () => {
    const longName = "AbdullahSuhailA[7_0]_final_revision_2026_08_06.pdf";
    render(<ContinueWorkCard data={makeData({ documentName: longName })} />);
    const el = screen.getByText(longName);
    expect(el).toHaveAttribute("title", longName);
    expect(el).toHaveStyle({ textOverflow: "ellipsis", whiteSpace: "nowrap" });
  });

  it("renders a skeleton while the dashboard query is in flight", () => {
    render(<ContinueWorkCard isLoading />);
    expect(screen.getByTestId("continue-work-skeleton")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
