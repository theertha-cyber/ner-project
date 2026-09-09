"use client";

import { useRouter } from "next/navigation";
import { AnnotateLanding } from "@/components/annotate/AnnotateLanding";

export default function AutomatedLandingPage() {
  const router = useRouter();
  return (
    <AnnotateLanding
      heading="Automated annotation"
      intro="Choose this when you have volume and a repeatable document shape — the model drafts, you spot-check instead of label. The stepper above is the glance: each step carries its own state."
      primaryAction={{
        label: "Start with step 1",
        onClick: () => router.push("/annotate/automated/schema"),
      }}
    >
      <p style={{ fontSize: 12.5, color: "var(--ink-3)", marginTop: 18, maxWidth: 620, lineHeight: 1.6 }}>
        Runs go in order. A schema proposal has to be approved before a batch can be pre-labeled;
        a batch has to be reviewed by an annotator before retraining unlocks. Step 1 needs at
        least 3 processed seed documents.
      </p>
    </AnnotateLanding>
  );
}
