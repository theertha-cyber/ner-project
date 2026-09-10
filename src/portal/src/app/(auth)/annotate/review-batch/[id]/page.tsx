"use client";

import { useParams } from "next/navigation";
import { RequireAuth } from "@/components/require-auth";
import { BatchAcceptancePage } from "@/components/seed-bootstrap/BatchAcceptancePage";

/**
 * The Annotator Admin's final review of a `large` automated batch. Reached from the
 * completion notification; opens straight on the batch's acceptance review.
 */
export default function ReviewBatchRoute() {
  const params = useParams<{ id: string }>();
  return (
    <RequireAuth roles={["annotator", "tenant_admin"]}>
      <div className="animate-fade-up">
        <BatchAcceptancePage initialBatchId={params.id} reviewOnly />
      </div>
    </RequireAuth>
  );
}
