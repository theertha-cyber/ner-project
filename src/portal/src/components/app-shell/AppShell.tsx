"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import type { AuthUser } from "@/lib/auth";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const { user } = useAuth();
  const [demoRole, setDemoRole] = useState<AuthUser["role"] | null>(null);

  if (!user) return <>{children}</>;

  const effectiveRole = demoRole ?? user.role;

  return (
    <div style={{ display: "flex", height: "100vh", background: "var(--color-surface-page, #f1f3f7)" }}>
      <Sidebar effectiveRole={effectiveRole} />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <Topbar demoRole={demoRole} onDemoRoleChange={setDemoRole} />
        <main style={{ flex: 1, padding: "24px 28px", overflow: "auto" }}>{children}</main>
      </div>
    </div>
  );
}
