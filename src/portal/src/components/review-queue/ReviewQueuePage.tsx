"use client";

import { useState } from "react";
import { Spinner } from "@/components/ui";
import { useToast } from "@/hooks/use-toast";
import {
  useResolveQueuedPrediction,
  useReviewAccumulation,
  useReviewQueue,
} from "@/hooks/use-review-queue";
import type { QueuedPrediction } from "@/types/confidence-review";

const PAGE_SIZE = 25;

function percent(confidence: number): string {
  return `${Math.round(confidence * 1000) / 10}%`;
}

/**
 * A neutral label chip.
 *
 * Deliberately not the shared status badge: its variants are a closed vocabulary of run states
 * (running, promoted, failed, and so on), and an entity type or a model version is not a state.
 * Borrowing a status colour for one would make that palette stop meaning anything.
 */
function Chip({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: "neutral" | "warn";
}) {
  const toneClass =
    tone === "warn"
      ? "border-[var(--warn)] text-[var(--warn)]"
      : "border-[var(--border)] text-[var(--text-secondary)]";
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${toneClass}`}
    >
      {children}
    </span>
  );
}

/**
 * The span in its sentence, with the predicted text marked.
 *
 * Rendered from `context` and `context_char_start` rather than by searching the excerpt for the
 * predicted value: the same text can occur more than once in a sentence, and highlighting the
 * first occurrence would point a reviewer at the wrong one. Offsets are the only thing that says
 * which mention this is.
 */
function ContextExcerpt({ prediction }: { prediction: QueuedPrediction }) {
  const relativeStart = prediction.char_start - prediction.context_char_start;
  const relativeEnd = prediction.char_end - prediction.context_char_start;
  const before = prediction.context.slice(0, relativeStart);
  const marked = prediction.context.slice(relativeStart, relativeEnd);
  const after = prediction.context.slice(relativeEnd);

  return (
    <p className="text-sm leading-relaxed text-[var(--text-secondary)]">
      …{before}
      <mark className="rounded bg-[var(--accent-soft)] px-1 font-medium text-[var(--text-primary)]">
        {marked}
      </mark>
      {after}…
    </p>
  );
}

/**
 * The accumulation figure, presented apart from dataset readiness.
 *
 * The two are different quantities answering different questions, and ADR-010 governs only the
 * second. The card says what the number is and, explicitly, what it is not — a figure this size
 * sitting next to a readiness bar is exactly the thing someone would otherwise read as progress
 * toward training.
 */
function AccumulationCard() {
  const { data, isLoading } = useReviewAccumulation();

  if (isLoading) return null;
  if (!data) return null;

  const servingBaseModel = data.model_version === null;

  return (
    <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <header className="flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">
          Reviewed material since this model was trained
        </h2>
        {servingBaseModel ? (
          <Chip>Base model</Chip>
        ) : (
          <Chip>Model version {data.model_version}</Chip>
        )}
      </header>

      {servingBaseModel ? (
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          No trained model is serving yet, so there is no version for this figure to be measured
          against. {data.spans_from_base_model} reviewed{" "}
          {data.spans_from_base_model === 1 ? "span" : "spans"} came from base-model predictions
          and are recorded separately.
        </p>
      ) : (
        <>
          <p className="mt-2 text-3xl font-semibold text-[var(--text-primary)]">
            {data.spans_accumulated}
          </p>
          <p className="text-sm text-[var(--text-secondary)]">
            confirmed {data.spans_accumulated === 1 ? "span" : "spans"} from production review
            since version {data.model_version} was trained
          </p>
          {data.spans_from_base_model > 0 && (
            <p className="mt-1 text-xs text-[var(--text-tertiary)]">
              A further {data.spans_from_base_model} came from base-model predictions and are not
              counted here.
            </p>
          )}
        </>
      )}

      <p className="mt-3 border-t border-[var(--border)] pt-3 text-xs text-[var(--text-tertiary)]">
        This is not a dataset readiness measure. Readiness is counted per entity type against its
        own threshold and is shown on the training screen. Nothing is started automatically by
        this number growing.
      </p>
    </section>
  );
}

interface CorrectionState {
  entity_type: string;
  char_start: number;
  char_end: number;
}

function QueueRow({ prediction }: { prediction: QueuedPrediction }) {
  const { toast } = useToast();
  const resolve = useResolveQueuedPrediction();
  const [correcting, setCorrecting] = useState<CorrectionState | null>(null);

  function submit(
    outcome: "confirmed" | "corrected" | "rejected",
    correction?: CorrectionState,
  ) {
    resolve.mutate(
      { predictionId: prediction.id, outcome, ...(correction ?? {}) },
      {
        onSuccess: (result) => {
          toast(
            result.rejected
              ? "Rejected — no span created"
              : `Recorded as ${result.outcome}`,
          );
          setCorrecting(null);
        },
        onError: (err) => toast(err.message, "bad"),
      },
    );
  }

  const drifted = prediction.text_at_offsets !== prediction.value;

  return (
    <li className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Chip>{prediction.entity_type}</Chip>
        <span className="text-sm font-medium text-[var(--text-primary)]">
          {prediction.text_at_offsets || prediction.value}
        </span>
        <span className="text-xs text-[var(--text-tertiary)]">
          {percent(prediction.confidence)} confident · characters {prediction.char_start}–
          {prediction.char_end} · {prediction.filename}
        </span>
        {prediction.below_business_threshold && (
          <Chip tone="warn">Not in extraction results</Chip>
        )}
        {prediction.served_by_base_model && <Chip>Base model</Chip>}
      </div>

      <div className="mt-2">
        <ContextExcerpt prediction={prediction} />
      </div>

      {drifted && (
        <p className="mt-2 text-xs text-[var(--warn)]">
          The document now reads “{prediction.text_at_offsets}” at these offsets, but the model
          extracted “{prediction.value}”. Check the offsets before confirming.
        </p>
      )}

      {correcting ? (
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <label className="text-xs text-[var(--text-secondary)]">
            Entity type
            <input
              className="mt-1 block w-40 rounded border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-sm"
              value={correcting.entity_type}
              onChange={(e) =>
                setCorrecting({ ...correcting, entity_type: e.target.value })
              }
            />
          </label>
          <label className="text-xs text-[var(--text-secondary)]">
            Start
            <input
              type="number"
              className="mt-1 block w-24 rounded border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-sm"
              value={correcting.char_start}
              onChange={(e) =>
                setCorrecting({ ...correcting, char_start: Number(e.target.value) })
              }
            />
          </label>
          <label className="text-xs text-[var(--text-secondary)]">
            End
            <input
              type="number"
              className="mt-1 block w-24 rounded border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-sm"
              value={correcting.char_end}
              onChange={(e) =>
                setCorrecting({ ...correcting, char_end: Number(e.target.value) })
              }
            />
          </label>
          <button
            type="button"
            className="rounded bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            disabled={resolve.isPending}
            onClick={() => submit("corrected", correcting)}
          >
            Save correction
          </button>
          <button
            type="button"
            className="rounded border border-[var(--border)] px-3 py-1.5 text-sm"
            onClick={() => setCorrecting(null)}
          >
            Cancel
          </button>
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            disabled={resolve.isPending}
            onClick={() => submit("confirmed")}
          >
            Confirm
          </button>
          <button
            type="button"
            className="rounded border border-[var(--border)] px-3 py-1.5 text-sm disabled:opacity-50"
            disabled={resolve.isPending}
            onClick={() =>
              setCorrecting({
                entity_type: prediction.entity_type,
                char_start: prediction.char_start,
                char_end: prediction.char_end,
              })
            }
          >
            Correct
          </button>
          <button
            type="button"
            className="rounded border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--danger)] disabled:opacity-50"
            disabled={resolve.isPending}
            onClick={() => submit("rejected")}
          >
            Not an entity
          </button>
        </div>
      )}
    </li>
  );
}

/**
 * The low-confidence review queue.
 *
 * Annotation-oriented, and deliberately not a replacement for the extraction review screen. That
 * one corrects an extracted *value* — a normalisation of what the text says — and keeps working
 * for its own purpose. This one adjusts *offsets*, because that is what a training span is.
 */
export function ReviewQueuePage() {
  const [offset, setOffset] = useState(0);
  const { data, isLoading, error } = useReviewQueue(PAGE_SIZE, offset);

  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-xl font-semibold text-[var(--text-primary)]">Review queue</h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          Predictions the model was least sure about. Confirming or correcting one turns it into
          training data; rejecting it records that the model was wrong and creates nothing.
        </p>
      </header>

      <AccumulationCard />

      {isLoading && <Spinner />}
      {error && <p className="text-sm text-[var(--danger)]">{error.message}</p>}

      {data && data.total === 0 && (
        <p className="rounded-xl border border-dashed border-[var(--border)] p-8 text-center text-sm text-[var(--text-secondary)]">
          Nothing waiting for review. Predictions appear here when they fall below the review
          confidence threshold.
        </p>
      )}

      {data && data.total > 0 && (
        <>
          <p className="text-sm text-[var(--text-secondary)]">
            {data.total} waiting · showing {offset + 1}–
            {Math.min(offset + data.items.length, data.total)}
          </p>
          <ul className="space-y-3">
            {data.items.map((prediction) => (
              <QueueRow key={prediction.id} prediction={prediction} />
            ))}
          </ul>
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded border border-[var(--border)] px-3 py-1.5 text-sm disabled:opacity-40"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            >
              Previous
            </button>
            <button
              type="button"
              className="rounded border border-[var(--border)] px-3 py-1.5 text-sm disabled:opacity-40"
              disabled={offset + PAGE_SIZE >= data.total}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  );
}
