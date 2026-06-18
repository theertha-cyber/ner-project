"use client";

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
        background: "var(--color-glass, rgba(255,255,255,0.85))",
        borderRight: "1px solid rgba(0,0,0,0.08)",
        backdropFilter: "blur(16px)",
      }}
    >
      {/* Logo block */}
      <div style={{ padding: "20px 16px 12px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: 8,
              background: "var(--color-brand-primary, #c2410c)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: "var(--font-display, sans-serif)",
              fontWeight: 700,
              fontSize: 18,
              color: "#fff",
              flexShrink: 0,
            }}
          >
            n
          </div>
          <span
            style={{
              fontFamily: "var(--font-display, sans-serif)",
              fontWeight: 600,
              fontSize: 14,
              color: "var(--color-text-primary, #0f172a)",
              letterSpacing: "-0.01em",
            }}
          >
            nerplatform
          </span>
        </div>
      </div>

      {/* Tenant pill */}
      <div style={{ padding: "0 12px 16px" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 10px",
            borderRadius: 8,
            border: "1px solid transparent",
            cursor: "default",
            transition: "border-color 0.15s",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(0,0,0,0.12)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLDivElement).style.borderColor = "transparent";
          }}
        >
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 6,
              background: "var(--color-brand-primary, #c2410c)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: "var(--font-mono, monospace)",
              fontWeight: 700,
              fontSize: 13,
              color: "#fff",
              flexShrink: 0,
            }}
          >
            {tenantInitial}
          </div>
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                fontFamily: "var(--font-display, sans-serif)",
                fontWeight: 500,
                fontSize: 12,
                color: "var(--color-text-primary, #0f172a)",
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
                color: "var(--color-text-secondary, #64748b)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {user.tenantSlug ?? "—"}
            </div>
          </div>
        </div>
      </div>

      {/* Nav section */}
      <nav style={{ flex: 1, overflowY: "auto", padding: "0 8px" }}>
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
                padding: "9px 10px",
                borderRadius: 7,
                border: "none",
                background: isActive
                  ? "var(--color-brand-primary, #c2410c)"
                  : "transparent",
                color: isActive ? "#fff" : "var(--color-text-secondary, #64748b)",
                fontFamily: "var(--font-display, sans-serif)",
                fontSize: 13,
                fontWeight: isActive ? 600 : 400,
                cursor: "pointer",
                textAlign: "left",
                marginBottom: 2,
                transition: "background 0.12s, color 0.12s",
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  (e.currentTarget as HTMLButtonElement).style.background = "rgba(0,0,0,0.05)";
                  (e.currentTarget as HTMLButtonElement).style.color = "var(--color-text-primary, #0f172a)";
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  (e.currentTarget as HTMLButtonElement).style.background = "transparent";
                  (e.currentTarget as HTMLButtonElement).style.color = "var(--color-text-secondary, #64748b)";
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
                    background: isActive ? "rgba(255,255,255,0.25)" : "rgba(194,65,12,0.12)",
                    color: isActive ? "#fff" : "var(--color-brand-primary, #c2410c)",
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

      {/* User strip */}
      <div
        style={{
          borderTop: "1px solid rgba(0,0,0,0.08)",
          padding: "12px 12px",
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 6,
            background: "linear-gradient(135deg, var(--color-brand-primary, #c2410c), #f59e0b)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: "var(--font-mono, monospace)",
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
              color: "var(--color-text-primary, #0f172a)",
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
              color: "var(--color-text-secondary, #64748b)",
            }}
          >
            {roleLabel}
          </div>
        </div>
        <button
          onClick={async () => {
            await logout();
            router.push("/login");
          }}
          title="Sign out"
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            fontSize: 16,
            color: "var(--color-text-secondary, #64748b)",
            padding: "4px",
            borderRadius: 4,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          ⎋
        </button>
      </div>
    </aside>
  );
}
