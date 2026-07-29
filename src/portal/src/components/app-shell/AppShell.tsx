"use client";

import { useAuth } from "@/lib/auth";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const { user } = useAuth();

  if (!user) return <>{children}</>;

  return (
    <div style={{ display: "flex", height: "100vh", background: "var(--color-surface-page, #f1f3f7)" }}>
      <Sidebar effectiveRole={user.role} />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <Topbar />
        <main style={{ flex: 1, padding: "24px 28px", overflow: "auto" }}>{children}</main>
      </div>
    </div>
  );
}
