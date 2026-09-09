"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useEntityTypes } from "@/hooks/use-entity-types";
import { AnnotateLanding, WorkCard } from "@/components/annotate/AnnotateLanding";

export default function ImportAnnotationLanding() {
  const router = useRouter();
  const { user } = useAuth();
  const isAnnotator = user?.role === "annotator";
  const entityTypes = useEntityTypes();
  const entityCount = entityTypes.data?.entity_types.length ?? 0;

  const workCards: WorkCard[] = [
    {
      title: "Imported files",
      description: "Rows that arrived pre-labelled, with the count still needing a human pass.",
      cta: "Open imported files",
      href: "/imported-documents",
    },
  ];

  return (
    <AnnotateLanding
      heading="Import annotations"
      intro="Choose this when the labels already exist — a vendor export, a gold set from another tool, or a previous NER project. Imported rows skip labeling and go straight to review."
      primaryAction={
        isAnnotator
          ? undefined
          : { label: "＋ Import file", onClick: () => router.push("/imported-documents?import=1") }
      }
      stats={[
        { label: "entity types defined", value: entityCount, note: "more defined means less mapping after import", href: "/entity-types" },
      ]}
      workCards={workCards}
    >
      <p style={{ fontSize: 12.5, color: "var(--ink-3)", marginTop: 18, maxWidth: 620, lineHeight: 1.6 }}>
        Supported formats: <code>.txt</code>, <code>.json</code>, <code>.jsonl</code> (token/tag rows).
        Entity types found in your file that aren&apos;t defined yet are flagged for mapping —
        never created silently.
      </p>
    </AnnotateLanding>
  );
}
