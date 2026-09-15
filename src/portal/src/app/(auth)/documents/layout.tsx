import { ReactNode } from "react";
import { RequireAuth } from "@/components/require-auth";
import { DataPlaneGate } from "@/components/data-plane/data-plane-gate";

export default function DocumentsLayout({ children }: { children: ReactNode }) {
  return (
    <RequireAuth roles={["tenant_admin", "annotator", "business_user"]}>
      <DataPlaneGate>{children}</DataPlaneGate>
    </RequireAuth>
  );
}
