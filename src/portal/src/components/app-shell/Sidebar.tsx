"use client";

import { useState, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import type { AuthUser } from "@/lib/auth";
import { navFor } from "@/lib/nav-config";
import { Settings, LogOut, ChevronDown, PanelLeft } from "lucide-react";

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
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    function handleEscape(e: KeyboardEvent) {
      if (e.key === "Escape") setMenuOpen(false);
    }
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, []);

  if (!user) return null;

  const navItems = navFor(effectiveRole);
  const initials = userInitials(user.email);
  const roleLabel = user.role.replace(/_/g, " ");

  return (
    <aside
      style={{
        width: collapsed ? 72 : 248,
        minWidth: collapsed ? 72 : 248,
        maxWidth: collapsed ? 72 : 248,
        position: "sticky",
        top: 0,
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        background: "var(--surface-2)",
        borderRight: "1px solid var(--line)",
        transition: "width 0.15s ease, min-width 0.15s ease, max-width 0.15s ease",
      }}
    >
      {/* Logo block — height matches Topbar (62px) so the two bottom borders line up */}
      <div
        style={{
          height: 62,
          minHeight: 62,
          display: "flex",
          alignItems: "center",
          justifyContent: collapsed ? "center" : "space-between",
          gap: 10,
          padding: collapsed ? "0 12px" : "0 12px 0 16px",
          borderBottom: "1px solid var(--line)",
        }}
      >
        {!collapsed && (
          <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
            <div
              style={{
                width: 30,
                height: 30,
                borderRadius: 8,
                background: "var(--primary)",
                display: "grid",
                placeItems: "center",
                fontFamily: "var(--font-display, sans-serif)",
                fontWeight: 800,
                fontSize: 17,
                lineHeight: 1,
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
                lineHeight: 1.2,
                color: "var(--ink)",
                letterSpacing: "-0.02em",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              NER Platform
            </span>
          </div>
        )}
        <button
          onClick={() => setCollapsed((prev) => !prev)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          style={{
            width: 28,
            height: 28,
            borderRadius: 7,
            border: "none",
            background: "transparent",
            display: "grid",
            placeItems: "center",
            color: "var(--ink-2)",
            cursor: "pointer",
            flexShrink: 0,
            transition: "background 0.12s, color 0.12s",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = "var(--surface-3)";
            (e.currentTarget as HTMLButtonElement).style.color = "var(--ink)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = "transparent";
            (e.currentTarget as HTMLButtonElement).style.color = "var(--ink-2)";
          }}
        >
          <PanelLeft size={17} strokeWidth={2} />
        </button>
      </div>

      {/* Nav section */}
      <nav style={{ flex: 1, overflowY: "auto", padding: "10px 12px" }}>
        {navItems.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <button
              key={item.id}
              onClick={() => router.push(item.href)}
              title={collapsed ? item.label : undefined}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: collapsed ? "center" : "flex-start",
                gap: 10,
                width: "100%",
                padding: collapsed ? "9px" : "9px 11px",
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
              <item.icon size={16} strokeWidth={2} style={{ flexShrink: 0 }} />
              {!collapsed && <span style={{ flex: 1 }}>{item.label}</span>}
              {!collapsed && item.badge != null && (
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
          title={collapsed ? user.email : undefined}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: collapsed ? "center" : "flex-start",
            gap: 8,
            width: "100%",
            padding: collapsed ? "7px" : "7px 8px",
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
          {!collapsed && (
            <>
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
                  flexShrink: 0,
                  transition: "transform 0.18s ease",
                  transform: menuOpen ? "rotate(180deg)" : "rotate(0deg)",
                }}
              >
                <ChevronDown size={13} strokeWidth={2.25} />
              </span>
            </>
          )}
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
            right: collapsed ? "auto" : 12,
            width: collapsed ? 180 : "auto",
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
            <Settings size={15} strokeWidth={2} />
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
            <LogOut size={15} strokeWidth={2} />
            <span>Logout</span>
          </button>
        </div>
      )}
    </aside>
  );
}
