"use client";

import { useState, useCallback, useEffect } from "react";
import { RequireAuth } from "@/components/require-auth";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { MessageThread } from "@/components/chat/MessageThread";
import { ChatInput } from "@/components/chat/ChatInput";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  created_at: string;
}

interface Source {
  source_type: string;
  document_id?: string;
  chunk_index?: number;
  chunk_text?: string;
  relevance_score?: number;
  entity_type?: string;
  value?: string;
  confidence?: number;
}

interface Conversation {
  id: string;
  title: string | null;
  created_at: string;
  message_count: number;
}

const CHAT_API_BASE = "/api/v1/chat";

function ChatPageInner() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);

  const loadConversations = useCallback(async () => {
    try {
      const resp = await fetch(CHAT_API_BASE + "/conversations", { credentials: "include" });
      if (resp.ok) {
        const data = await resp.json();
        setConversations(data);
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const loadMessages = useCallback(async (convId: string) => {
    setLoading(true);
    try {
      const resp = await fetch(CHAT_API_BASE + "/conversations/" + convId, { credentials: "include" });
      if (resp.ok) {
        const data = await resp.json();
        setMessages(data.messages || []);
      }
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSelectConversation = useCallback((convId: string) => {
    setActiveConvId(convId);
    loadMessages(convId);
  }, [loadMessages]);

  const handleNewConversation = useCallback(() => {
    setActiveConvId(null);
    setMessages([]);
  }, []);

  const handleDeleteConversation = useCallback(async (convId: string) => {
    try {
      const resp = await fetch(CHAT_API_BASE + "/conversations/" + convId, {
        method: "DELETE",
        credentials: "include",
      });
      if (resp.status === 204) {
        setConversations((prev) => prev.filter((c) => c.id !== convId));
        if (activeConvId === convId) {
          setActiveConvId(null);
          setMessages([]);
        }
      }
    } catch {
      /* ignore */
    }
  }, [activeConvId]);

  const handleSendMessage = useCallback(async (text: string) => {
    if (!text.trim()) return;

    const tempId = "temp-" + Date.now();
    const optimistic: Message = {
      id: tempId,
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimistic]);
    setSending(true);

    try {
      const resp = await fetch(CHAT_API_BASE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          message: text,
          conversation_id: activeConvId,
        }),
      });

      if (resp.ok) {
        const data = await resp.json();
        setMessages((prev) =>
          prev.map((m) => (m.id === tempId ? { ...m, id: data.conversation_id + "-user" } : m))
        );
        const assistantMsg: Message = {
          id: data.conversation_id + "-resp-" + Date.now(),
          role: "assistant",
          content: data.reply,
          sources: data.sources,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMsg]);

        if (!activeConvId) {
          setActiveConvId(data.conversation_id);
          loadConversations();
        }
      }
    } catch {
      setMessages((prev) => prev.filter((m) => m.id !== tempId));
    } finally {
      setSending(false);
    }
  }, [activeConvId, loadConversations]);

  return (
    <div style={{ display: "flex", height: "calc(100vh - 60px)", overflow: "hidden" }}>
      <ChatSidebar
        conversations={conversations}
        activeConvId={activeConvId}
        onSelect={handleSelectConversation}
        onNew={handleNewConversation}
        onDelete={handleDeleteConversation}
      />
      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        {activeConvId || messages.length > 0 ? (
          <>
            <MessageThread messages={messages} loading={loading} />
            <ChatInput onSend={handleSendMessage} disabled={sending} />
          </>
        ) : (
          <div
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#9ca3af",
              fontSize: 16,
            }}
          >
            Select a conversation or start a new one
          </div>
        )}
      </div>
    </div>
  );
}

export default function ChatPage() {
  return (
    <RequireAuth roles={["tenant_admin", "business_user"]}>
      <ChatPageInner />
    </RequireAuth>
  );
}
