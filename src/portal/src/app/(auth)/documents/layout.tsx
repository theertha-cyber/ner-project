import { ReactNode } from "react";
import { RequireAuth } from "@/components/require-auth";

export default function DocumentsLayout({ children }: { children: ReactNode }) {
  return <RequireAuth roles={["tenant_admin", "annotator", "business_user"]}>{children}</RequireAuth>;
}
