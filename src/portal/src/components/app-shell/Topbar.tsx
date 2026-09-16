"use client";

import { usePathname } from "next/navigation";
import Image from "next/image";
import { useAuth } from "@/lib/auth";
import { useDarkMode } from "@/hooks";
import { navFor, crumbsFor, resolveScreenTitle } from "@/lib/nav-config";
import { Sun, Moon } from "lucide-react";
import { NotificationBell } from "./NotificationBell";

export function Topbar() {
  const { user } = useAuth();
  const pathname = usePathname();
  const { dark, toggle } = useDarkMode();

  if (!user) return null;

  const [title] = resolveScreenTitle(pathname);
  const crumbs = crumbsFor(navFor(user.role), pathname);

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
      <div style={{ display: "flex", alignItems: "baseline", gap: 7, minWidth: 0 }}>
        {crumbs.length > 1 &&
          crumbs.slice(0, -1).map((c, i) => (
            <span key={i} style={{ display: "flex", alignItems: "baseline", gap: 7 }}>
              <span
                style={{
                  fontFamily: "var(--font-display, sans-serif)",
                  fontSize: 13,
                  color: "var(--ink-3)",
                  whiteSpace: "nowrap",
                }}
              >
                {c.label}
              </span>
              <span style={{ color: "var(--ink-3)", fontSize: 12 }}>/</span>
            </span>
          ))}
        <span
          style={{
            fontFamily: "var(--font-display, sans-serif)",
            fontWeight: 700,
            fontSize: 16,
            color: "var(--ink)",
            lineHeight: 1.2,
            whiteSpace: "nowrap",
          }}
        >
          {crumbs[crumbs.length - 1]?.label ?? title}
        </span>
      </div>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* In-app logo */}
      <Image
        src="/inapp-logo.svg"
        alt="NER Platform"
        width={82}
        height={36}
        style={{ objectFit: "contain", flexShrink: 0 }}
      />

      {(user.role === "tenant_admin" || user.role === "annotator") && <NotificationBell />}

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
          color: "var(--ink-3)",
          flexShrink: 0,
        }}
      >
        {dark ? <Sun size={17} strokeWidth={2} /> : <Moon size={17} strokeWidth={2} />}
      </button>
    </header>
  );
}
