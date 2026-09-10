"use client";

import { useParams, useRouter } from "next/navigation";
import { RequireAuth } from "@/components/require-auth";
import { ImportedDocumentReview } from "../page";

/**
 * A single imported row, reviewed against the schema it claims to follow. Reached by a
 * deep link (e.g. from a notification or a bookmark); the list view still opens it inline.
 */
export default function ImportedRowReviewRoute() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  return (
    <RequireAuth roles={["annotator", "tenant_admin"]}>
      <ImportedDocumentReview
        annotationId={params.id}
        onBack={() => router.push("/imported-documents")}
      />
    </RequireAuth>
  );
}
