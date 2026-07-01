"use client";

interface Conversation {
  id: string;
  title: string | null;
  created_at: string;
  message_count: number;
}

interface ChatSidebarProps {
  conversations: Conversation[];
  activeConvId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  loading?: boolean;
}

export function ChatSidebar({ conversations, activeConvId, onSelect, onNew, onDelete, loading }: ChatSidebarProps) {
  return (
    <div
      style={{
        width: 280,
        borderRight: "1px solid #e5e7eb",
        display: "flex",
        flexDirection: "column",
        background: "#f9fafb",
      }}
    >
      <div style={{ padding: "12px", borderBottom: "1px solid #e5e7eb" }}>
        <button
          onClick={onNew}
          disabled={loading}
          style={{
            width: "100%",
            padding: "10px 16px",
            background: loading ? "#93c5fd" : "#2563eb",
            color: "white",
            border: "none",
            borderRadius: 8,
            cursor: loading ? "not-allowed" : "pointer",
            fontWeight: 600,
            fontSize: 14,
          }}
        >
          {loading ? "Creating..." : "+ New conversation"}
        </button>
      </div>
      <div style={{ flex: 1, overflowY: "auto" }}>
        {conversations.length === 0 && (
          <div style={{ padding: 16, color: "#9ca3af", textAlign: "center", fontSize: 14 }}>
            No conversations yet
          </div>
        )}
        {conversations.map((conv) => (
          <div
            key={conv.id}
            onClick={() => onSelect(conv.id)}
            style={{
              padding: "12px 16px",
              cursor: "pointer",
              borderBottom: "1px solid #e5e7eb",
              background: activeConvId === conv.id ? "#e0e7ff" : "transparent",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontWeight: activeConvId === conv.id ? 600 : 400,
                  fontSize: 14,
                  color: "#111827",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {conv.title || "New conversation"}
              </div>
              <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 2 }}>
                {conv.message_count} messages
              </div>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (confirm("Delete this conversation?")) {
                  onDelete(conv.id);
                }
              }}
              style={{
                background: "none",
                border: "none",
                color: "#ef4444",
                cursor: "pointer",
                fontSize: 14,
                padding: "4px 8px",
                borderRadius: 4,
              }}
              title="Delete conversation"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
