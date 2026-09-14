"use client";

import Link from "next/link";
import { usePrelabelBatches } from "@/hooks/use-prelabel-batch";
import { Spinner } from "@/components/ui";

/**
 * Landing page for an initial validation batch's hand-off to an Annotator Admin.
 *
 * `initial`, not `large`: annotation-workflow-review-simplification moved the reviewed batch
 * from the main run to the small validation batch, and removed review from the main run
 * entirely — a `large` batch is promoted automatically the moment pre-labeling finishes. This
 * screen now lists the initial batches waiting on an Annotator Admin's validation, which is
 * what unlocks the tenant admin's large-batch upload step.
 */
export default function ReviewBatchLandingPage() {
  const { data, isLoading } = usePrelabelBatches();

  const pending = (data?.batches ?? []).filter(
    (b) =>
      b.batch_kind === "initial" &&
      (b.state === "completed" || b.state === "partially_completed") &&
      b.annotator_review_status !== "approved" &&
      b.acceptance_decision !== "rejected",
  );

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="font-display text-2xl font-semibold" style={{ color: "var(--ink)" }}>
          Batch Review
        </h1>
        <p className="font-body text-sm mt-1" style={{ color: "var(--ink-2)" }}>
          Initial validation batches a Tenant Admin has pre-labeled and handed off for your
          review. Approving one unlocks the large batch — which needs no further review.
        </p>
      </div>

      {isLoading ? (
        <Spinner size="sm" />
      ) : pending.length === 0 ? (
        <p className="font-body text-sm" style={{ color: "var(--ink-3)" }}>
          Nothing waiting on you right now.
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {pending.map((batch) => (
            <Link
              key={batch.batch_id}
              href={`/annotate/review-batch/${batch.batch_id}`}
              className="flex items-center justify-between rounded-lg border border-border p-3 font-body text-sm hover:bg-surface-2"
              style={{ background: "var(--surface-1)" }}
            >
              <span style={{ color: "var(--ink)" }}>
                Batch {batch.batch_id.slice(0, 8)}
              </span>
              <span style={{ color: "var(--ink-3)" }}>
                {batch.created_at ? new Date(batch.created_at).toLocaleString() : "—"}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
