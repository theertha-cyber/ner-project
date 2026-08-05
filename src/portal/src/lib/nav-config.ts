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
  Users,
  MessageSquare,
  KeyRound,
  ArrowUpRight,
} from "lucide-react";
import type { AuthUser } from "@/lib/auth";

export interface NavItem {
  id: string;
  icon: LucideIcon;
  label: string;
  href: string;
  roles: AuthUser["role"][];
  badge?: number;
}

export function navFor(role: AuthUser["role"]): NavItem[] {
  switch (role) {
    case "system_admin":
      return [
        { id: "dashboard", icon: LayoutDashboard, label: "Dashboard", href: "/dashboard", roles: ["system_admin"] },
        { id: "tenants", icon: Hexagon, label: "Tenants", href: "/admin/tenants", roles: ["system_admin"], badge: 6 },
        { id: "training-jobs", icon: BrainCircuit, label: "Models & Training", href: "/training-jobs", roles: ["system_admin"], badge: 2 },
        { id: "audit", icon: ScrollText, label: "Audit Log", href: "/audit", roles: ["system_admin"] },
      ];
    case "tenant_admin":
      return [
        { id: "dashboard", icon: LayoutDashboard, label: "Dashboard", href: "/dashboard", roles: ["tenant_admin"] },
        { id: "documents", icon: File, label: "Uploaded Documents", href: "/documents", roles: ["tenant_admin"] },
        { id: "entity-types", icon: Tags, label: "Entity Types", href: "/entity-types", roles: ["tenant_admin"] },
        { id: "annotation", icon: PenLine, label: "Annotation", href: "/annotation", roles: ["tenant_admin"] },
        { id: "imported-documents", icon: FileDown, label: "Import Annotations", href: "/imported-documents", roles: ["tenant_admin"] },
        { id: "training-jobs", icon: BrainCircuit, label: "Models & Training", href: "/training-jobs", roles: ["tenant_admin"], badge: 1 },
        { id: "users", icon: Users, label: "Create User", href: "/users", roles: ["tenant_admin"] },
        { id: "chat", icon: MessageSquare, label: "Chat", href: "/chat", roles: ["tenant_admin"] },
        { id: "widget-keys", icon: KeyRound, label: "Widget Keys", href: "/widget-keys", roles: ["tenant_admin"] },
      ];
    case "annotator":
      return [
        { id: "dashboard", icon: LayoutDashboard, label: "Dashboard", href: "/dashboard", roles: ["annotator"] },
        { id: "annotation", icon: PenLine, label: "Annotation", href: "/annotation", roles: ["annotator"], badge: 4 },
        { id: "imported-documents", icon: FileDown, label: "Import Annotations", href: "/imported-documents", roles: ["annotator"] },
      ];
    case "business_user":
      return [
        { id: "dashboard", icon: LayoutDashboard, label: "Dashboard", href: "/dashboard", roles: ["business_user"] },
        { id: "documents", icon: File, label: "Documents", href: "/documents", roles: ["business_user"] },
        { id: "extractions", icon: ArrowUpRight, label: "Extractions", href: "/extractions", roles: ["business_user"] },
        { id: "chat", icon: MessageSquare, label: "Chat", href: "/chat", roles: ["business_user"] },
      ];
  }
}

export const SCREEN_TITLES: Record<string, [title: string, path: string]> = {
  dashboard: ["Dashboard", "/dashboard"],
  annotation: ["Annotation", "/annotation"],
  tenants: ["Tenants", "/admin/tenants"],
  "training-jobs": ["Models & Training", "/training-jobs"],
  models: ["Models & Training", "/training-jobs"],
  documents: ["Uploaded Documents", "/documents"],
  "imported-documents": ["Import Pre-Annotated Files", "/imported-documents"],
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
