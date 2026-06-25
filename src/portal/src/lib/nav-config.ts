import type { AuthUser } from "@/lib/auth";

export interface NavItem {
  id: string;
  icon: string;
  label: string;
  href: string;
  roles: AuthUser["role"][];
  badge?: number;
}

export function navFor(role: AuthUser["role"]): NavItem[] {
  switch (role) {
    case "system_admin":
      return [
        { id: "dashboard", icon: "⊞", label: "Dashboard", href: "/dashboard", roles: ["system_admin"] },
        { id: "tenants", icon: "⬡", label: "Tenants", href: "/admin/tenants", roles: ["system_admin"], badge: 6 },
        { id: "training-jobs", icon: "↻", label: "Training Queue", href: "/training-jobs", roles: ["system_admin"], badge: 2 },
        { id: "models", icon: "◈", label: "Model Registry", href: "/models", roles: ["system_admin"] },
        { id: "audit", icon: "≡", label: "Audit Log", href: "/audit", roles: ["system_admin"] },
      ];
    case "tenant_admin":
      return [
        { id: "dashboard", icon: "⊞", label: "Dashboard", href: "/dashboard", roles: ["tenant_admin"] },
        { id: "documents", icon: "◻", label: "Documents", href: "/documents", roles: ["tenant_admin"] },
        { id: "annotation", icon: "✎", label: "Annotation", href: "/annotation", roles: ["tenant_admin"] },
        { id: "entity-types", icon: "◇", label: "Entity Types", href: "/entity-types", roles: ["tenant_admin"] },
        { id: "training-jobs", icon: "↻", label: "Training Jobs", href: "/training-jobs", roles: ["tenant_admin"], badge: 1 },
        { id: "models", icon: "◈", label: "Model Registry", href: "/models", roles: ["tenant_admin"] },
        { id: "users", icon: "⊙", label: "Users", href: "/users", roles: ["tenant_admin"] },
        { id: "chat", icon: "💬", label: "Chat", href: "/chat", roles: ["tenant_admin"] },
        { id: "analytics", icon: "📊", label: "Analytics", href: "/analytics", roles: ["tenant_admin"] },
        { id: "widget-keys", icon: "⊟", label: "Widget Keys", href: "/widget-keys", roles: ["tenant_admin"] },
      ];
    case "annotator":
      return [
        { id: "dashboard", icon: "⊞", label: "My Work", href: "/dashboard", roles: ["annotator"] },
        { id: "annotation", icon: "✎", label: "Annotation", href: "/annotation", roles: ["annotator"], badge: 4 },
        { id: "documents", icon: "◻", label: "Documents", href: "/documents", roles: ["annotator"] },
      ];
    case "business_user":
      return [
        { id: "dashboard", icon: "⊞", label: "Overview", href: "/dashboard", roles: ["business_user"] },
        { id: "documents", icon: "◻", label: "Documents", href: "/documents", roles: ["business_user"] },
        { id: "extractions", icon: "⤴", label: "Extractions", href: "/extractions", roles: ["business_user"] },
        { id: "models", icon: "◈", label: "Models", href: "/models", roles: ["business_user"] },
        { id: "chat", icon: "💬", label: "Chat", href: "/chat", roles: ["business_user"] },
        { id: "analytics", icon: "📊", label: "Analytics", href: "/analytics", roles: ["business_user"] },
      ];
  }
}

export const SCREEN_TITLES: Record<string, [title: string, path: string]> = {
  dashboard: ["Dashboard", "/dashboard"],
  annotation: ["Annotation", "/annotation"],
  tenants: ["Tenants", "/admin/tenants"],
  "training-jobs": ["Training Jobs", "/training-jobs"],
  models: ["Models", "/models"],
  documents: ["Documents", "/documents"],
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
