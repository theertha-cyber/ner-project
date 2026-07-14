import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { JobTimeline } from "./job-timeline";
import { getTimeline } from "@/lib/training-jobs";

describe("JobTimeline", () => {
  it("renders steps in a single horizontal row", () => {
    const steps = getTimeline("running");
    render(<JobTimeline steps={steps} currentStatus="running" />);
    const list = screen.getByRole("list", { name: /job status timeline/i });
    expect(list.className).toContain("flex");
    expect(screen.getAllByRole("listitem")).toHaveLength(steps.length);
  });

  it("distinguishes the current step from completed and future steps", () => {
    const steps = getTimeline("running");
    render(<JobTimeline steps={steps} currentStatus="running" />);
    const dots = screen.getAllByTestId("timeline-dot");
    const activeDot = dots.find((d) => d.dataset.state === "active");
    const completedDots = dots.filter((d) => d.dataset.state === "completed");
    const pendingDots = dots.filter((d) => d.dataset.state === "pending");

    expect(activeDot).toBeDefined();
    expect(activeDot!.className).toContain("bg-status-running");
    expect(completedDots.length).toBeGreaterThan(0);
    completedDots.forEach((d) => expect(d.className).toContain("bg-status-completed"));
    expect(pendingDots.length).toBeGreaterThan(0);

    const runningLabel = screen.getByText("Running");
    expect(runningLabel.className).toContain("font-bold");
  });

  it("shows the failure branch without a completed step for a failed job", () => {
    const steps = getTimeline("failed");
    render(<JobTimeline steps={steps} currentStatus="failed" />);
    expect(screen.getByText("Pending Approval")).toBeDefined();
    expect(screen.getByText("Queued")).toBeDefined();
    expect(screen.getByText("Running")).toBeDefined();
    expect(screen.getByText("Failed")).toBeDefined();
    expect(screen.queryByText("Completed")).toBeNull();

    const dots = screen.getAllByTestId("timeline-dot");
    const activeDot = dots.find((d) => d.dataset.state === "active");
    expect(activeDot!.className).toContain("bg-status-failed");
  });

  it("shows the rejected branch without a completed step for a rejected job", () => {
    const steps = getTimeline("rejected");
    render(<JobTimeline steps={steps} currentStatus="rejected" />);
    expect(screen.getByText("Pending Approval")).toBeDefined();
    expect(screen.getByText("Rejected")).toBeDefined();
    expect(screen.queryByText("Completed")).toBeNull();
  });

  it("shows the cancelled branch without a completed step for a cancelled job", () => {
    const steps = getTimeline("cancelled");
    render(<JobTimeline steps={steps} currentStatus="cancelled" />);
    expect(screen.getByText("Cancelled")).toBeDefined();
    expect(screen.queryByText("Completed")).toBeNull();
  });
});
