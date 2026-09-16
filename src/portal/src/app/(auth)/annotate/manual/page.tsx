"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { authFetch } from "@/lib/auth-fetch";
import { useDocuments } from "@/hooks/use-documents";
import { useEntityTypes } from "@/hooks/use-entity-types";
import { AnnotateLanding, GlanceStat, WorkCard } from "@/components/annotate/AnnotateLanding";
import { AnnotationTask } from "@/components/annotation/TaskQueue";
import { AnnotatedDocuments } from "@/components/annotate/AnnotatedDocuments";
import { TrainModelBanner } from "@/components/annotate/TrainModelBanner";

export default function ManualAnnotationLanding() {
  const router = useRouter();
  const { user } = useAuth();
  const isAnnotator = user?.role === "annotator";

  const docs = useDocuments(1, 1, "processed");
  const entityTypes = useEntityTypes();
  const tasksQuery = useQuery({
    queryKey: ["annotation-tasks"],
    queryFn: async () => {
      const res = await authFetch("/api/v1/annotation-tasks");
      if (!res.ok) throw new Error("Failed to load tasks");
      return res.json() as Promise<AnnotationTask[]>;
    },
  });

  const docCount = docs.data?.total ?? 0;
  const entityCount = entityTypes.data?.entity_types.length ?? 0;
  const allTasks = tasksQuery.data ?? [];
  const myTasks = user ? allTasks.filter((t) => t.annotator_user_id === user.userId) : allTasks;
  const completedTasks = (isAnnotator ? myTasks : allTasks).filter((t) => t.status === "completed");
  const annotatedCount = completedTasks.length;

  // The three steps of the manual workflow, in the order a new user actually does them:
  // get documents in, define what to label them with, then label them.
  const workCards: WorkCard[] = isAnnotator
    ? [
        {
          title: "Annotation workspace",
          description: "Label documents span by span in the three-pane editor.",
          cta: "Open workspace",
          href: "/annotation",
        },
      ]
    : [
        {
          title: "1. Upload documents",
          description: "Add the files that need labeling — PDFs, scans, or text.",
          cta: "Upload documents",
          href: "/documents?upload=1",
        },
        {
          title: "2. Define entity types",
          description: "Decide what to label — the fields the model should learn to find.",
          cta: "Entity types",
          href: "/entity-types",
        },
        {
          title: "3. Annotation workspace",
          description: "Label documents span by span in the three-pane editor.",
          cta: "Open workspace",
          href: "/annotation",
        },
      ];

  const stats: GlanceStat[] = isAnnotator
    ? [
        { label: "assigned to me", value: "—", href: "/annotation" },
        { label: "completed by me", value: annotatedCount, href: "/annotation" },
      ]
    : [
        { label: "documents ready", value: docCount, href: "/documents" },
        { label: "annotated", value: annotatedCount, href: "/annotation" },
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
          ? { label: "Open workspace", onClick: () => router.push("/annotation") }
          : {
              label: "＋ Assign task",
              onClick: () => router.push("/annotation?assign=1"),
              disabled: missing.length > 0,
              disabledReason: missing.length > 0 ? `Blocked: ${missing.join(", ")}` : undefined,
            }
      }
      stats={stats}
      workCards={workCards}
      workCardsLabel={isAnnotator ? "Where the work is" : "Your workflow"}
    >
      <AnnotatedDocuments
        tasks={completedTasks}
        onView={(task) => router.push(`/annotation?task=${task.id}`)}
      />
      {!isAnnotator && (
        <TrainModelBanner
          annotatedCount={annotatedCount}
          onTrain={() => router.push("/training-jobs?source=manual")}
        />
      )}
    </AnnotateLanding>
  );
}
