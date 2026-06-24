import { useState, useEffect } from "react";
import { SlideOver, Spinner } from "@/components/ui";
import { authFetch } from "@/lib/auth-fetch";
import { useSubmitTrainingJob } from "@/hooks/use-submit-training-job";
import type { SubmitJobPayload } from "@/types/training-jobs";

export interface SubmitJobSlideoverProps {
  open: boolean;
  onClose: () => void;
}

const BATCH_OPTIONS = [4, 8, 16, 32];
const SEQ_OPTIONS = [64, 128, 256];

interface FormErrors {
  learning_rate?: string;
  num_epochs?: string;
  batch_size?: string;
  max_seq_length?: string;
}

export function SubmitJobSlideover({ open, onClose }: SubmitJobSlideoverProps) {
  const [learningRate, setLearningRate] = useState("2e-5");
  const [numEpochs, setNumEpochs] = useState(3);
  const [batchSize, setBatchSize] = useState(8);
  const [maxSeqLength, setMaxSeqLength] = useState(128);
  const [spanCount, setSpanCount] = useState<number | null>(null);
  const [spanLoading, setSpanLoading] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);

  const submitMutation = useSubmitTrainingJob();

  useEffect(() => {
    if (!open) {
      setErrors({});
      setServerError(null);
      return;
    }

    let cancelled = false;
    setSpanLoading(true);

    authFetch("/api/v1/annotation-export")
      .then((res) => {
        if (!res.ok) throw new Error("Failed to fetch spans");
        return res.text();
      })
      .then((text) => {
        if (!cancelled) {
          const count = text.split("\n").filter((line) => line.trim()).length;
          setSpanCount(count);
        }
      })
      .catch(() => {
        if (!cancelled) setSpanCount(null);
      })
      .finally(() => {
        if (!cancelled) setSpanLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open]);

  function validate(): FormErrors {
    const e: FormErrors = {};
    const lr = parseFloat(learningRate);
    if (isNaN(lr) || lr <= 0) e.learning_rate = "Must be a positive number";
    if (numEpochs < 1) e.num_epochs = "Minimum 1 epoch";
    if (!BATCH_OPTIONS.includes(batchSize)) e.batch_size = "Select a valid batch size";
    if (!SEQ_OPTIONS.includes(maxSeqLength)) e.max_seq_length = "Select a valid sequence length";
    return e;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setServerError(null);
    const v = validate();
    setErrors(v);
    if (Object.keys(v).length > 0) return;

    const payload: SubmitJobPayload = {
      learning_rate: parseFloat(learningRate),
      num_epochs: numEpochs,
      batch_size: batchSize,
      max_seq_length: maxSeqLength,
    };

    submitMutation.mutate(payload, {
      onSuccess: () => {
        onClose();
      },
      onError: (err) => {
        setServerError(err.message);
      },
    });
  }

  const meetsThreshold = spanCount !== null && spanCount >= 500;
  const canSubmit = meetsThreshold && Object.keys(errors).length === 0;

  return (
    <SlideOver open={open} onClose={onClose} width={440}>
      <div className="flex flex-col h-full">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="text-lg font-semibold text-gray-900">Submit Training Job</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
          {/* Span preflight */}
          <div
            className={`rounded-lg border p-3 text-sm ${
              spanLoading
                ? "border-gray-200 bg-gray-50"
                : meetsThreshold
                  ? "border-status-completed/30 bg-status-completed/5 text-status-completed"
                  : spanCount !== null
                    ? "border-status-failed/30 bg-status-failed/5 text-status-failed"
                    : "border-gray-200 bg-gray-50 text-gray-500"
            }`}
          >
            {spanLoading ? (
              <span className="flex items-center gap-2">
                <Spinner size="sm" /> Checking annotated entities...
              </span>
            ) : spanCount !== null ? (
              meetsThreshold
                ? `${spanCount} confirmed spans  ·  meets the 500-span minimum`
                : `${spanCount} confirmed spans  ·  requires 500 minimum`
            ) : (
              "Unable to check span count"
            )}
          </div>

          {/* Learning Rate */}
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700">Learning Rate</label>
            <input
              type="text"
              value={learningRate}
              onChange={(e) => setLearningRate(e.target.value)}
              className={`w-full rounded border px-2 py-1.5 text-sm ${
                errors.learning_rate ? "border-status-failed" : "border-border"
              }`}
            />
            {errors.learning_rate && (
              <p className="mt-0.5 text-xs text-status-failed">{errors.learning_rate}</p>
            )}
          </div>

          {/* Num Epochs */}
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700">
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
            {errors.num_epochs && (
              <p className="mt-0.5 text-xs text-status-failed">{errors.num_epochs}</p>
            )}
          </div>

          {/* Batch Size */}
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700">Batch Size</label>
            <select
              value={batchSize}
              onChange={(e) => setBatchSize(Number(e.target.value))}
              className={`w-full rounded border px-2 py-1.5 text-sm ${
                errors.batch_size ? "border-status-failed" : "border-border"
              }`}
            >
              {BATCH_OPTIONS.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
            {errors.batch_size && (
              <p className="mt-0.5 text-xs text-status-failed">{errors.batch_size}</p>
            )}
          </div>

          {/* Max Seq Length */}
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700">Max Seq Length</label>
            <select
              value={maxSeqLength}
              onChange={(e) => setMaxSeqLength(Number(e.target.value))}
              className={`w-full rounded border px-2 py-1.5 text-sm ${
                errors.max_seq_length ? "border-status-failed" : "border-border"
              }`}
            >
              {SEQ_OPTIONS.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
            {errors.max_seq_length && (
              <p className="mt-0.5 text-xs text-status-failed">{errors.max_seq_length}</p>
            )}
          </div>

          {/* Server error */}
          {serverError && (
            <div className="rounded-lg border border-status-failed/30 bg-status-failed/5 p-3 text-sm text-status-failed">
              {serverError}
            </div>
          )}

          {/* Submit */}
          <div className="mt-auto pt-2">
            <button
              type="submit"
              disabled={!canSubmit || submitMutation.isPending}
              className="w-full rounded-lg bg-brand-primary px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitMutation.isPending ? "Submitting..." : "Submit Training Job"}
            </button>
          </div>
        </form>
      </div>
    </SlideOver>
  );
}
