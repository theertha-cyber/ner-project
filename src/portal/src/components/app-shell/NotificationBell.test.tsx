import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { NotificationBell } from "./NotificationBell";
import type { AppNotification } from "@/hooks/use-notifications";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({ push: mockPush })),
}));

let mockRole: "tenant_admin" | "annotator" = "tenant_admin";
vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(() => ({ user: { role: mockRole } })),
}));

let mockItems: AppNotification[] = [];
const mockMarkRead = vi.fn();
vi.mock("@/hooks/use-notifications", () => ({
  useNotifications: vi.fn(() => ({ data: { items: mockItems, unread: mockItems.length } })),
  useMarkNotificationRead: vi.fn(() => ({ mutate: mockMarkRead })),
}));

function notification(overrides: Partial<AppNotification> = {}): AppNotification {
  return {
    id: "notif-1",
    kind: "annotation_task_completed",
    title: "Annotation task completed",
    body: "Document annotated and approved.",
    resource_type: "annotation_task",
    resource_id: "task-1",
    read_at: null,
    created_at: "2026-09-12T10:00:00Z",
    ...overrides,
  };
}

describe("NotificationBell — navigation targets", () => {
  beforeEach(() => {
    mockPush.mockClear();
    mockMarkRead.mockClear();
    mockRole = "tenant_admin";
    mockItems = [];
  });

  it("routes a completed manual annotation task notification to Models & Training scoped to manual", () => {
    mockItems = [notification()];
    render(<NotificationBell />);

    fireEvent.click(screen.getByLabelText("Notifications"));
    fireEvent.click(screen.getByText("Annotation task completed"));

    expect(mockPush).toHaveBeenCalledWith("/training-jobs?source=manual");
  });

  it("marks the notification read when clicked", () => {
    mockItems = [notification()];
    render(<NotificationBell />);

    fireEvent.click(screen.getByLabelText("Notifications"));
    fireEvent.click(screen.getByText("Annotation task completed"));

    expect(mockMarkRead).toHaveBeenCalledWith("notif-1");
  });

  it("routes an automated batch notification to the retrain page for a tenant_admin", () => {
    mockItems = [
      notification({
        id: "notif-2",
        kind: "automated_batch_approved",
        title: "Automated batch approved",
        resource_type: "prelabel_batch",
        resource_id: "batch-1",
      }),
    ];
    render(<NotificationBell />);

    fireEvent.click(screen.getByLabelText("Notifications"));
    fireEvent.click(screen.getByText("Automated batch approved"));

    expect(mockPush).toHaveBeenCalledWith("/annotate/automated/retrain");
  });

  it("routes an automated batch notification to the batch review for an annotator", () => {
    mockRole = "annotator";
    mockItems = [
      notification({
        id: "notif-3",
        kind: "automated_batch_approved",
        title: "Automated batch approved",
        resource_type: "prelabel_batch",
        resource_id: "batch-1",
      }),
    ];
    render(<NotificationBell />);

    fireEvent.click(screen.getByLabelText("Notifications"));
    fireEvent.click(screen.getByText("Automated batch approved"));

    expect(mockPush).toHaveBeenCalledWith("/annotate/review-batch/batch-1");
  });
});
