"use client";

import { useMemo, useState } from "react";
import { Spinner } from "@/components/ui";
import { useDocuments } from "@/hooks/use-documents";
import { useToast } from "@/hooks/use-toast";
import { useCreatePrelabelBatch, usePrelabelBatch } from "@/hooks/use-prelabel-batch";
import {
  useAcceptBatch,
  useBatchAcceptance,
  useStartAcceptanceReview,
  useSubmitAcceptanceReview,
} from "@/hooks/use-batch-acceptance";
import type { SuggestionDisposition } from "@/types/seed-bootstrap";

const DISPOSITION_OPTIONS: { value: SuggestionDisposition; label: string; hint: string }[] = [
  { value: "agree", label: "Correct", hint: "Right type, right boundaries" },
  { value: "boundary", label: "Wrong span", hint: "Right type, boundaries need fixing" },
  { value: "retype", label: "Wrong type", hint: "Real entity, wrong label" },
  { value: "reject", label: "Not an entity", hint: "Should not be here at all" },
];

function percent(rate: number | null | undefined): string {
  if (rate === null || rate === undefined) return "—";
  return `${Math.round(rate * 1000) / 10}%`;
}

export function BatchAcceptancePage() {
  const { toast } = useToast();
  const { data: documentsData, isLoading: documentsLoading } = useDocuments(1, 200, "processed");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [batchId, setBatchId] = useState<string | null>(null);
  const [dispositions, setDispositions] = useState<Record<string, SuggestionDisposition>>({});

  const createBatch = useCreatePrelabelBatch();
  const { data: batch } = usePrelabelBatch(batchId);
  const startReview = useStartAcceptanceReview();
  const { data: acceptance } = useBatchAcceptance(batchId);
  const submitReview = useSubmitAcceptanceReview();
  const acceptBatch = useAcceptBatch();

  const documents = useMemo(
    () => (documentsData?.documents ?? []).filter((doc) => doc.purpose !== "query"),
    [documentsData],
  );

  const suggestions = acceptance?.suggestions ?? [];
  const reviewedCount = suggestions.filter((s) => dispositions[s.id]).length;
  const complete = suggestions.length > 0 && reviewedCount === suggestions.length;
  const rate = acceptance?.agreement_rate ?? null;
  const threshold = acceptance?.agreement_threshold ?? 1;
  const meetsThreshold = rate !== null && rate >= threshold;
  const decided = acceptance?.decision === "accepted" || acceptance?.decision === "rejected";

  function toggle(docId: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(docId)) next.delete(docId);
      else next.add(docId);
      return next;
    });
  }

  function handleCreateBatch() {
    createBatch.mutate([...selected], {
      onSuccess: (data) => setBatchId(data.batch_id),
      onError: (err) => toast(err.message, "bad"),
    });
  }

  function handleStartReview() {
    if (!batchId) return;
    startReview.mutate(batchId, {
      onError: (err) => toast(err.message, "bad"),
    });
  }

  function handleSubmitReview() {
    if (!batchId) return;
    submitReview.mutate(
      {
        batchId,
        dispositions: suggestions.map((s) => ({
          suggestion_id: s.id,
          disposition: dispositions[s.id],
        })),
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

      {!batchId && (
        <section className="flex flex-col gap-3">
          <h2 className="font-display text-base font-semibold" style={{ color: "var(--ink)" }}>
            Documents to pre-label
          </h2>
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
                    checked={selected.has(doc.id)}
                    onChange={() => toggle(doc.id)}
                  />
                  <span className="truncate">{doc.filename}</span>
                </label>
              ))}
            </div>
          )}
          <div className="flex items-center gap-3">
            <button
              type="button"
              disabled={selected.size === 0 || createBatch.isPending}
              onClick={handleCreateBatch}
              className="rounded-lg bg-brand-primary px-4 py-2 font-body text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              {createBatch.isPending ? "Starting…" : "Pre-label these documents"}
            </button>
            <span className="font-body text-sm" style={{ color: "var(--ink-3)" }}>
              {selected.size} selected
            </span>
          </div>
        </section>
      )}

      {batch && (
        <section className="flex flex-col gap-3">
          <div
            className="rounded-lg p-3 font-body text-sm flex flex-wrap gap-x-6 gap-y-1"
            style={{ background: "var(--surface-3)", border: "1px solid var(--line)", color: "var(--ink-2)" }}
          >
            <span>Status: {batch.status}</span>
            <span>{batch.document_count} documents</span>
            <span>{batch.succeeded} succeeded</span>
            <span>{batch.failed} failed</span>
            {/* Dropped because the model could not quote them from the document. A rising
                number here is the earliest sign the model has started paraphrasing. */}
            <span>{batch.ungrounded} suggestions dropped as ungrounded</span>
          </div>

          {batch.status === "completed" && !acceptance && (
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

          {!decided && (
            <div className="flex flex-col gap-2 max-h-[28rem] overflow-y-auto">
              {suggestions.map((suggestion) => (
                <div
                  key={suggestion.id}
                  className="rounded-lg border border-border bg-surface p-3 flex flex-wrap items-center gap-3"
                >
                  <span
                    className="rounded px-2 py-0.5 font-mono text-xs"
                    style={{ background: "var(--surface-3)", color: "var(--ink-2)" }}
                  >
                    {suggestion.entity_type}
                  </span>
                  <span className="font-body text-sm flex-1 min-w-0 truncate" style={{ color: "var(--ink)" }}>
                    {suggestion.text}
                  </span>
                  <div className="flex gap-1.5">
                    {DISPOSITION_OPTIONS.map((option) => {
                      const active = dispositions[suggestion.id] === option.value;
                      return (
                        <button
                          key={option.value}
                          type="button"
                          title={option.hint}
                          onClick={() =>
                            setDispositions((current) => ({
                              ...current,
                              [suggestion.id]: option.value,
                            }))
                          }
                          className="rounded border px-2 py-1 font-body text-xs"
                          style={{
                            borderColor: active ? "var(--primary-line)" : "var(--line)",
                            background: active ? "var(--surface-3)" : "transparent",
                            color: active ? "var(--ink)" : "var(--ink-3)",
                          }}
                        >
                          {option.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}

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
              {/* Enabled only once the recorded rate clears the threshold. The server refuses
                  a sub-threshold batch regardless — this is the same rule stated where the
                  reviewer can see it, not a substitute for it. */}
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
