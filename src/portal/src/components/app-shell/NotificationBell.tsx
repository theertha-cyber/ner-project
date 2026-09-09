"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Bell } from "lucide-react";
import { useNotifications, useMarkNotificationRead, AppNotification } from "@/hooks/use-notifications";

function hrefFor(n: AppNotification): string | null {
  if (n.resource_type === "annotation_task") return "/annotate/automated/retrain";
  if (n.resource_type === "prelabel_batch") return "/annotate/automated/retrain";
  if (n.resource_type === "import_file") return "/imported-documents";
  return null;
}

export function NotificationBell() {
  const router = useRouter();
  const { data } = useNotifications();
  const markRead = useMarkNotificationRead();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function onEsc(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onEsc);
    return () => document.removeEventListener("keydown", onEsc);
  }, []);

  const unread = data?.unread ?? 0;
  const items = data?.items ?? [];

  return (
    <div style={{ position: "relative", flexShrink: 0 }}>
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label="Notifications"
        title="Notifications"
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
          position: "relative",
        }}
      >
        <Bell size={17} strokeWidth={2} />
        {unread > 0 && (
          <span
            style={{
              position: "absolute",
              top: -4,
              right: -4,
              minWidth: 16,
              height: 16,
              padding: "0 4px",
              borderRadius: 20,
              background: "var(--primary)",
              color: "#fff",
              fontSize: 10,
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <>
          <div onClick={() => setOpen(false)} style={{ position: "fixed", inset: 0, zIndex: 60 }} />
          <div
            style={{
              position: "absolute",
              right: 0,
              top: 44,
              width: 340,
              maxHeight: 420,
              overflowY: "auto",
              background: "var(--surface-2)",
              border: "1px solid var(--line)",
              borderRadius: 12,
              boxShadow: "0 8px 28px rgba(0,0,0,0.16)",
              zIndex: 61,
              padding: 6,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 10px" }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)" }}>Notifications</span>
              {unread > 0 && (
                <button
                  onClick={() => markRead.mutate("all")}
                  style={{ border: "none", background: "transparent", color: "var(--primary)", fontSize: 12, cursor: "pointer" }}
                >
                  Mark all read
                </button>
              )}
            </div>
            {items.length === 0 && (
              <div style={{ padding: "18px 12px", fontSize: 12.5, color: "var(--ink-3)", textAlign: "center" }}>
                Nothing new.
              </div>
            )}
            {items.map((n) => {
              const target = hrefFor(n);
              return (
                <button
                  key={n.id}
                  onClick={() => {
                    if (!n.read_at) markRead.mutate(n.id);
                    if (target) {
                      router.push(target);
                      setOpen(false);
                    }
                  }}
                  style={{
                    display: "block",
                    width: "100%",
                    textAlign: "left",
                    border: "none",
                    borderRadius: 8,
                    background: n.read_at ? "transparent" : "var(--primary-soft)",
                    padding: "9px 10px",
                    cursor: "pointer",
                    marginBottom: 2,
                  }}
                >
                  <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--ink)" }}>{n.title}</div>
                  {n.body && (
                    <div style={{ fontSize: 11.5, color: "var(--ink-2)", marginTop: 2, lineHeight: 1.4 }}>{n.body}</div>
                  )}
                  <div style={{ fontSize: 10.5, color: "var(--ink-3)", marginTop: 3 }}>
                    {new Date(n.created_at).toLocaleString()}
                  </div>
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
