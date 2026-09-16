"use client";

import { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { RequireAuth } from "@/components/require-auth";
import { useEntityTypes } from "@/hooks/use-entity-types";
import { usePrelabelBatches } from "@/hooks/use-prelabel-batch";
import { AutomatedStepper, StepDef, StepState } from "@/components/annotate/AutomatedStepper";

export default function AutomatedLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const entityTypes = useEntityTypes();
  const batches = usePrelabelBatches();

  // Retraining is a recurring, optional decision, not a 4th step in this pipeline (it can
  // never be "done" the way steps 1-3 can) — it stays reachable at this route, but the
  // 3-step stepper above it would misrepresent it as the next thing in the sequence.
  const showStepper = pathname !== "/annotate/automated/retrain";

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
  ];

  return (
    <RequireAuth roles={["tenant_admin"]}>
      <div className="animate-fade-up" style={{ maxWidth: 960 }}>
        {showStepper && <AutomatedStepper steps={steps} />}
        {children}
      </div>
    </RequireAuth>
  );
}
