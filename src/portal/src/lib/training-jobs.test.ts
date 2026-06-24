import { describe, it, expect } from "vitest";
import { getTimeline } from "./training-jobs";

describe("getTimeline", () => {
  it("returns pending_approval as active when status is pending_approval", () => {
    const timeline = getTimeline("pending_approval");
    expect(timeline[0]).toEqual({ label: "Pending Approval", state: "active" });
    expect(timeline[1]).toEqual({ label: "Queued", state: "pending" });
    expect(timeline[2]).toEqual({ label: "Running", state: "pending" });
    expect(timeline[3]).toEqual({ label: "Completed", state: "pending" });
  });

  it("marks pending_approval as completed and queued as active when status is queued", () => {
    const timeline = getTimeline("queued");
    expect(timeline[0]).toEqual({ label: "Pending Approval", state: "completed" });
    expect(timeline[1]).toEqual({ label: "Queued", state: "active" });
    expect(timeline[2]).toEqual({ label: "Running", state: "pending" });
    expect(timeline[3]).toEqual({ label: "Completed", state: "pending" });
  });

  it("marks pending_approval and queued as completed and running as active when status is running", () => {
    const timeline = getTimeline("running");
    expect(timeline[0]).toEqual({ label: "Pending Approval", state: "completed" });
    expect(timeline[1]).toEqual({ label: "Queued", state: "completed" });
    expect(timeline[2]).toEqual({ label: "Running", state: "active" });
    expect(timeline[3]).toEqual({ label: "Completed", state: "pending" });
  });

  it("marks all as completed when status is completed", () => {
    const timeline = getTimeline("completed");
    expect(timeline[0]).toEqual({ label: "Pending Approval", state: "completed" });
    expect(timeline[1]).toEqual({ label: "Queued", state: "completed" });
    expect(timeline[2]).toEqual({ label: "Running", state: "completed" });
    expect(timeline[3]).toEqual({ label: "Completed", state: "active" });
  });

  it("returns failed timeline with active on failed step", () => {
    const timeline = getTimeline("failed");
    expect(timeline[0]).toEqual({ label: "Pending Approval", state: "completed" });
    expect(timeline[1]).toEqual({ label: "Queued", state: "completed" });
    expect(timeline[2]).toEqual({ label: "Running", state: "completed" });
    expect(timeline[3]).toEqual({ label: "Failed", state: "active" });
  });

  it("returns cancelled timeline with active on cancelled step", () => {
    const timeline = getTimeline("cancelled");
    expect(timeline[0]).toEqual({ label: "Pending Approval", state: "completed" });
    expect(timeline[1]).toEqual({ label: "Queued", state: "completed" });
    expect(timeline[2]).toEqual({ label: "Running", state: "completed" });
    expect(timeline[3]).toEqual({ label: "Cancelled", state: "active" });
  });

  it("returns rejected timeline with rejected as active", () => {
    const timeline = getTimeline("rejected");
    expect(timeline[0]).toEqual({ label: "Pending Approval", state: "completed" });
    expect(timeline[1]).toEqual({ label: "Rejected", state: "active" });
  });
});
