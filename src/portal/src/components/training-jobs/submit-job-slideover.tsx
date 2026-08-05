import { useState, useEffect } from "react";
import { SlideOver, Spinner } from "@/components/ui";
import { authFetch } from "@/lib/auth-fetch";
import { useSubmitTrainingJob } from "@/hooks/use-submit-training-job";

export interface SubmitJobSlideoverProps {
  open: boolean;
  onClose: () => void;
}

export function SubmitJobSlideover({ open, onClose }: SubmitJobSlideoverProps) {
  const [spanCount, setSpanCount] = useState<number | null>(null);
  const [spanLoading, setSpanLoading] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const submitMutation = useSubmitTrainingJob();

  useEffect(() => {
    if (!open) {
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

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setServerError(null);

    submitMutation.mutate(undefined, {
      onSuccess: () => {
        onClose();
      },
      onError: (err) => {
        setServerError(err.message);
      },
    });
  }

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

          <p className="font-body text-sm" style={{ color: "var(--ink-2)" }}>
            Submitting this request notifies a System Admin, who will set the training
            hyperparameters and approve the run.
          </p>

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
              disabled={submitMutation.isPending}
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
