"use client";

import { ReactNode } from "react";
import { RequireAuth } from "@/components/require-auth";
import { useEntityTypes } from "@/hooks/use-entity-types";
import { useRetrainingDecision } from "@/hooks/use-retraining";
import { usePrelabelBatches } from "@/hooks/use-prelabel-batch";
import { AutomatedStepper, StepDef, StepState } from "@/components/annotate/AutomatedStepper";

export default function AutomatedLayout({ children }: { children: ReactNode }) {
  const entityTypes = useEntityTypes();
  const decision = useRetrainingDecision();
  const batches = usePrelabelBatches();

  const hasSchema = (entityTypes.data?.entity_types.filter((e) => e.is_active).length ?? 0) > 0;

  const rows = batches.data?.batches ?? [];
  const anyBatch = rows.length > 0;
  const anyProcessing = rows.some((b) => b.state === "processing" || b.status === "queued");
  const anyFinished = rows.some(
    (b) => b.state === "completed" || b.state === "partially_completed" || b.state === "failed",
  );
  const anyReviewed = rows.some((b) => b.acceptance_decision != null);
  const anyApprovedLarge = rows.some(
    (b) => b.batch_kind === "large" && b.annotator_review_status === "approved",
  );
  const accumulation =
    decision.data && decision.data.has_trained_model ? decision.data.spans_accumulated : 0;

  const step = (done: boolean, unlocked: boolean, current = false): StepState =>
    done ? "done" : current ? "current" : unlocked ? "ready" : "blocked";

  const steps: StepDef[] = [
    {
      num: 1,
      title: "Suggest Entity Types",
      href: "/annotate/automated/schema",
      state: hasSchema ? "done" : "ready",
      sub: hasSchema ? "schema approved" : "pick seed documents",
    },
    {
      num: 2,
      title: "Batch Pre-labeling",
      href: "/annotate/automated/prelabel",
      state: step(anyBatch && !anyProcessing, hasSchema, anyProcessing),
      sub: !hasSchema
        ? "needs an approved schema"
        : anyProcessing
          ? "a batch is running"
          : anyBatch
            ? undefined
            : "no batch yet",
    },
    {
      num: 3,
      title: "Review Sample",
      href: "/annotate/automated/prelabel?tab=review",
      state: step(anyApprovedLarge || anyReviewed, anyFinished),
      sub: anyFinished ? undefined : "needs a finished batch",
    },
    {
      num: 4,
      title: "Retraining",
      href: "/annotate/automated/retrain",
      state: step(false, anyApprovedLarge || accumulation > 0),
      sub: anyApprovedLarge
        ? "an approved batch is training-eligible"
        : accumulation > 0
          ? `${accumulation} spans accumulated`
          : "needs a reviewed batch",
    },
  ];

  return (
    <RequireAuth roles={["tenant_admin"]}>
      <div className="animate-fade-up" style={{ maxWidth: 960 }}>
        <AutomatedStepper steps={steps} />
        {children}
      </div>
    </RequireAuth>
  );
}
