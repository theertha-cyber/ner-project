"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useEntityTypes } from "@/hooks/use-entity-types";
import { useImportFiles } from "@/hooks/use-import-files";
import { AnnotateLanding, GlanceStat, WorkCard } from "@/components/annotate/AnnotateLanding";

export default function ImportAnnotationLanding() {
  const router = useRouter();
  const { user } = useAuth();
  const isAnnotator = user?.role === "annotator";
  const entityTypes = useEntityTypes();
  const entityCount = entityTypes.data?.entity_types.length ?? 0;
  const files = useImportFiles(user?.role === "tenant_admin");

  const fileList = files.data?.files ?? [];
  const pendingRows = fileList.reduce((n, f) => n + f.pending_count, 0);
  const eligibleFiles = fileList.filter((f) => f.training_eligible).length;

  const stats: GlanceStat[] = isAnnotator
    ? [{ label: "entity types defined", value: entityCount, href: "/entity-types" }]
    : [
        { label: "files imported", value: fileList.length, href: "/imported-documents" },
        {
          label: "rows need type mapping",
          value: pendingRows,
          tone: pendingRows > 0 ? "warn" : "default",
          href: "/imported-documents",
        },
        { label: "files training-eligible", value: eligibleFiles, tone: "good", href: "/imported-documents" },
      ];

  const workCards: WorkCard[] = [
    {
      title: "Imported files",
      description: "Rows that arrived pre-labelled, with the count still needing a type mapping or a human pass.",
      cta: "Open imported files",
      href: "/imported-documents",
      count: pendingRows || undefined,
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
      stats={stats}
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
