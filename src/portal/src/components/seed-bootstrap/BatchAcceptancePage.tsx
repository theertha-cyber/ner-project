"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Spinner } from "@/components/ui";
import { useDocuments } from "@/hooks/use-documents";
import { useEntityTypes } from "@/hooks/use-entity-types";
import { useToast } from "@/hooks/use-toast";
import {
  useCreatePrelabelBatch,
  usePrelabelBatch,
  usePrelabelBatches,
} from "@/hooks/use-prelabel-batch";
import {
  useAcceptBatch,
  useBatchAcceptance,
  useStartAcceptanceReview,
  useSubmitAcceptanceReview,
} from "@/hooks/use-batch-acceptance";
import type { BatchKind, SuggestionDisposition } from "@/types/seed-bootstrap";
import { BATCH_STATE_LABEL } from "@/types/seed-bootstrap";
import { BatchReviewDocument } from "./BatchReviewDocument";

const INITIAL_BATCH_MAX = 5;

// Same palette and assignment rule as the annotation workspace, so a type keeps its colour
// across the two screens.
const ENTITY_COLORS = [
  "#6366f1", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6",
  "#3b82f6", "#f97316", "#ec4899", "#14b8a6", "#84cc16",
];

function percent(rate: number | null | undefined): string {
  if (rate === null || rate === undefined) return "—";
  return `${Math.round(rate * 1000) / 10}%`;
}

interface BatchAcceptancePageProps {
  /** When set, the page opens straight on this batch's acceptance review and hides the
   * document picker — the Annotator Admin's entry point for an `initial` batch. */
  initialBatchId?: string;
  reviewOnly?: boolean;
}

export function BatchAcceptancePage({ initialBatchId, reviewOnly }: BatchAcceptancePageProps = {}) {
  if (reviewOnly) return <ReviewOnlyBatch batchId={initialBatchId ?? null} />;
  return <TwoStageBatchFlow />;
}

/* -----------------------------------------------------------------------------------------
   Tenant Admin's view: both stages stay visible at once — the initial batch's own status and
   its "reviewed by an Annotator Admin" confirmation don't disappear once the large batch
   exists, and the large-batch picker is shown (locked, not hidden) before it unlocks, so there
   is always a second, visibly-named action to point at.
----------------------------------------------------------------------------------------- */

function TwoStageBatchFlow() {
  const router = useRouter();
  const { toast } = useToast();
  const { data: documentsData, isLoading: documentsLoading } = useDocuments(1, 200, "processed");
  const { data: batchesData } = usePrelabelBatches();
  const createBatch = useCreatePrelabelBatch();

  const [selectedInitial, setSelectedInitial] = useState<Set<string>>(new Set());
  const [selectedLarge, setSelectedLarge] = useState<Set<string>>(new Set());
  const [restartInitial, setRestartInitial] = useState(false);
  // Bridges the gap between "batch created" and the list query's next refetch, so the new
  // batch's own card appears immediately rather than waiting on a poll.
  const [createdInitialId, setCreatedInitialId] = useState<string | null>(null);
  const [createdLargeId, setCreatedLargeId] = useState<string | null>(null);

  const batches = batchesData?.batches ?? [];
  const initialSummary = batches.find((b) => b.batch_kind === "initial");
  const largeSummary = batches.find((b) => b.batch_kind === "large");
  const initialRejected = initialSummary?.acceptance_decision === "rejected";
  const initialApproved = initialSummary?.annotator_review_status === "approved";

  const initialId = createdInitialId ?? (restartInitial ? null : initialSummary?.batch_id ?? null);
  const largeId = createdLargeId ?? largeSummary?.batch_id ?? null;

  const { data: initialBatch } = usePrelabelBatch(initialId);
  const { data: largeBatch } = usePrelabelBatch(largeId);

  const showInitialPicker = !initialId || (initialRejected && restartInitial);
  const largeUnlocked = initialApproved || initialBatch?.annotator_review_status === "approved";
  const largeDone =
    largeBatch != null &&
    (largeBatch.state === "completed" || largeBatch.state === "partially_completed");
  const largeRunning =
    largeBatch != null && (largeBatch.state === "queued" || largeBatch.state === "processing");

  // Toast the two moments the admin is actually waiting on, on top of the persistent inline
  // state below and the platform notification bell — this page is where they're looking.
  const wasApproved = useRef(false);
  useEffect(() => {
    const approved = initialBatch?.annotator_review_status === "approved";
    if (approved && !wasApproved.current) {
      toast("Initial validation batch reviewed and approved by an Annotator Admin.", "ok");
    }
    wasApproved.current = approved;
  }, [initialBatch?.annotator_review_status, toast]);

  const wasLargeDone = useRef(false);
  useEffect(() => {
    const done = largeBatch != null && (largeBatch.state === "completed" || largeBatch.state === "partially_completed");
    if (done && !wasLargeDone.current) {
      toast("Large batch completed — training eligible. You can train the model now.", "ok");
    }
    wasLargeDone.current = done;
  }, [largeBatch?.state, toast]);

  const documents = useMemo(
    // Training documents only: query documents are for chat, and a Q&A-pair document is
    // schema-proposal guidance, not something to pre-label (the batch worker drops it anyway).
    () =>
      (documentsData?.documents ?? []).filter(
        (doc) => doc.purpose !== "query" && doc.purpose !== "qa_pair",
      ),
    [documentsData],
  );

  function toggle(set: Set<string>, setSet: (s: Set<string>) => void, docId: string) {
    const next = new Set(set);
    if (next.has(docId)) next.delete(docId);
    else next.add(docId);
    setSet(next);
  }

  const tooManyForInitial = selectedInitial.size > INITIAL_BATCH_MAX;

  function handleCreate(kind: BatchKind, selected: Set<string>, clear: () => void, remember: (id: string) => void) {
    createBatch.mutate(
      { documentIds: [...selected], batchKind: kind },
      {
        onSuccess: (data) => {
          clear();
          remember(data.batch_id);
          if (kind === "initial") setRestartInitial(false);
        },
        onError: (err) => toast(err.message, "bad"),
      },
    );
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="font-display text-2xl font-semibold" style={{ color: "var(--ink)" }}>
          Batch Pre-labeling
        </h1>
        <p className="font-body text-sm mt-1" style={{ color: "var(--ink-2)" }}>
          Two stages, in order: a small validation batch an Annotator Admin reviews, then the
          main batch — no review needed, it becomes training data as soon as it finishes.
        </p>
      </div>

      {/* ── Stage 1: initial validation batch ─────────────────────────────────────── */}
      <section className="flex flex-col gap-3">
        <h2 className="font-display text-base font-semibold" style={{ color: "var(--ink)" }}>
          1 · Initial validation batch (up to {INITIAL_BATCH_MAX} documents)
        </h2>

        {showInitialPicker ? (
          <>
            {tooManyForInitial && (
              <p className="font-body text-xs" style={{ color: "var(--bad)" }}>
                An initial validation batch covers at most {INITIAL_BATCH_MAX} documents.
              </p>
            )}
            {documentsLoading ? (
              <Spinner size="sm" />
            ) : (
              <div className="flex flex-col gap-1 max-h-80 overflow-y-auto rounded-lg border border-border p-2">
                {documents.map((doc) => (
                  <label
                    key={doc.id}
                    className="flex items-center gap-2 rounded px-2 py-1.5 font-body text-sm cursor-pointer"
                    style={{ color: "var(--ink-2)" }}
                  >
                    <input
                      type="checkbox"
                      checked={selectedInitial.has(doc.id)}
                      onChange={() => toggle(selectedInitial, setSelectedInitial, doc.id)}
                    />
                    <span className="truncate">{doc.filename}</span>
                  </label>
                ))}
              </div>
            )}
            <div className="flex items-center gap-3">
              <button
                type="button"
                disabled={selectedInitial.size === 0 || createBatch.isPending || tooManyForInitial}
                onClick={() =>
                  handleCreate("initial", selectedInitial, () => setSelectedInitial(new Set()), setCreatedInitialId)
                }
                className="rounded-lg bg-brand-primary px-4 py-2 font-body text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                {createBatch.isPending ? "Starting…" : "Pre-label these documents"}
              </button>
              <span className="font-body text-sm" style={{ color: "var(--ink-3)" }}>
                {selectedInitial.size} selected
              </span>
            </div>
          </>
        ) : (
          initialBatch && (
            <div className="flex flex-col gap-2">
              <BatchStatusBar batch={initialBatch} />
              {initialBatch.annotator_review_status === "approved" ? (
                <p className="font-body text-sm font-medium flex items-center gap-1.5" style={{ color: "var(--good)" }}>
                  ✓ Reviewed and approved by an Annotator Admin
                </p>
              ) : initialRejected ? (
                <div className="flex flex-col items-start gap-2">
                  <p className="font-body text-sm" style={{ color: "var(--bad)" }}>
                    Rejected at review. Its suggestions remain available for per-document review
                    below.
                  </p>
                  <button
                    type="button"
                    onClick={() => setRestartInitial(true)}
                    className="rounded-lg border border-border px-4 py-2 font-body text-sm"
                    style={{ color: "var(--ink-2)" }}
                  >
                    Start a new validation batch
                  </button>
                </div>
              ) : initialBatch.state === "queued" || initialBatch.state === "processing" ? (
                <p className="font-body text-sm" style={{ color: "var(--ink-3)" }}>
                  Pre-labeling now…
                </p>
              ) : (
                <p className="font-body text-sm" style={{ color: "var(--ink-3)" }}>
                  With an Annotator Admin for review. The main batch unlocks once it&apos;s
                  approved.
                </p>
              )}
            </div>
          )
        )}
      </section>

      {/* ── Stage 2: large batch ───────────────────────────────────────────────────── */}
      <section className="flex flex-col gap-3">
        <h2 className="font-display text-base font-semibold" style={{ color: "var(--ink)" }}>
          2 · Large batch (100+ documents, no review needed)
        </h2>

        {!largeUnlocked && (
          <p className="font-body text-sm" style={{ color: "var(--ink-3)" }}>
            Locked until the initial validation batch above is approved by an Annotator Admin.
          </p>
        )}

        {/* The upload option stays available even after a large batch has already run — this
            is a repeatable step (new documents keep arriving), not a one-time gate like the
            initial batch above. */}
        {largeUnlocked && (
          <>
            {documentsLoading ? (
              <Spinner size="sm" />
            ) : (
              <div className="flex flex-col gap-1 max-h-80 overflow-y-auto rounded-lg border border-border p-2">
                {documents.map((doc) => (
                  <label
                    key={doc.id}
                    className="flex items-center gap-2 rounded px-2 py-1.5 font-body text-sm cursor-pointer"
                    style={{ color: "var(--ink-2)" }}
                  >
                    <input
                      type="checkbox"
                      checked={selectedLarge.has(doc.id)}
                      onChange={() => toggle(selectedLarge, setSelectedLarge, doc.id)}
                    />
                    <span className="truncate">{doc.filename}</span>
                  </label>
                ))}
              </div>
            )}
            <div className="flex items-center gap-3">
              <button
                type="button"
                disabled={selectedLarge.size === 0 || createBatch.isPending || largeRunning}
                onClick={() =>
                  handleCreate("large", selectedLarge, () => setSelectedLarge(new Set()), setCreatedLargeId)
                }
                className="rounded-lg bg-brand-primary px-4 py-2 font-body text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                {createBatch.isPending ? "Starting…" : "Pre-label these documents"}
              </button>
              <span className="font-body text-sm" style={{ color: "var(--ink-3)" }}>
                {selectedLarge.size} selected
              </span>
            </div>
            {largeRunning && (
              <p className="font-body text-xs" style={{ color: "var(--ink-3)" }}>
                A large batch is already running — you can start another once it finishes.
              </p>
            )}
          </>
        )}

        {largeId && largeBatch && (
          <div className="flex flex-col gap-2 mt-1">
            <p
              className="font-display text-xs font-semibold uppercase tracking-wide"
              style={{ color: "var(--ink-3)" }}
            >
              Most recent large batch
            </p>
            <BatchStatusBar batch={largeBatch} />
            {largeDone ? (
              <>
                <p className="font-body text-sm font-medium flex items-center gap-1.5" style={{ color: "var(--good)" }}>
                  ✓ Completed — promoted automatically, training eligible
                </p>
                <button
                  type="button"
                  onClick={() => router.push("/training-jobs?source=automated")}
                  className="self-start rounded-lg bg-brand-primary px-4 py-2 font-body text-sm font-medium text-white"
                >
                  Train model →
                </button>
              </>
            ) : (
              <p className="font-body text-sm" style={{ color: "var(--ink-3)" }}>
                Pre-labeling now — no review is needed once it finishes. Every suggestion
                becomes training data automatically.
              </p>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

function BatchStatusBar({ batch }: { batch: NonNullable<ReturnType<typeof usePrelabelBatch>["data"]> }) {
  return (
    <div
      className="rounded-lg p-3 font-body text-sm flex flex-wrap gap-x-6 gap-y-1"
      style={{ background: "var(--surface-3)", border: "1px solid var(--line)", color: "var(--ink-2)" }}
    >
      <span
        className="rounded px-2 py-0.5 font-mono text-xs"
        style={{ background: "var(--surface-1)", border: "1px solid var(--line)", color: "var(--ink)" }}
      >
        {BATCH_STATE_LABEL[batch.state] ?? batch.state}
      </span>
      <span>
        {batch.progress ? `${batch.progress.settled} / ${batch.progress.total}` : batch.document_count}{" "}
        documents
      </span>
      <span>{batch.succeeded} succeeded</span>
      <span>{batch.failed} failed</span>
      {/* Dropped because the model could not quote them from the document. A rising number
          here is the earliest sign the model has started paraphrasing. */}
      <span>{batch.ungrounded} suggestions dropped as ungrounded</span>
    </div>
  );
}

/* -----------------------------------------------------------------------------------------
   Annotator Admin's view: unchanged from before — one batch, opened straight into its
   acceptance review.
----------------------------------------------------------------------------------------- */

function ReviewOnlyBatch({ batchId }: { batchId: string | null }) {
  const { toast } = useToast();
  const { data: entityTypesData } = useEntityTypes();
  const [dispositions, setDispositions] = useState<Record<string, SuggestionDisposition>>({});

  const { data: batch } = usePrelabelBatch(batchId);
  const startReview = useStartAcceptanceReview();
  const { data: acceptance } = useBatchAcceptance(batchId, true);
  const submitReview = useSubmitAcceptanceReview();
  const acceptBatch = useAcceptBatch();

  const entityColors = useMemo(() => {
    const colors: Record<string, string> = {};
    (entityTypesData?.entity_types ?? []).forEach((et, i) => {
      colors[et.name] = ENTITY_COLORS[i % ENTITY_COLORS.length];
    });
    return colors;
  }, [entityTypesData]);

  const suggestions = useMemo(() => acceptance?.suggestions ?? [], [acceptance]);
  const reviewedCount = suggestions.filter((s) => dispositions[s.id]).length;

  const reviewDocuments = useMemo(() => {
    const ids =
      acceptance?.sampled_document_ids && acceptance.sampled_document_ids.length > 0
        ? acceptance.sampled_document_ids
        : [...new Set(suggestions.map((s) => s.document_id))];
    return ids.map((documentId) => ({
      documentId,
      filename: documentId,
      suggestions: suggestions.filter((s) => s.document_id === documentId),
    }));
  }, [acceptance, suggestions]);

  function setDisposition(suggestionId: string, disposition: SuggestionDisposition) {
    setDispositions((current) => ({ ...current, [suggestionId]: disposition }));
  }
  const complete = suggestions.length > 0 && reviewedCount === suggestions.length;
  const rate = acceptance?.agreement_rate ?? null;
  const threshold = acceptance?.agreement_threshold ?? 1;
  const meetsThreshold = rate !== null && rate >= threshold;
  const decided = acceptance?.decision === "accepted" || acceptance?.decision === "rejected";

  function handleStartReview() {
    if (!batchId) return;
    startReview.mutate(batchId, { onError: (err) => toast(err.message, "bad") });
  }

  function handleSubmitReview() {
    if (!batchId) return;
    submitReview.mutate(
      {
        batchId,
        dispositions: suggestions.map((s) => ({ suggestion_id: s.id, disposition: dispositions[s.id] })),
      },
      {
        onSuccess: (result) => toast(`Agreement ${percent(result.agreement_rate)}`),
        onError: (err) => toast(err.message, "bad"),
      },
    );
  }

  function handleAccept() {
    if (!batchId) return;
    acceptBatch.mutate(batchId, {
      onSuccess: (result) => toast(`${result.promoted_spans} spans confirmed`),
      onError: (err) => toast(err.message, "bad"),
    });
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="font-display text-2xl font-semibold" style={{ color: "var(--ink)" }}>
          Batch Pre-labeling
        </h1>
        <p className="font-body text-sm mt-1" style={{ color: "var(--ink-2)" }}>
          Pre-label a set of documents in one job, then review a sample before confirming the
          whole batch.
        </p>
      </div>

      {batch && (
        <section className="flex flex-col gap-3">
          <BatchStatusBar batch={batch} />
          {(batch.state === "completed" || batch.state === "partially_completed") && !acceptance && (
            <button
              type="button"
              disabled={startReview.isPending}
              onClick={handleStartReview}
              className="self-start rounded-lg bg-brand-primary px-4 py-2 font-body text-sm font-medium text-white disabled:opacity-50"
            >
              {startReview.isPending ? "Drawing sample…" : "Start acceptance review"}
            </button>
          )}
        </section>
      )}

      {acceptance && (
        <section className="flex flex-col gap-4">
          <div
            className="rounded-lg p-3 font-body text-sm flex flex-wrap gap-x-6 gap-y-1"
            style={{ background: "var(--surface-3)", border: "1px solid var(--line)", color: "var(--ink-2)" }}
          >
            <span>
              {acceptance.sampled
                ? `Random sample of ${acceptance.sample_size} documents`
                : `Full review — all ${acceptance.sample_size} documents`}
            </span>
            <span>
              Reviewed {reviewedCount} of {suggestions.length} suggestions
            </span>
            <span style={{ color: meetsThreshold ? "var(--good)" : "var(--ink-2)" }}>
              Agreement {percent(rate)} / required {percent(threshold)}
            </span>
            {decided && <span>Decision: {acceptance.decision}</span>}
          </div>

          {Object.keys(entityColors).length > 0 && (
            <div className="flex flex-wrap gap-x-4 gap-y-1.5">
              {Object.entries(entityColors).map(([name, color]) => (
                <span key={name} className="flex items-center gap-1.5 font-mono text-xs" style={{ color: "var(--ink-3)" }}>
                  <span className="inline-block size-2.5 rounded-sm" style={{ background: color }} />
                  {name}
                </span>
              ))}
            </div>
          )}

          <div className="flex flex-col gap-4">
            {reviewDocuments.map((doc) => (
              <BatchReviewDocument
                key={doc.documentId}
                documentId={doc.documentId}
                filename={doc.filename}
                suggestions={doc.suggestions}
                dispositions={dispositions}
                onDisposition={setDisposition}
                entityColors={entityColors}
                entityTypes={entityTypesData?.entity_types ?? []}
                readOnly={decided}
              />
            ))}
          </div>

          {!decided && (
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                disabled={!complete || submitReview.isPending}
                onClick={handleSubmitReview}
                className="rounded-lg border border-border px-4 py-2 font-body text-sm disabled:cursor-not-allowed disabled:opacity-50"
                style={{ color: "var(--ink-2)" }}
              >
                {submitReview.isPending ? "Recording…" : "Record review"}
              </button>
              <button
                type="button"
                disabled={!meetsThreshold || acceptBatch.isPending}
                onClick={handleAccept}
                className="rounded-lg bg-brand-primary px-4 py-2 font-body text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                {acceptBatch.isPending ? "Confirming…" : "Confirm whole batch"}
              </button>
              {!complete && (
                <span className="font-body text-sm" style={{ color: "var(--ink-3)" }}>
                  Review every suggestion in the sample first.
                </span>
              )}
              {complete && rate !== null && !meetsThreshold && (
                <span className="font-body text-sm" style={{ color: "var(--bad)" }}>
                  Below the required agreement. This batch cannot be bulk-confirmed; its
                  suggestions stay available for per-document review.
                </span>
              )}
            </div>
          )}

          {acceptance.decision === "accepted" && (
            <p className="font-body text-sm" style={{ color: "var(--good)" }}>
              Batch confirmed at {percent(acceptance.agreement_rate)} agreement.
            </p>
          )}
          {acceptance.decision === "rejected" && (
            <p className="font-body text-sm" style={{ color: "var(--bad)" }}>
              Batch rejected at {percent(acceptance.agreement_rate)} agreement. Its suggestions
              remain available for per-document review.
            </p>
          )}
        </section>
      )}
    </div>
  );
}
