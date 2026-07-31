"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { RequireAuth } from "@/components/require-auth";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { MessageThread } from "@/components/chat/MessageThread";
import { ChatInput } from "@/components/chat/ChatInput";
import { authFetch } from "@/lib/auth-fetch";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  created_at: string;
  isThinking?: boolean;
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
  const [creatingConversation, setCreatingConversation] = useState(false);
  const [errorToast, setErrorToast] = useState<string | null>(null);
  const errorTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadConversations = useCallback(async () => {
    try {
      const resp = await authFetch(CHAT_API_BASE + "/conversations");
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
      const resp = await authFetch(CHAT_API_BASE + "/conversations/" + convId);
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

  const showError = useCallback((msg: string) => {
    setErrorToast(msg);
    if (errorTimerRef.current) clearTimeout(errorTimerRef.current);
    errorTimerRef.current = setTimeout(() => setErrorToast(null), 5000);
  }, []);

  const handleNewConversation = useCallback(async () => {
    setCreatingConversation(true);
    try {
      const resp = await authFetch(CHAT_API_BASE + "/conversations", {
        method: "POST",
      });
      if (resp.ok) {
        const data = await resp.json();
        const newConv: Conversation = {
          id: data.id,
          title: data.title || null,
          created_at: data.created_at,
          message_count: 0,
        };
        setConversations((prev) => [newConv, ...prev]);
        setActiveConvId(data.id);
        setMessages([]);
        setErrorToast(null);
      } else {
        showError("Failed to create conversation. Please try again.");
      }
    } catch {
      showError("Network error. Please check your connection and try again.");
    } finally {
      setCreatingConversation(false);
    }
  }, [showError]);

  const handleRenameConversation = useCallback(async (convId: string, title: string) => {
    try {
      const resp = await authFetch(CHAT_API_BASE + "/conversations/" + convId, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      if (resp.ok) {
        const data = await resp.json();
        setConversations((prev) =>
          prev.map((c) => (c.id === convId ? { ...c, title: data.title } : c))
        );
      } else {
        showError("Failed to rename conversation. Please try again.");
      }
    } catch {
      showError("Network error. Please check your connection and try again.");
    }
  }, [showError]);

  const handleDeleteConversation = useCallback(async (convId: string) => {
    try {
      const resp = await authFetch(CHAT_API_BASE + "/conversations/" + convId, {
        method: "DELETE",
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

    const isFirstMessage = messages.length === 0;
    const tempId = "temp-" + Date.now();
    const thinkingId = "thinking-" + Date.now();
    const optimistic: Message = {
      id: tempId,
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };
    const thinking: Message = {
      id: thinkingId,
      role: "assistant",
      content: "",
      created_at: new Date().toISOString(),
      isThinking: true,
    };
    setMessages((prev) => [...prev, optimistic, thinking]);
    setSending(true);

    try {
      const resp = await authFetch(CHAT_API_BASE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          conversation_id: activeConvId,
        }),
      });

      if (resp.ok) {
        const data = await resp.json();
        const assistantMsg: Message = {
          id: data.conversation_id + "-resp-" + Date.now(),
          role: "assistant",
          content: data.reply,
          sources: data.sources,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) =>
          prev
            .map((m) => (m.id === tempId ? { ...m, id: data.conversation_id + "-user" } : m))
            .map((m) => (m.id === thinkingId ? assistantMsg : m))
        );

        if (!activeConvId) {
          setActiveConvId(data.conversation_id);
        }
        if (!activeConvId || isFirstMessage) {
          loadConversations();
        }
      } else {
        setMessages((prev) => prev.filter((m) => m.id !== tempId && m.id !== thinkingId));
        showError("Failed to get a response. Please try again.");
      }
    } catch {
      setMessages((prev) => prev.filter((m) => m.id !== tempId && m.id !== thinkingId));
      showError("Network error. Please check your connection and try again.");
    } finally {
      setSending(false);
    }
  }, [activeConvId, messages, loadConversations, showError]);

  return (
    <div className="animate-fade-up flex h-full" style={{ overflow: "hidden", position: "relative" }}>
      {errorToast && (
        <div
          style={{
            position: "absolute",
            top: 8,
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 100,
            background: "var(--bad-soft)",
            color: "var(--bad)",
            border: "1px solid var(--bad)",
            borderRadius: 8,
            padding: "10px 20px",
            fontSize: 13,
            fontWeight: 500,
            maxWidth: 400,
            textAlign: "center",
          }}
        >
          {errorToast}
        </div>
      )}
      <ChatSidebar
        conversations={conversations}
        activeConvId={activeConvId}
        onSelect={handleSelectConversation}
        onNew={handleNewConversation}
        onDelete={handleDeleteConversation}
        onRename={handleRenameConversation}
        loading={creatingConversation}
      />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
        {activeConvId ? (
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
              color: "var(--ink-3)",
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
