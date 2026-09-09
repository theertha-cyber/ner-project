"use client";

import { ReactNode } from "react";
import { RequireAuth } from "@/components/require-auth";
import { useEntityTypes } from "@/hooks/use-entity-types";
import { useRetrainingDecision } from "@/hooks/use-retraining";
import { AutomatedStepper, StepDef } from "@/components/annotate/AutomatedStepper";

export default function AutomatedLayout({ children }: { children: ReactNode }) {
  const entityTypes = useEntityTypes();
  const decision = useRetrainingDecision();

  const hasSchema = (entityTypes.data?.entity_types.filter((e) => e.is_active).length ?? 0) > 0;
  const accumulation =
    decision.data && decision.data.has_trained_model ? decision.data.spans_accumulated : 0;

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
      state: hasSchema ? "ready" : "blocked",
      sub: hasSchema ? undefined : "needs an approved schema",
    },
    {
      num: 3,
      title: "Review Sample",
      href: "/annotate/automated/prelabel?tab=review",
      state: hasSchema ? "ready" : "blocked",
      sub: hasSchema ? "after a batch runs" : "needs a finished batch",
    },
    {
      num: 4,
      title: "Retraining",
      href: "/annotate/automated/retrain",
      state: accumulation > 0 ? "ready" : "blocked",
      sub: accumulation > 0 ? `${accumulation} spans accumulated` : "needs a reviewed batch",
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
