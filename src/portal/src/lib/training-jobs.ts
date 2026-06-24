import type { JobStatus, TimelineStep } from "@/types/training-jobs";

const LIFECYCLE: { status: JobStatus; label: string }[] = [
  { status: "pending_approval", label: "Pending Approval" },
  { status: "queued", label: "Queued" },
  { status: "running", label: "Running" },
  { status: "completed", label: "Completed" },
];

const FAIL_ORDER: JobStatus[] = [
  "pending_approval",
  "queued",
  "running",
  "failed",
];

const CANCEL_ORDER: JobStatus[] = [
  "pending_approval",
  "queued",
  "running",
  "cancelled",
];

const REJECT_ORDER: JobStatus[] = [
  "pending_approval",
  "rejected",
];

function buildTimeline(order: { status: JobStatus; label: string }[], current: JobStatus): TimelineStep[] {
  let reachedTerminal = false;
  return order.map((step) => {
    if (step.status === current) {
      if (current === "failed" || current === "cancelled" || current === "rejected") {
        reachedTerminal = true;
      }
      return { label: step.label, state: "active" as const };
    }
    if (!reachedTerminal && step.status !== "failed" && step.status !== "cancelled" && step.status !== "rejected") {
      const statusOrder = order.map((o) => o.status);
      const currentIdx = statusOrder.indexOf(current);
      const stepIdx = statusOrder.indexOf(step.status);
      if (stepIdx < currentIdx) return { label: step.label, state: "completed" as const };
    }
    if (reachedTerminal) return { label: step.label, state: "pending" as const };
    if (step.status === "failed" || step.status === "cancelled" || step.status === "rejected") {
      return { label: step.label, state: "pending" as const };
    }
    return { label: step.label, state: "pending" as const };
  });
}

export function getTimeline(status: JobStatus): TimelineStep[] {
  switch (status) {
    case "failed":
      return buildTimeline(
        FAIL_ORDER.map((s) => ({
          status: s,
          label: s === "failed" ? "Failed" : LIFECYCLE.find((l) => l.status === s)!.label,
        })),
        status,
      );
    case "cancelled":
      return buildTimeline(
        CANCEL_ORDER.map((s) => ({
          status: s,
          label: s === "cancelled" ? "Cancelled" : LIFECYCLE.find((l) => l.status === s)!.label,
        })),
        status,
      );
    case "rejected":
      return buildTimeline(
        REJECT_ORDER.map((s) => ({
          status: s,
          label: s === "rejected" ? "Rejected" : LIFECYCLE.find((l) => l.status === s)!.label,
        })),
        status,
      );
    default:
      return buildTimeline(LIFECYCLE, status);
  }
}
