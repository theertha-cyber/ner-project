"use client";

import { useRouter } from "next/navigation";
import { AnnotateLanding, WorkCard } from "@/components/annotate/AnnotateLanding";

export default function AutomatedLandingPage() {
  const router = useRouter();

  // Step 1 (Suggest Entity Types) reads from seed documents already sitting in the tenant's
  // library — nothing here uploads them. Without these two cards a new tenant admin has no
  // visible path to get documents in before the stepper's first step is even unlocked.
  const workCards: WorkCard[] = [
    {
      title: "Upload documents",
      description: "Add the seed documents step 1 will draft a schema from.",
      cta: "Upload documents",
      href: "/documents?upload=1&purpose=training&mode=automated",
    },
    {
      title: "Upload Q&A pair",
      description: "Optional guidance that sharpens which entity types get suggested.",
      cta: "Upload Q&A pair",
      href: "/documents?upload=1&purpose=qa_pair",
    },
  ];

  return (
    <AnnotateLanding
      heading="Automated annotation"
      intro="Choose this when you have volume and a repeatable document shape — the model drafts, you spot-check instead of label. The stepper above is the glance: each step carries its own state."
      primaryAction={{
        label: "Start with step 1",
        onClick: () => router.push("/annotate/automated/schema"),
      }}
      primaryActionPosition="belowWorkCards"
      workCards={workCards}
      workCardsLabel="Before you begin"
    >
      <p style={{ fontSize: 12.5, color: "var(--ink-3)", marginTop: 18, maxWidth: 620, lineHeight: 1.6 }}>
        These three steps go in order: a schema proposal has to be approved before a batch can
        be pre-labeled, and a batch has to be reviewed by an annotator before it&apos;s training-
        eligible. Step 1 needs at least 3 processed seed documents. Retraining itself is a
        separate, optional decision — once you have a reviewed batch or a serving model, find it
        under Models &amp; Training rather than as a step here.
      </p>
    </AnnotateLanding>
  );
}
