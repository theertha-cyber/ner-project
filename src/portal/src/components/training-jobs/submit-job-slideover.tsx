import { useState, useEffect } from "react";
import { SlideOver, Spinner } from "@/components/ui";
import { authFetch } from "@/lib/auth-fetch";
import { useSubmitTrainingJob } from "@/hooks/use-submit-training-job";
import { useTrainingReadiness } from "@/hooks/use-training-readiness";
import type { SourceScope } from "@/types/training-jobs";

const SOURCE_LABEL: Record<SourceScope, string> = {
  manual: "Manual annotation",
  automated: "Automated batches",
  import: "Imported annotations",
};

export interface SubmitJobSlideoverProps {
  open: boolean;
  onClose: () => void;
  /** Set when opened from a specific workflow's own "Train model" action (Manual,
   * Automated) — the source is then locked, not chosen, since that workflow already decided
   * it. Omit to require an explicit choice (the generic entry point on this page). */
  sourceScope?: SourceScope;
}

export function SubmitJobSlideover({ open, onClose, sourceScope }: SubmitJobSlideoverProps) {
  const [spanCount, setSpanCount] = useState<number | null>(null);
  const [spanLoading, setSpanLoading] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  // Only used when no `sourceScope` prop is given — the generic "+ Submit job" entry point
  // still requires picking exactly one workflow, since training never blends them.
  const [chosenSource, setChosenSource] = useState<SourceScope | null>(null);

  const effectiveSource = sourceScope ?? chosenSource;

  const submitMutation = useSubmitTrainingJob();
  // Fetched only while the panel is open, and read only to display. Nothing below disables
  // the submit button on it: the check is advisory, and turning it into a gate here would
  // duplicate `NER_MIN_ENTITIES_PER_TYPE` and pre-empt the System Admin approval step
  // ADR-009 puts this decision behind.
  const { data: readiness, isLoading: readinessLoading } = useTrainingReadiness(open);

  useEffect(() => {
    if (!open) {
      setServerError(null);
      setChosenSource(null);
      return;
    }
  }, [open]);

  useEffect(() => {
    if (!open || !effectiveSource) {
      setSpanCount(null);
      return;
    }

    let cancelled = false;
    setSpanLoading(true);

    authFetch(`/api/v1/annotation-export?source=${effectiveSource}`)
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
  }, [open, effectiveSource]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setServerError(null);

    if (!effectiveSource) {
      setServerError("Choose which workflow this training run is for.");
      return;
    }

    submitMutation.mutate(
      { sourceScope: effectiveSource },
      {
        onSuccess: () => {
          onClose();
        },
        onError: (err) => {
          setServerError(err.message);
        },
      },
    );
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
          {/* Manual, Automated, and Import are independent workflows — a job trains on
              exactly one, never a blend. Locked when opened from that workflow's own
              "Train model" action; otherwise the tenant admin must choose. */}
          {sourceScope ? (
            <div
              className="rounded-lg p-3 font-body text-sm"
              style={{ background: "var(--surface-3)", border: "1px solid var(--line)", color: "var(--ink-2)" }}
            >
              Training source: <strong style={{ color: "var(--ink)" }}>{SOURCE_LABEL[sourceScope]}</strong>
            </div>
          ) : (
            <fieldset className="flex flex-col gap-2">
              <legend className="font-body text-sm font-medium mb-1" style={{ color: "var(--ink)" }}>
                Which workflow is this training run for?
              </legend>
              {(Object.keys(SOURCE_LABEL) as SourceScope[]).map((value) => (
                <label
                  key={value}
                  className="flex items-center gap-2 rounded-lg p-2 font-body text-sm cursor-pointer"
                  style={{
                    border: `1px solid ${chosenSource === value ? "var(--brand-primary, var(--ink))" : "var(--line)"}`,
                    color: "var(--ink-2)",
                  }}
                >
                  <input
                    type="radio"
                    name="source-scope"
                    checked={chosenSource === value}
                    onChange={() => setChosenSource(value)}
                  />
                  {SOURCE_LABEL[value]}
                </label>
              ))}
            </fieldset>
          )}

          {/* Span preflight, scoped to the chosen/locked source */}
          <div
            className="rounded-lg p-3 font-body text-sm"
            style={{ background: "var(--surface-3)", border: "1px solid var(--line)", color: "var(--ink-2)" }}
          >
            {!effectiveSource ? (
              "Choose a workflow above to check its confirmed spans"
            ) : spanLoading ? (
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
              run has already cost the run. Tenant-wide, not scoped to the chosen source above —
              the readiness report predates source scoping and is advisory regardless. */}
          <div
            className="rounded-lg p-3 font-body text-sm flex flex-col gap-2"
            style={{ background: "var(--surface-3)", border: "1px solid var(--line)", color: "var(--ink-2)" }}
          >
            <div className="font-body text-xs" style={{ color: "var(--ink-3)" }}>
              Tenant-wide readiness (not scoped to the workflow above)
            </div>
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
              disabled={submitMutation.isPending || !effectiveSource}
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
