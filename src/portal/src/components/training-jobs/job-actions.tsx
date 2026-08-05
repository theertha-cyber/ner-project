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

const BATCH_OPTIONS = [4, 8, 16, 32];
const SEQ_OPTIONS = [64, 128, 256];

interface ApproveFormErrors {
  learning_rate?: string;
  num_epochs?: string;
  batch_size?: string;
  max_seq_length?: string;
}

export function JobActions({ jobId, status, tenantId }: JobActionsProps) {
  const { user } = useAuth();
  const [showRejectReason, setShowRejectReason] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  const [showApproveForm, setShowApproveForm] = useState(false);
  const [learningRate, setLearningRate] = useState("2e-5");
  const [numEpochs, setNumEpochs] = useState(3);
  const [batchSize, setBatchSize] = useState(8);
  const [maxSeqLength, setMaxSeqLength] = useState(128);
  const [approveErrors, setApproveErrors] = useState<ApproveFormErrors>({});
  const [approveServerError, setApproveServerError] = useState<string | null>(null);

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

  function validateApproveForm(): ApproveFormErrors {
    const e: ApproveFormErrors = {};
    const lr = parseFloat(learningRate);
    if (isNaN(lr) || lr <= 0) e.learning_rate = "Must be a positive number";
    if (numEpochs < 1 || numEpochs > 50) e.num_epochs = "Must be between 1 and 50";
    if (!BATCH_OPTIONS.includes(batchSize)) e.batch_size = "Select a valid batch size";
    if (!SEQ_OPTIONS.includes(maxSeqLength)) e.max_seq_length = "Select a valid sequence length";
    return e;
  }

  const approveFormValid = Object.keys(validateApproveForm()).length === 0;

  function handleApproveSubmit(e: React.FormEvent) {
    e.preventDefault();
    setApproveServerError(null);
    const v = validateApproveForm();
    setApproveErrors(v);
    if (Object.keys(v).length > 0) return;

    approveMutation.mutate(
      {
        jobId,
        tenantId,
        hyperparams: {
          learning_rate: parseFloat(learningRate),
          num_epochs: numEpochs,
          batch_size: batchSize,
          max_seq_length: maxSeqLength,
        },
      },
      {
        onSuccess: () => {
          setShowApproveForm(false);
        },
        onError: (err) => {
          setApproveServerError(err.message);
        },
      },
    );
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
          className="rounded-lg px-3 py-1.5 font-body text-sm font-medium disabled:opacity-50"
          style={{ border: "1px solid var(--line)", color: "var(--ink-2)" }}
        >
          {cancelMutation.isPending ? "Cancelling..." : "Cancel"}
        </button>
      )}

      {canApprove && !showApproveForm && (
        <button
          type="button"
          onClick={() => setShowApproveForm(true)}
          className="rounded-lg bg-status-completed px-3 py-1.5 font-body text-sm font-medium text-white hover:bg-status-completed/80"
        >
          Approve
        </button>
      )}

      {canApprove && showApproveForm && (
        <form onSubmit={handleApproveSubmit} className="flex w-full flex-col gap-3">
          <div>
            <label className="mb-1 block font-body text-xs font-medium" style={{ color: "var(--ink-2)" }}>
              Learning Rate
            </label>
            <input
              type="text"
              value={learningRate}
              onChange={(e) => setLearningRate(e.target.value)}
              className="w-full rounded px-2 py-1.5 font-mono text-sm"
              style={{
                border: `1px solid ${approveErrors.learning_rate ? "var(--bad)" : "var(--line)"}`,
                background: "var(--surface-2)",
                color: "var(--ink)",
              }}
            />
            {approveErrors.learning_rate && (
              <p className="mt-0.5 font-body text-xs" style={{ color: "var(--bad)" }}>{approveErrors.learning_rate}</p>
            )}
          </div>

          <div>
            <label className="mb-1 block font-body text-xs font-medium" style={{ color: "var(--ink-2)" }}>
              Epochs: {numEpochs}
            </label>
            <input
              type="range"
              min={1}
              max={50}
              value={numEpochs}
              onChange={(e) => setNumEpochs(Number(e.target.value))}
              className="w-full accent-brand-primary"
            />
            {approveErrors.num_epochs && (
              <p className="mt-0.5 font-body text-xs" style={{ color: "var(--bad)" }}>{approveErrors.num_epochs}</p>
            )}
          </div>

          <div>
            <label className="mb-1 block font-body text-xs font-medium" style={{ color: "var(--ink-2)" }}>
              Batch Size
            </label>
            <select
              value={batchSize}
              onChange={(e) => setBatchSize(Number(e.target.value))}
              className="w-full rounded px-2 py-1.5 font-mono text-sm"
              style={{
                border: `1px solid ${approveErrors.batch_size ? "var(--bad)" : "var(--line)"}`,
                background: "var(--surface-2)",
                color: "var(--ink)",
              }}
            >
              {BATCH_OPTIONS.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
            {approveErrors.batch_size && (
              <p className="mt-0.5 font-body text-xs" style={{ color: "var(--bad)" }}>{approveErrors.batch_size}</p>
            )}
          </div>

          <div>
            <label className="mb-1 block font-body text-xs font-medium" style={{ color: "var(--ink-2)" }}>
              Max Seq Length
            </label>
            <select
              value={maxSeqLength}
              onChange={(e) => setMaxSeqLength(Number(e.target.value))}
              className="w-full rounded px-2 py-1.5 font-mono text-sm"
              style={{
                border: `1px solid ${approveErrors.max_seq_length ? "var(--bad)" : "var(--line)"}`,
                background: "var(--surface-2)",
                color: "var(--ink)",
              }}
            >
              {SEQ_OPTIONS.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
            {approveErrors.max_seq_length && (
              <p className="mt-0.5 font-body text-xs" style={{ color: "var(--bad)" }}>{approveErrors.max_seq_length}</p>
            )}
          </div>

          {approveServerError && (
            <div
              className="rounded-lg p-3 font-body text-sm"
              style={{ background: "var(--bad-soft)", border: "1px solid var(--bad)", color: "var(--bad)" }}
            >
              {approveServerError}
            </div>
          )}

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={!approveFormValid || approveMutation.isPending}
              className="rounded-lg bg-status-completed px-3 py-1.5 font-body text-sm font-medium text-white hover:bg-status-completed/80 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {approveMutation.isPending ? "Approving..." : "Confirm approve & queue"}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowApproveForm(false);
                setApproveErrors({});
                setApproveServerError(null);
              }}
              className="rounded-lg px-3 py-1.5 font-body text-sm font-medium"
              style={{ border: "1px solid var(--line)", color: "var(--ink-2)" }}
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {canReject && !showRejectReason && (
        <button
          type="button"
          onClick={() => setShowRejectReason(true)}
          className="rounded-lg border border-status-failed px-3 py-1.5 font-body text-sm font-medium text-status-failed hover:bg-status-failed/5"
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
            className="w-full rounded px-2 py-1.5 font-body text-sm"
            style={{ border: "1px solid var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleReject}
              disabled={rejectMutation.isPending}
              className="rounded-lg bg-status-failed px-3 py-1.5 font-body text-sm font-medium text-white hover:bg-status-failed/80 disabled:opacity-50"
            >
              {rejectMutation.isPending ? "Rejecting..." : "Confirm Reject"}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowRejectReason(false);
                setRejectReason("");
              }}
              className="rounded-lg px-3 py-1.5 font-body text-sm font-medium"
              style={{ border: "1px solid var(--line)", color: "var(--ink-2)" }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
