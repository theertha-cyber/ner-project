"use client";

import { useEffect, useRef, useState } from "react";
import { Search, Plus, EllipsisVertical, Pencil, Trash2, X } from "lucide-react";

interface Conversation {
  id: string;
  title: string | null;
  created_at: string;
  message_count: number;
}

interface ConversationListProps {
  conversations: Conversation[];
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onRename?: (id: string, title: string) => void;
  loading?: boolean;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// Formatted from UTC parts rather than `toLocaleDateString`: the server and the
// browser resolve locale and timezone differently, which renders a different
// string on each side and trips a hydration mismatch.
function formatDate(value: string): string | null {
  const d = new Date(value);
  if (isNaN(d.getTime())) return null;
  return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()}`;
}

export function ConversationList({
  conversations,
  onSelect,
  onNew,
  onDelete,
  onRename,
  loading,
}: ConversationListProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  const [menuId, setMenuId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // The row menu is a lightweight popover: a mousedown outside it, or Escape,
  // dismisses it. Dismissal is decided by containment rather than by stopping
  // propagation inside the menu — the App Router hydrates at `document`, so
  // React's delegated listener shares that node with this one and
  // `stopPropagation` would not keep this handler from running (that needs
  // `stopImmediatePropagation`, which React does not call). Without the
  // containment check, pressing a menu item closed the menu on mousedown and
  // the following click landed on nothing.
  useEffect(() => {
    if (!menuId) return;
    const onMouseDown = (e: MouseEvent) => {
      const node = menuRef.current;
      if (node && e.target instanceof Node && node.contains(e.target)) return;
      setMenuId(null);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenuId(null);
    };
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuId]);

  useEffect(() => {
    if (searchOpen) searchRef.current?.focus();
  }, [searchOpen]);

  const startEditing = (conv: Conversation) => {
    setMenuId(null);
    setEditingId(conv.id);
    setDraftTitle(conv.title || "New conversation");
  };

  const cancelEditing = () => {
    setEditingId(null);
    setDraftTitle("");
  };

  const confirmEditing = (convId: string) => {
    const trimmed = draftTitle.trim();
    if (trimmed && onRename) {
      onRename(convId, trimmed);
    }
    setEditingId(null);
    setDraftTitle("");
  };

  const handleDelete = (conv: Conversation) => {
    setMenuId(null);
    if (confirm("Delete this conversation?")) {
      onDelete(conv.id);
    }
  };

  const needle = query.trim().toLowerCase();
  const visible = needle
    ? conversations.filter((c) => (c.title || "New conversation").toLowerCase().includes(needle))
    : conversations;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <div style={{ maxWidth: 880, width: "100%", margin: "0 auto", padding: "16px 8px 0" }}>
        {/* The page name already sits in the app topbar, so the header here is
            just the actions, right-aligned. */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-end",
            gap: 8,
            marginBottom: 18,
          }}
        >
          {searchOpen ? (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                background: "var(--surface-3)",
                border: "1px solid var(--line)",
                borderRadius: "var(--radius-md)",
                padding: "0 8px 0 12px",
                height: 36,
                width: 240,
              }}
            >
              <Search size={15} style={{ color: "var(--ink-3)", flexShrink: 0 }} aria-hidden />
              <input
                ref={searchRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Escape") {
                    setQuery("");
                    setSearchOpen(false);
                  }
                }}
                placeholder="Search chats"
                aria-label="Search chats"
                style={{
                  flex: 1,
                  minWidth: 0,
                  background: "transparent",
                  border: "none",
                  outline: "none",
                  fontSize: 14,
                  color: "var(--ink)",
                }}
              />
              <button
                type="button"
                onClick={() => {
                  setQuery("");
                  setSearchOpen(false);
                }}
                aria-label="Close search"
                style={{
                  display: "flex",
                  alignItems: "center",
                  background: "none",
                  border: "none",
                  color: "var(--ink-3)",
                  cursor: "pointer",
                  padding: 4,
                }}
              >
                <X size={14} />
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setSearchOpen(true)}
              aria-label="Search chats"
              title="Search chats"
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 36,
                height: 36,
                borderRadius: "var(--radius-md)",
                background: "transparent",
                border: "1px solid transparent",
                color: "var(--ink-2)",
                cursor: "pointer",
              }}
            >
              <Search size={17} />
            </button>
          )}

          <button
            type="button"
            onClick={onNew}
            disabled={loading}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              height: 36,
              padding: "0 14px",
              borderRadius: "var(--radius-md)",
              background: loading ? "var(--surface-3)" : "var(--primary)",
              color: loading ? "var(--ink-3)" : "#fff",
              border: "none",
              fontSize: 14,
              fontWeight: 600,
              cursor: loading ? "not-allowed" : "pointer",
            }}
          >
            <Plus size={16} />
            {loading ? "Creating..." : "New chat"}
          </button>
        </div>
      </div>

      <div style={{ flex: 1, minHeight: 0, overflowY: "auto" }}>
        <div style={{ maxWidth: 880, width: "100%", margin: "0 auto", padding: "0 8px 24px" }}>
          {visible.length === 0 && (
            <div style={{ padding: "56px 16px", textAlign: "center" }}>
              <div style={{ fontSize: 15, color: "var(--ink-2)", marginBottom: 4 }}>
                {conversations.length === 0 ? "No conversations yet" : "No chats match your search"}
              </div>
              <div style={{ fontSize: 13, color: "var(--ink-3)" }}>
                {conversations.length === 0
                  ? "Start a new chat to ask questions about your documents and extracted entities."
                  : "Try a different search term."}
              </div>
            </div>
          )}

          {visible.map((conv) => {
            const isHovered = hoveredId === conv.id || menuId === conv.id;
            const date = formatDate(conv.created_at);
            return (
              <div
                key={conv.id}
                onMouseEnter={() => setHoveredId(conv.id)}
                onMouseLeave={() => setHoveredId(null)}
                style={{
                  position: "relative",
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  padding: "0 8px 0 14px",
                  minHeight: 52,
                  borderRadius: "var(--radius-md)",
                  borderBottom: "1px solid var(--line-2)",
                  background: isHovered ? "var(--surface-3)" : "transparent",
                  transition: "background 120ms ease",
                }}
              >
                {editingId === conv.id ? (
                  <input
                    autoFocus
                    value={draftTitle}
                    onChange={(e) => setDraftTitle(e.target.value)}
                    onBlur={() => confirmEditing(conv.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        confirmEditing(conv.id);
                      } else if (e.key === "Escape") {
                        e.preventDefault();
                        cancelEditing();
                      }
                    }}
                    aria-label="Conversation title"
                    style={{
                      flex: 1,
                      minWidth: 0,
                      fontSize: 15,
                      color: "var(--ink)",
                      background: "var(--surface-2)",
                      border: "1px solid var(--primary-line)",
                      borderRadius: 6,
                      padding: "6px 8px",
                      outline: "none",
                    }}
                  />
                ) : (
                  <button
                    type="button"
                    onClick={() => onSelect(conv.id)}
                    style={{
                      flex: 1,
                      minWidth: 0,
                      display: "block",
                      textAlign: "left",
                      background: "none",
                      border: "none",
                      padding: "14px 0",
                      cursor: "pointer",
                      color: "var(--ink)",
                      fontSize: 15,
                      lineHeight: 1.3,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {conv.title || "New conversation"}
                  </button>
                )}

                <div
                  ref={menuId === conv.id ? menuRef : undefined}
                  style={{
                    position: "relative",
                    flexShrink: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "flex-end",
                    gap: 8,
                    height: 32,
                  }}
                >
                  {editingId !== conv.id && (
                    <>
                      <span style={{ fontSize: 12.5, color: "var(--ink-3)", whiteSpace: "nowrap" }}>
                        {conv.message_count} {conv.message_count === 1 ? "message" : "messages"}
                        {date ? ` · ${date}` : ""}
                      </span>
                      {/* Kept mounted and merely hidden so the metadata beside it
                          doesn't shift sideways as the pointer enters the row. */}
                      <button
                        type="button"
                        onClick={() => setMenuId(menuId === conv.id ? null : conv.id)}
                        aria-label="Conversation options"
                        aria-haspopup="menu"
                        aria-expanded={menuId === conv.id}
                        title="Conversation options"
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          width: 30,
                          height: 30,
                          borderRadius: 8,
                          background: menuId === conv.id ? "var(--surface-2)" : "transparent",
                          border: "1px solid var(--line)",
                          color: "var(--ink-2)",
                          cursor: "pointer",
                          visibility: isHovered ? "visible" : "hidden",
                        }}
                      >
                        <EllipsisVertical size={16} />
                      </button>
                    </>
                  )}

                  {menuId === conv.id && (
                  <div
                    role="menu"
                    style={{
                      position: "absolute",
                      top: 36,
                      right: 0,
                      zIndex: 20,
                      minWidth: 168,
                      padding: 6,
                      borderRadius: "var(--radius-lg)",
                      background: "var(--color-surface-overlay)",
                      border: "1px solid var(--line)",
                      boxShadow: "var(--shadow-overlay)",
                    }}
                  >
                    {onRename && (
                      <button
                        type="button"
                        role="menuitem"
                        onClick={() => startEditing(conv)}
                        title="Rename conversation"
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 10,
                          width: "100%",
                          padding: "8px 10px",
                          borderRadius: 8,
                          background: "none",
                          border: "none",
                          color: "var(--ink)",
                          fontSize: 14,
                          textAlign: "left",
                          cursor: "pointer",
                        }}
                      >
                        <Pencil size={15} style={{ color: "var(--ink-2)" }} />
                        Rename
                      </button>
                    )}
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => handleDelete(conv)}
                      title="Delete conversation"
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 10,
                        width: "100%",
                        padding: "8px 10px",
                        borderRadius: 8,
                        background: "none",
                        border: "none",
                        color: "var(--bad)",
                        fontSize: 14,
                        textAlign: "left",
                        cursor: "pointer",
                      }}
                    >
                      <Trash2 size={15} />
                      Delete
                    </button>
                  </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
