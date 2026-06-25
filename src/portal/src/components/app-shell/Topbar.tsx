"use client";

import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useDarkMode } from "@/hooks";
import { SCREEN_TITLES, SCREEN_TITLES_FALLBACK } from "@/lib/nav-config";
import type { AuthUser } from "@/lib/auth";

function resolveScreen(pathname: string): [string, string] {
  for (const [, value] of Object.entries(SCREEN_TITLES)) {
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

  return (
    <header
      style={{
        height: 62,
        minHeight: 62,
        display: "flex",
        alignItems: "center",
        padding: "0 20px",
        borderBottom: "1px solid var(--line)",
        background: "var(--surface-2)",
        position: "sticky",
        top: 0,
        zIndex: 50,
        gap: 16,
      }}
    >
      {/* Screen title + path — side by side with baseline alignment */}
      <div style={{ display: "flex", alignItems: "baseline", gap: 9 }}>
        <span
          style={{
            fontFamily: "var(--font-display, sans-serif)",
            fontWeight: 700,
            fontSize: 16,
            color: "var(--ink)",
            lineHeight: 1.2,
          }}
        >
          {title}
        </span>
        <span
          style={{
            fontFamily: "var(--font-mono, monospace)",
            fontSize: 11,
            color: "var(--ink-3)",
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
          padding: "7px 12px",
          borderRadius: 10,
          border: "1px solid var(--line)",
          background: "var(--surface-3)",
          fontFamily: "var(--font-mono, monospace)",
          fontSize: 12,
          color: "var(--ink-3)",
          cursor: "default",
          userSelect: "none",
          width: 230,
        }}
      >
        ⌕ search · ⌘K
      </div>

      {/* Role-switcher chips — demo mode only, wrapped in pill container */}
      {process.env.NEXT_PUBLIC_DEMO_MODE === "true" && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 3,
            background: "var(--surface-3)",
            border: "1px solid var(--line)",
            borderRadius: 10,
            padding: 3,
          }}
        >
          {/* AS: static session label */}
          <span
            style={{
              fontFamily: "var(--font-mono, monospace)",
              fontSize: 10,
              color: "var(--ink-3)",
              userSelect: "none",
              padding: "0 6px",
            }}
          >
            AS
          </span>
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
                  borderColor: active ? "var(--primary)" : "transparent",
                  background: active ? "var(--primary)" : "transparent",
                  color: active ? "#fff" : "var(--ink-3)",
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
          borderRadius: 10,
          border: "1px solid var(--line)",
          background: "transparent",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 16,
          color: "var(--ink-3)",
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
          borderRadius: 10,
          background: "linear-gradient(135deg, var(--primary), var(--primary-2))",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "var(--font-display, sans-serif)",
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
