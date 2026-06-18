import { ReactNode } from "react";
import { RequireAuth } from "@/components/require-auth";

export default function AdminLayout({ children }: { children: ReactNode }) {
  return <RequireAuth roles={["system_admin"]}>{children}</RequireAuth>;
}
