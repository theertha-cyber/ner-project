"use client";

import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useDarkMode } from "@/hooks";
import { SCREEN_TITLES, SCREEN_TITLES_FALLBACK } from "@/lib/nav-config";

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

export function Topbar() {
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
