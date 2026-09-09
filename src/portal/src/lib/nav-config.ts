import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  Hexagon,
  BrainCircuit,
  ScrollText,
  File,
  PenLine,
  FileDown,
  Tags,
  Sparkles,
  Users,
  MessageSquare,
  KeyRound,
  ArrowUpRight,
} from "lucide-react";
import type { AuthUser } from "@/lib/auth";

type Role = AuthUser["role"];

/**
 * The sidebar is a two-level tree. A `link` is a navigable row; a `section` is a
 * non-navigable header grouping links. `children` on a link are the landing page's
 * tab/step sub-screens — they drive breadcrumbs and the landing tab strip, and are
 * deliberately NOT rendered as sidebar rows (see the IA spec: "sub-screens stay out
 * of the sidebar").
 */
export interface NavLeaf {
  kind: "link";
  id: string;
  icon: LucideIcon;
  label: string;
  href: string;
  badge?: number;
  children?: NavLeaf[];
}

export interface NavSection {
  kind: "section";
  id: string;
  label: string;
  items: NavLeaf[];
}

export type NavItem = NavLeaf | NavSection;

function link(
  id: string,
  icon: LucideIcon,
  label: string,
  href: string,
  extra?: { badge?: number; children?: NavLeaf[] },
): NavLeaf {
  return { kind: "link", id, icon, label, href, ...extra };
}

function section(id: string, label: string, items: NavLeaf[]): NavSection {
  return { kind: "section", id, label, items };
}

// ── Shared sub-tree: the three annotation methods ────────────────────────────

function manualLeaf(): NavLeaf {
  return link("annotate-manual", PenLine, "Manual", "/annotate/manual", {
    children: [
      link("annotation", PenLine, "Workspace", "/annotation"),
      link("review-queue", FileDown, "Review Queue", "/review-queue"),
    ],
  });
}

function automatedLeaf(): NavLeaf {
  return link("annotate-automated", Sparkles, "Automated", "/annotate/automated", {
    children: [
      link("auto-schema", Sparkles, "1 · Suggest Entity Types", "/annotate/automated/schema"),
      link("auto-prelabel", BrainCircuit, "2 · Batch Pre-labeling", "/annotate/automated/prelabel"),
      link("auto-review", FileDown, "3 · Review Sample", "/annotate/automated/prelabel?tab=review"),
      link("auto-retrain", BrainCircuit, "4 · Retraining", "/annotate/automated/retrain"),
    ],
  });
}

function importLeaf(): NavLeaf {
  return link("annotate-import", FileDown, "Import", "/annotate/import", {
    children: [link("imported-documents", FileDown, "Imported Files", "/imported-documents")],
  });
}

// ── Per-role trees ──────────────────────────────────────────────────────────

export function navFor(role: Role): NavItem[] {
  switch (role) {
    case "system_admin":
      return [
        link("dashboard", LayoutDashboard, "Dashboard", "/dashboard"),
        link("tenants", Hexagon, "Tenants", "/admin/tenants", { badge: 6 }),
        link("training-jobs", BrainCircuit, "Models & Training", "/training-jobs", { badge: 2 }),
        link("audit", ScrollText, "Audit Log", "/audit"),
      ];

    case "tenant_admin":
      return [
        link("dashboard", LayoutDashboard, "Dashboard", "/dashboard"),
        section("annotate", "Annotate", [manualLeaf(), automatedLeaf(), importLeaf()]),
        section("setup", "Setup", [
          link("documents", File, "Uploaded Documents", "/documents"),
          link("entity-types", Tags, "Entity Types", "/entity-types"),
        ]),
        link("training-jobs", BrainCircuit, "Models & Training", "/training-jobs", { badge: 1 }),
        section("admin", "Admin", [
          link("users", Users, "Create User", "/users"),
          link("widget-keys", KeyRound, "Widget Keys", "/widget-keys"),
          link("chat", MessageSquare, "Chat", "/chat"),
        ]),
      ];

    case "annotator":
      return [
        link("dashboard", LayoutDashboard, "Dashboard", "/dashboard"),
        section("annotate", "Annotate", [manualLeaf(), importLeaf()]),
      ];

    case "business_user":
      return [
        link("dashboard", LayoutDashboard, "Dashboard", "/dashboard"),
        link("documents", File, "Documents", "/documents"),
        link("extractions", ArrowUpRight, "Extractions", "/extractions"),
        link("chat", MessageSquare, "Chat", "/chat"),
      ];
  }
}

// ── Tree helpers ────────────────────────────────────────────────────────────

/** Every navigable link in a role's tree, sections flattened away, children included. */
export function flattenNav(items: NavItem[]): NavLeaf[] {
  const out: NavLeaf[] = [];
  const walk = (leaf: NavLeaf) => {
    out.push(leaf);
    leaf.children?.forEach(walk);
  };
  for (const item of items) {
    if (item.kind === "section") item.items.forEach(walk);
    else walk(item);
  }
  return out;
}

/** Rows the sidebar renders: top-level links + section headers with their direct links. */
export function sidebarRows(items: NavItem[]): NavItem[] {
  return items;
}

export interface Crumb {
  label: string;
  href?: string;
}

/**
 * Breadcrumb trail for a pathname, derived by walking a role's nav tree:
 * section → landing link → sub-screen. Falls back to the flat SCREEN_TITLES map.
 */
export function crumbsFor(items: NavItem[], pathname: string): Crumb[] {
  const matches = (href: string) => {
    const base = href.split("?")[0];
    return pathname === base || pathname.startsWith(base + "/");
  };

  for (const item of items) {
    const sectionLabel = item.kind === "section" ? item.label : null;
    const roots = item.kind === "section" ? item.items : [item];
    for (const root of roots) {
      if (root.children) {
        for (const child of root.children) {
          if (matches(child.href)) {
            const trail: Crumb[] = [];
            if (sectionLabel) trail.push({ label: sectionLabel });
            trail.push({ label: root.label, href: root.href });
            trail.push({ label: child.label });
            return trail;
          }
        }
      }
      if (matches(root.href)) {
        const trail: Crumb[] = [];
        if (sectionLabel) trail.push({ label: sectionLabel });
        trail.push({ label: root.label });
        return trail;
      }
    }
  }

  const [title] = resolveScreenTitle(pathname);
  return [{ label: title }];
}

// ── Flat route → title map (topbar title, breadcrumb fallback) ───────────────

export const SCREEN_TITLES: Record<string, [title: string, path: string]> = {
  dashboard: ["Dashboard", "/dashboard"],
  "annotate-manual": ["Manual Annotation", "/annotate/manual"],
  "annotate-automated": ["Automated Annotation", "/annotate/automated"],
  "annotate-automated-schema": ["Suggest Entity Types", "/annotate/automated/schema"],
  "annotate-automated-prelabel": ["Batch Pre-labeling", "/annotate/automated/prelabel"],
  "annotate-automated-retrain": ["Retraining", "/annotate/automated/retrain"],
  "annotate-import": ["Import Annotations", "/annotate/import"],
  annotation: ["Annotation Workspace", "/annotation"],
  tenants: ["Tenants", "/admin/tenants"],
  "training-jobs": ["Models & Training", "/training-jobs"],
  models: ["Models & Training", "/training-jobs"],
  documents: ["Uploaded Documents", "/documents"],
  "imported-documents": ["Imported Files", "/imported-documents"],
  "review-queue": ["Review Queue", "/review-queue"],
  // Legacy routes — kept so their titles resolve while redirects are in flight.
  "schema-proposals": ["Suggest Entity Types", "/schema-proposals"],
  "prelabel-batches": ["Batch Pre-labeling", "/prelabel-batches"],
  retraining: ["Retraining", "/retraining"],
  "entity-types": ["Entity Types", "/entity-types"],
  users: ["Users", "/users"],
  extractions: ["Extractions", "/extractions"],
  audit: ["Audit Log", "/audit"],
  chat: ["Chat", "/chat"],
  analytics: ["Analytics", "/analytics"],
  settings: ["Settings", "/settings"],
  "widget-keys": ["Widget Keys", "/widget-keys"],
};

export const SCREEN_TITLES_FALLBACK: [string, string] = ["Dashboard", "/dashboard"];

/** Longest-prefix match against SCREEN_TITLES. */
export function resolveScreenTitle(pathname: string): [string, string] {
  let best: [string, string] | null = null;
  for (const value of Object.values(SCREEN_TITLES)) {
    if (pathname === value[1] || pathname.startsWith(value[1] + "/")) {
      if (!best || value[1].length > best[1].length) best = value;
    }
  }
  return best ?? SCREEN_TITLES_FALLBACK;
}
