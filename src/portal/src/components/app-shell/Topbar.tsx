"use client";

import { usePathname } from "next/navigation";
import Image from "next/image";
import { useAuth } from "@/lib/auth";
import { useDarkMode } from "@/hooks";
import { SCREEN_TITLES, SCREEN_TITLES_FALLBACK } from "@/lib/nav-config";
import { Sun, Moon } from "lucide-react";

function resolveScreen(pathname: string): [string, string] {
  for (const [, value] of Object.entries(SCREEN_TITLES)) {
    if (pathname === value[1] || pathname.startsWith(value[1] + "/")) {
      return value;
    }
  }
  return SCREEN_TITLES_FALLBACK;
}

export function Topbar() {
  const { user } = useAuth();
  const pathname = usePathname();
  const { dark, toggle } = useDarkMode();

  if (!user) return null;

  const [title] = resolveScreen(pathname);

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
