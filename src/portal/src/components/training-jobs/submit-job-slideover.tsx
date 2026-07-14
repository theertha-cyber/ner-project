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

  const canSubmit = Object.keys(errors).length === 0;

  return (
    <SlideOver open={open} onClose={onClose} width={440}>
      <div className="flex flex-col h-full" style={{ background: "var(--surface-2)" }}>
        <div
          className="flex items-center justify-between px-4 py-3"
          style={{ borderBottom: "1px solid var(--line)" }}
        >
          <h2 className="font-display text-lg font-semibold" style={{ color: "var(--ink)" }}>
            Submit Training Job
          </h2>
          <button
            type="button"
            onClick={onClose}
            style={{ color: "var(--ink-3)" }}
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
          {/* Span preflight */}
          <div
            className="rounded-lg p-3 font-body text-sm"
            style={{ background: "var(--surface-3)", border: "1px solid var(--line)", color: "var(--ink-2)" }}
          >
            {spanLoading ? (
              <span className="flex items-center gap-2">
                <Spinner size="sm" /> Checking annotated entities...
              </span>
            ) : spanCount !== null ? (
              `${spanCount} confirmed spans`
            ) : (
              "Unable to check span count"
            )}
          </div>

          {/* Learning Rate */}
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
                border: `1px solid ${errors.learning_rate ? "var(--bad)" : "var(--line)"}`,
                background: "var(--surface-2)",
                color: "var(--ink)",
              }}
            />
            {errors.learning_rate && (
              <p className="mt-0.5 font-body text-xs" style={{ color: "var(--bad)" }}>{errors.learning_rate}</p>
            )}
          </div>

          {/* Num Epochs */}
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
            {errors.num_epochs && (
              <p className="mt-0.5 font-body text-xs" style={{ color: "var(--bad)" }}>{errors.num_epochs}</p>
            )}
          </div>

          {/* Batch Size */}
          <div>
            <label className="mb-1 block font-body text-xs font-medium" style={{ color: "var(--ink-2)" }}>
              Batch Size
            </label>
            <select
              value={batchSize}
              onChange={(e) => setBatchSize(Number(e.target.value))}
              className="w-full rounded px-2 py-1.5 font-mono text-sm"
              style={{
                border: `1px solid ${errors.batch_size ? "var(--bad)" : "var(--line)"}`,
                background: "var(--surface-2)",
                color: "var(--ink)",
              }}
            >
              {BATCH_OPTIONS.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
            {errors.batch_size && (
              <p className="mt-0.5 font-body text-xs" style={{ color: "var(--bad)" }}>{errors.batch_size}</p>
            )}
          </div>

          {/* Max Seq Length */}
          <div>
            <label className="mb-1 block font-body text-xs font-medium" style={{ color: "var(--ink-2)" }}>
              Max Seq Length
            </label>
            <select
              value={maxSeqLength}
              onChange={(e) => setMaxSeqLength(Number(e.target.value))}
              className="w-full rounded px-2 py-1.5 font-mono text-sm"
              style={{
                border: `1px solid ${errors.max_seq_length ? "var(--bad)" : "var(--line)"}`,
                background: "var(--surface-2)",
                color: "var(--ink)",
              }}
            >
              {SEQ_OPTIONS.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
            {errors.max_seq_length && (
              <p className="mt-0.5 font-body text-xs" style={{ color: "var(--bad)" }}>{errors.max_seq_length}</p>
            )}
          </div>

          {/* Server error */}
          {serverError && (
            <div
              className="rounded-lg p-3 font-body text-sm"
              style={{ background: "var(--bad-soft)", border: "1px solid var(--bad)", color: "var(--bad)" }}
            >
              {serverError}
            </div>
          )}

          {/* Submit */}
          <div className="mt-auto pt-2">
            <button
              type="submit"
              disabled={!canSubmit || submitMutation.isPending}
              className="w-full rounded-lg bg-brand-primary px-4 py-2 font-body text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitMutation.isPending ? "Submitting..." : "Submit Training Job"}
            </button>
          </div>
        </form>
      </div>
    </SlideOver>
  );
}
