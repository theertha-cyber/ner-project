import { useState, useEffect } from "react";
import { SlideOver, Spinner } from "@/components/ui";
import { authFetch } from "@/lib/auth-fetch";
import { useSubmitTrainingJob } from "@/hooks/use-submit-training-job";
import { useTrainingReadiness } from "@/hooks/use-training-readiness";

export interface SubmitJobSlideoverProps {
  open: boolean;
  onClose: () => void;
}

export function SubmitJobSlideover({ open, onClose }: SubmitJobSlideoverProps) {
  const [spanCount, setSpanCount] = useState<number | null>(null);
  const [spanLoading, setSpanLoading] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const submitMutation = useSubmitTrainingJob();
  // Fetched only while the panel is open, and read only to display. Nothing below disables
  // the submit button on it: the check is advisory, and turning it into a gate here would
  // duplicate `NER_MIN_ENTITIES_PER_TYPE` and pre-empt the System Admin approval step
  // ADR-009 puts this decision behind.
  const { data: readiness, isLoading: readinessLoading } = useTrainingReadiness(open);

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

          {/* Per-entity-type readiness. Shown before submission because that is the only
              point at which it can save anything — the same shortfall discovered after a GPU
              run has already cost the run. */}
          <div
            className="rounded-lg p-3 font-body text-sm flex flex-col gap-2"
            style={{ background: "var(--surface-3)", border: "1px solid var(--line)", color: "var(--ink-2)" }}
          >
            {readinessLoading && (
              <span className="flex items-center gap-2">
                <Spinner size="sm" /> Checking per-type readiness...
              </span>
            )}
            {!readinessLoading && !readiness && (
              <span>Unable to check per-type readiness</span>
            )}
            {readiness && (
              <>
                <div style={{ color: "var(--ink-3)" }}>
                  {readiness.threshold_per_entity_type} entities per type unlocks training
                </div>
                {readiness.shortfalling_entity_types.length === 0 ? (
                  <div style={{ color: "var(--good)" }}>
                    Every entity type meets the threshold.
                  </div>
                ) : (
                  <div className="flex flex-col gap-1">
                    <div>
                      {readiness.shortfalling_entity_types.length} entity type
                      {readiness.shortfalling_entity_types.length === 1 ? "" : "s"} below the
                      threshold:
                    </div>
                    <ul className="flex flex-col gap-0.5">
                      {readiness.shortfalling_entity_types.map((row) => (
                        <li key={row.entity_type} className="flex justify-between gap-4">
                          <span>{row.entity_type}</span>
                          <span style={{ color: "var(--ink-3)" }}>
                            {row.count} / {readiness.threshold_per_entity_type}
                          </span>
                        </li>
                      ))}
                    </ul>
                    <div style={{ color: "var(--ink-3)" }}>
                      You can still submit. A System Admin decides whether to run it.
                    </div>
                  </div>
                )}
              </>
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
