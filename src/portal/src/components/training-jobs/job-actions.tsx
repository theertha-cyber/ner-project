import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useCancelTrainingJob } from "@/hooks/use-cancel-training-job";
import { useApproveTrainingJob } from "@/hooks/use-approve-training-job";
import { useRejectTrainingJob } from "@/hooks/use-reject-training-job";
import type { JobStatus } from "@/types/training-jobs";

export interface JobActionsProps {
  jobId: string;
  status: JobStatus;
  tenantId: string;
}

export function JobActions({ jobId, status, tenantId }: JobActionsProps) {
  const { user } = useAuth();
  const [showRejectReason, setShowRejectReason] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  const cancelMutation = useCancelTrainingJob();
  const approveMutation = useApproveTrainingJob();
  const rejectMutation = useRejectTrainingJob();

  const isTenantAdmin = user?.role === "tenant_admin";
  const isSystemAdmin = user?.role === "system_admin";

  const canCancel = isTenantAdmin && ["pending_approval", "queued", "running"].includes(status);
  const canApprove = isSystemAdmin && status === "pending_approval";
  const canReject = isSystemAdmin && status === "pending_approval";

  function handleCancel() {
    if (!window.confirm("Are you sure you want to cancel this training job?")) return;
    cancelMutation.mutate(jobId);
  }

  function handleApprove() {
    approveMutation.mutate({ jobId, tenantId });
  }

  function handleReject() {
    rejectMutation.mutate(
      { jobId, tenantId, reason: rejectReason || undefined },
      {
        onSuccess: () => {
          setShowRejectReason(false);
          setRejectReason("");
        },
      },
    );
  }

  if (!canCancel && !canApprove && !canReject) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {canCancel && (
        <button
          type="button"
          onClick={handleCancel}
          disabled={cancelMutation.isPending}
          className="rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          {cancelMutation.isPending ? "Cancelling..." : "Cancel"}
        </button>
      )}

      {canApprove && (
        <button
          type="button"
          onClick={handleApprove}
          disabled={approveMutation.isPending}
          className="rounded-lg bg-status-completed px-3 py-1.5 text-sm font-medium text-white hover:bg-status-completed/80 disabled:opacity-50"
        >
          {approveMutation.isPending ? "Approving..." : "Approve & queue"}
        </button>
      )}

      {canReject && !showRejectReason && (
        <button
          type="button"
          onClick={() => setShowRejectReason(true)}
          className="rounded-lg border border-status-failed px-3 py-1.5 text-sm font-medium text-status-failed hover:bg-status-failed/5"
        >
          Reject
        </button>
      )}

      {canReject && showRejectReason && (
        <div className="flex w-full flex-col gap-2">
          <textarea
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="Optional rejection reason..."
            rows={2}
            className="w-full rounded border border-border px-2 py-1.5 text-sm"
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleReject}
              disabled={rejectMutation.isPending}
              className="rounded-lg bg-status-failed px-3 py-1.5 text-sm font-medium text-white hover:bg-status-failed/80 disabled:opacity-50"
            >
              {rejectMutation.isPending ? "Rejecting..." : "Confirm Reject"}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowRejectReason(false);
                setRejectReason("");
              }}
              className="rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
