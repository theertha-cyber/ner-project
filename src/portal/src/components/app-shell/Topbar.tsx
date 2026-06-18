"use client";

import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useDarkMode } from "@/hooks";
import { SCREEN_TITLES, SCREEN_TITLES_FALLBACK, navFor } from "@/lib/nav-config";
import type { AuthUser } from "@/lib/auth";

function resolveScreen(pathname: string): [string, string] {
  for (const [key, value] of Object.entries(SCREEN_TITLES)) {
    if (pathname === value[1] || pathname.startsWith(value[1] + "/")) {
      return value;
    }
  }
  return SCREEN_TITLES_FALLBACK;
}

function userInitials(email: string): string {
  return email.slice(0, 2).toUpperCase();
}

const DEMO_ROLES: { label: string; role: AuthUser["role"] }[] = [
  { label: "SA", role: "system_admin" },
  { label: "TA", role: "tenant_admin" },
  { label: "AN", role: "annotator" },
  { label: "BU", role: "business_user" },
];

interface TopbarProps {
  demoRole: AuthUser["role"] | null;
  onDemoRoleChange: (role: AuthUser["role"]) => void;
}

export function Topbar({ demoRole, onDemoRoleChange }: TopbarProps) {
  const { user } = useAuth();
  const pathname = usePathname();
  const { dark, toggle } = useDarkMode();

  if (!user) return null;

  const [title, path] = resolveScreen(pathname);
  const initials = userInitials(user.email);
  const isDemoMode = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

  return (
    <header
      style={{
        height: 62,
        minHeight: 62,
        display: "flex",
        alignItems: "center",
        padding: "0 20px",
        borderBottom: "1px solid rgba(0,0,0,0.08)",
        background: "var(--color-glass, rgba(255,255,255,0.85))",
        backdropFilter: "blur(16px)",
        zIndex: 50,
        gap: 16,
      }}
    >
      {/* Screen title + path */}
      <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
        <span
          style={{
            fontFamily: "var(--font-display, sans-serif)",
            fontWeight: 700,
            fontSize: 15,
            color: "var(--color-text-primary, #0f172a)",
            lineHeight: 1.2,
          }}
        >
          {title}
        </span>
        <span
          style={{
            fontFamily: "var(--font-mono, monospace)",
            fontSize: 11,
            color: "var(--color-text-secondary, #64748b)",
            lineHeight: 1,
          }}
        >
          {path}
        </span>
      </div>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Search placeholder */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "6px 12px",
          borderRadius: 7,
          border: "1px solid rgba(0,0,0,0.1)",
          background: "rgba(0,0,0,0.03)",
          fontFamily: "var(--font-mono, monospace)",
          fontSize: 12,
          color: "var(--color-text-secondary, #64748b)",
          cursor: "default",
          userSelect: "none",
        }}
      >
        ⌕ search · ⌘K
      </div>

      {/* Role-switcher chips — demo mode only */}
      {process.env.NEXT_PUBLIC_DEMO_MODE === "true" && (
        <div style={{ display: "flex", gap: 4 }}>
          {DEMO_ROLES.map(({ label, role }) => {
            const active = demoRole === role;
            return (
              <button
                key={role}
                onClick={() => onDemoRoleChange(role)}
                style={{
                  fontFamily: "var(--font-mono, monospace)",
                  fontSize: 11,
                  fontWeight: 600,
                  padding: "4px 8px",
                  borderRadius: 5,
                  border: "1px solid",
                  borderColor: active
                    ? "var(--color-brand-primary, #c2410c)"
                    : "rgba(0,0,0,0.12)",
                  background: active
                    ? "var(--color-brand-primary, #c2410c)"
                    : "transparent",
                  color: active ? "#fff" : "var(--color-text-secondary, #64748b)",
                  cursor: "pointer",
                }}
              >
                {label}
              </button>
            );
          })}
        </div>
      )}

      {/* Dark mode toggle */}
      <button
        onClick={toggle}
        title={dark ? "Switch to light mode" : "Switch to dark mode"}
        style={{
          width: 36,
          height: 36,
          borderRadius: 7,
          border: "1px solid rgba(0,0,0,0.1)",
          background: "transparent",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 16,
          color: "var(--color-text-secondary, #64748b)",
          flexShrink: 0,
        }}
      >
        {dark ? "☀" : "☽"}
      </button>

      {/* Avatar */}
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: 7,
          background: "linear-gradient(135deg, var(--color-brand-primary, #c2410c), #f59e0b)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "var(--font-mono, monospace)",
          fontWeight: 700,
          fontSize: 13,
          color: "#fff",
          flexShrink: 0,
          cursor: "default",
        }}
      >
        {initials}
      </div>
    </header>
  );
}
