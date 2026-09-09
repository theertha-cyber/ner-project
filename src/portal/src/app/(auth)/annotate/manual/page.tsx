"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useDocuments } from "@/hooks/use-documents";
import { useEntityTypes } from "@/hooks/use-entity-types";
import { useReviewQueue } from "@/hooks/use-review-queue";
import { AnnotateLanding, GlanceStat, WorkCard } from "@/components/annotate/AnnotateLanding";

export default function ManualAnnotationLanding() {
  const router = useRouter();
  const { user } = useAuth();
  const isAnnotator = user?.role === "annotator";

  const docs = useDocuments(1, 1, "processed");
  const entityTypes = useEntityTypes();
  const queue = useReviewQueue(1, 0);

  const docCount = docs.data?.total ?? 0;
  const entityCount = entityTypes.data?.entity_types.length ?? 0;
  const awaitingReview = queue.data?.total ?? 0;

  const workCards: WorkCard[] = [
    {
      title: "Annotation workspace",
      description: "Label documents span by span in the three-pane editor.",
      cta: "Open workspace",
      href: "/annotation",
    },
    {
      title: "Review queue",
      description: "Confirm or correct the model's low-confidence spans.",
      cta: "Open queue",
      href: "/review-queue",
      count: awaitingReview,
    },
  ];

  const stats: GlanceStat[] = isAnnotator
    ? [
        { label: "assigned to me", value: "—", href: "/annotation" },
        { label: "submitted, awaiting review", value: awaitingReview, href: "/review-queue" },
      ]
    : [
        { label: "predictions awaiting review", value: awaitingReview, href: "/review-queue" },
        { label: "documents ready", value: docCount, href: "/documents" },
        { label: "entity types defined", value: entityCount, href: "/entity-types" },
      ];

  const missing: string[] = [];
  if (!isAnnotator) {
    if (docCount === 0) missing.push("no processed documents");
    if (entityCount === 0) missing.push("no entity types defined");
  }

  return (
    <AnnotateLanding
      heading="Manual annotation"
      intro="Choose this when documents need a human eye — new formats, edge cases, or the gold set the model will be judged on."
      primaryAction={
        isAnnotator
          ? { label: "Open my queue", onClick: () => router.push("/review-queue") }
          : {
              label: "＋ Assign task",
              onClick: () => router.push("/annotation?assign=1"),
              disabled: missing.length > 0,
              disabledReason: missing.length > 0 ? `Blocked: ${missing.join(", ")}` : undefined,
            }
      }
      stats={stats}
      workCards={workCards}
    />
  );
}
