"use client";

import { useState, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import type { AuthUser } from "@/lib/auth";
import { navFor } from "@/lib/nav-config";

function tenantDisplayName(slug: string | null): string {
  if (!slug) return "Platform";
  return slug.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function userInitials(email: string): string {
  return email.slice(0, 2).toUpperCase();
}

interface SidebarProps {
  effectiveRole: AuthUser["role"];
}

export function Sidebar({ effectiveRole }: SidebarProps) {
  const { user, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    function handleEscape(e: KeyboardEvent) {
      if (e.key === "Escape") setMenuOpen(false);
    }
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, []);

  if (!user) return null;

  const navItems = navFor(effectiveRole);
  const tenantName = tenantDisplayName(user.tenantSlug);
  const tenantInitial = tenantName[0].toUpperCase();
  const initials = userInitials(user.email);
  const roleLabel = user.role.replace(/_/g, " ");

  return (
    <aside
      style={{
        width: 248,
        minWidth: 248,
        maxWidth: 248,
        position: "sticky",
        top: 0,
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        background: "var(--surface-2)",
        borderRight: "1px solid var(--line)",
      }}
    >
      {/* Logo block */}
      <div style={{ padding: "20px 16px 12px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 30,
              height: 30,
              borderRadius: 8,
              background: "var(--primary)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: "var(--font-display, sans-serif)",
              fontWeight: 800,
              fontSize: 17,
              color: "#fff",
              flexShrink: 0,
            }}
          >
            n
          </div>
          <span
            style={{
              fontFamily: "var(--font-display, sans-serif)",
              fontWeight: 700,
              fontSize: 16,
              color: "var(--ink)",
              letterSpacing: "-0.02em",
            }}
          >
            nerplatform
          </span>
        </div>
      </div>

      {/* Tenant pill */}
      <div style={{ padding: "0 12px 14px" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "9px 11px",
            borderRadius: 12,
            border: "1px solid var(--line)",
            background: "var(--surface-3)",
            cursor: "default",
            transition: "border-color 0.15s",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLDivElement).style.borderColor = "var(--primary-line)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLDivElement).style.borderColor = "var(--line)";
          }}
        >
          <div
            style={{
              width: 26,
              height: 26,
              borderRadius: 7,
              background: "var(--primary-soft)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: "var(--font-mono, monospace)",
              fontWeight: 700,
              fontSize: 13,
              color: "var(--primary-2)",
              flexShrink: 0,
            }}
          >
            {tenantInitial}
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div
              style={{
                fontFamily: "var(--font-display, sans-serif)",
                fontWeight: 600,
                fontSize: 12.5,
                color: "var(--ink)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {tenantName}
            </div>
            <div
              style={{
                fontFamily: "var(--font-mono, monospace)",
                fontSize: 10,
                color: "var(--ink-3)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {user.tenantSlug ?? "—"}
            </div>
          </div>
          <span style={{ fontSize: 11, color: "var(--ink-3)", flexShrink: 0 }}>▾</span>
        </div>
      </div>

      {/* Nav section */}
      <nav style={{ flex: 1, overflowY: "auto", padding: "4px 12px" }}>
        {navItems.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <button
              key={item.id}
              onClick={() => router.push(item.href)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                width: "100%",
                padding: "9px 11px",
                borderRadius: 10,
                border: "none",
                background: isActive ? "var(--primary)" : "transparent",
                color: isActive ? "#fff" : "var(--ink-2)",
                fontFamily: "var(--font-display, sans-serif)",
                fontSize: 13.5,
                fontWeight: isActive ? 600 : 400,
                cursor: "pointer",
                textAlign: "left",
                marginBottom: 2,
                transition: "background 0.12s, color 0.12s",
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  (e.currentTarget as HTMLButtonElement).style.background = "var(--surface-3)";
                  (e.currentTarget as HTMLButtonElement).style.color = "var(--ink)";
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  (e.currentTarget as HTMLButtonElement).style.background = "transparent";
                  (e.currentTarget as HTMLButtonElement).style.color = "var(--ink-2)";
                }
              }}
            >
              <span style={{ fontSize: 15, lineHeight: 1, flexShrink: 0 }}>{item.icon}</span>
              <span style={{ flex: 1 }}>{item.label}</span>
              {item.badge != null && (
                <span
                  style={{
                    fontFamily: "var(--font-mono, monospace)",
                    fontSize: 10,
                    fontWeight: 600,
                    padding: "1px 6px",
                    borderRadius: 20,
                    background: isActive ? "rgba(255,255,255,0.25)" : "var(--primary-soft)",
                    color: isActive ? "#fff" : "var(--primary)",
                    flexShrink: 0,
                  }}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* User strip — full-width trigger button */}
      <div style={{ borderTop: "1px solid var(--line)", padding: "12px" }}>
        <button
          onClick={() => setMenuOpen((prev) => !prev)}
          aria-haspopup="true"
          aria-expanded={menuOpen}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            width: "100%",
            padding: "7px 8px",
            borderRadius: 11,
            border: menuOpen ? "1px solid var(--primary-line)" : "1px solid transparent",
            background: menuOpen ? "var(--primary-soft)" : "transparent",
            cursor: "pointer",
            textAlign: "left",
            transition: "border-color 0.15s, background 0.15s",
          }}
        >
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 9,
              background: "linear-gradient(135deg, var(--primary), var(--primary-2))",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: "var(--font-display, sans-serif)",
              fontWeight: 700,
              fontSize: 12,
              color: "#fff",
              flexShrink: 0,
            }}
          >
            {initials}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontSize: 12,
                fontWeight: 500,
                color: "var(--ink)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {user.email}
            </div>
            <div
              style={{
                fontFamily: "var(--font-mono, monospace)",
                fontSize: 10,
                color: "var(--ink-3)",
              }}
            >
              {roleLabel}
            </div>
          </div>
          <span
            style={{
              width: 24,
              height: 24,
              borderRadius: 7,
              background: "var(--surface-2)",
              border: "1px solid var(--line)",
              display: "grid",
              placeItems: "center",
              color: "var(--ink-2)",
              fontSize: 9,
              flexShrink: 0,
              transition: "transform 0.18s ease",
              transform: menuOpen ? "rotate(180deg)" : "rotate(0deg)",
            }}
          >
            ▾
          </span>
        </button>
      </div>

      {/* Backdrop — covers viewport below menu (z-index 60) */}
      {menuOpen && (
        <div
          onClick={() => setMenuOpen(false)}
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            zIndex: 60,
          }}
        />
      )}

      {/* Floating menu panel (z-index 61, above backdrop) */}
      {menuOpen && (
        <div
          className="animate-menu-pop"
          style={{
            position: "absolute",
            left: 12,
            right: 12,
            bottom: 62,
            zIndex: 61,
            transformOrigin: "bottom center",
            background: "var(--surface-2)",
            border: "1px solid var(--line)",
            borderRadius: 8,
            padding: 4,
            boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
          }}
        >
          <button
            onClick={() => { router.push("/settings"); setMenuOpen(false); }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              width: "100%",
              padding: "8px 10px",
              borderRadius: 6,
              border: "none",
              background: "transparent",
              color: "var(--ink)",
              fontFamily: "var(--font-display, sans-serif)",
              fontSize: 13,
              cursor: "pointer",
              textAlign: "left",
            }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "var(--surface-3)"; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "transparent"; }}
          >
            <span style={{ fontSize: 15, lineHeight: 1 }}>⚙</span>
            <span>Settings</span>
          </button>
          <button
            onClick={async () => { await logout(); router.push("/login"); }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              width: "100%",
              padding: "8px 10px",
              borderRadius: 6,
              border: "none",
              background: "transparent",
              color: "var(--bad)",
              fontFamily: "var(--font-display, sans-serif)",
              fontSize: 13,
              cursor: "pointer",
              textAlign: "left",
            }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "var(--bad-soft)"; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "transparent"; }}
          >
            <span style={{ fontSize: 15, lineHeight: 1 }}>⎋</span>
            <span>Logout</span>
          </button>
        </div>
      )}
    </aside>
  );
}
