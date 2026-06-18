"use client";

import { ReactNode, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import type { AuthUser } from "@/lib/auth";

interface RequireAuthProps {
  roles?: AuthUser["role"][];
  children: ReactNode;
}

export function RequireAuth({ roles, children }: RequireAuthProps) {
  const { user } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (user === null) {
      router.replace("/login");
    } else if (roles && !roles.includes(user.role)) {
      router.replace("/dashboard");
    }
    // roles is typically static per route; re-run only when user or router changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, router]);

  if (user === null) return null;
  if (roles && !roles.includes(user.role)) return null;

  return <>{children}</>;
}
