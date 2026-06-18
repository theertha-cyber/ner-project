import { ReactNode } from "react";
import { RequireAuth } from "@/components/require-auth";
import { AppShell } from "@/components/app-shell";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div style={{ animation: "dashFadeIn 0.4s ease both" }}>
      <RequireAuth>
        <AppShell>{children}</AppShell>
      </RequireAuth>
    </div>
  );
}
