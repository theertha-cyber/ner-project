"use client";

import { useState, useCallback, useEffect, useRef, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { RequireAuth } from "@/components/require-auth";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { MessageThread } from "@/components/chat/MessageThread";
import { ChatInput } from "@/components/chat/ChatInput";
import { authFetch } from "@/lib/auth-fetch";
import { useAuth } from "@/lib/auth";
import { readChatStream } from "@/lib/chat-stream";
import type { Feedback } from "@/components/chat/MessageFeedback";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  created_at: string;
  isThinking?: boolean;
  isStreaming?: boolean;
  answer_kind?: "answer" | "clarification" | "guardrail_blocked" | "out_of_domain" | null;
  model_version?: string | null;
  feedback?: Feedback | null;
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
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const conversationParam = searchParams.get("conversation");
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

  useEffect(() => {
    if (conversationParam && conversationParam !== activeConvId) {
      handleSelectConversation(conversationParam);
    }
  }, [conversationParam, activeConvId, handleSelectConversation]);

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

  const handleSendMessageStreaming = useCallback(async (text: string, tempId: string, thinkingId: string, isFirstMessage: boolean) => {
    let accumulated = "";
    let outcome: "done" | "error" | null = null;

    try {
      const resp = await authFetch(CHAT_API_BASE + "/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          conversation_id: activeConvId,
        }),
      });

      if (!resp.ok) {
        throw new Error("Streaming request failed with status " + resp.status);
      }

      await readChatStream(resp, {
        onToken: (delta) => {
          accumulated += delta;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === thinkingId
                ? { ...m, isThinking: false, isStreaming: true, content: accumulated }
                : m
            )
          );
        },
        onDone: (data) => {
          outcome = "done";
          const conversationId = data.conversation_id as string | undefined;
          const assistantMsg: Message = {
            id: (data.message_id as string) || (conversationId ?? tempId) + "-resp-" + Date.now(),
            role: "assistant",
            content: typeof data.reply === "string" ? data.reply : accumulated,
            sources: data.sources as Source[] | undefined,
            created_at: new Date().toISOString(),
            answer_kind: data.answer_kind as Message["answer_kind"],
            model_version: (data.model_version as string | null) ?? null,
          };
          setMessages((prev) =>
            prev
              .map((m) => (m.id === tempId ? { ...m, id: (conversationId ?? tempId) + "-user" } : m))
              .map((m) => (m.id === thinkingId ? assistantMsg : m))
          );

          if (!activeConvId && conversationId) {
            setActiveConvId(conversationId);
          }
          if (!activeConvId || isFirstMessage) {
            loadConversations();
          }
        },
        onError: () => {
          outcome = "error";
        },
      });

      if (outcome !== "done") {
        // Either an `error` frame arrived, or the stream closed with neither
        // `done` nor `error` — both are treated as a failed turn.
        throw new Error("Streaming turn did not complete successfully");
      }
    } catch {
      setMessages((prev) => prev.filter((m) => m.id !== tempId && m.id !== thinkingId));
      showError("Failed to get a response. Please try again.");
    } finally {
      setSending(false);
    }
  }, [activeConvId, loadConversations, showError]);

  const handleSendMessageNonStreaming = useCallback(async (text: string, tempId: string, thinkingId: string, isFirstMessage: boolean) => {
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
          id: data.message_id || data.conversation_id + "-resp-" + Date.now(),
          role: "assistant",
          content: data.reply,
          sources: data.sources,
          created_at: new Date().toISOString(),
          answer_kind: data.answer_kind,
          model_version: data.model_version,
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
  }, [activeConvId, loadConversations, showError]);

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

    // Read fresh on every send (not memoized at module scope) so a client-side
    // kill switch can be exercised without a rebuild in tests.
    const streamingEnabled = process.env.NEXT_PUBLIC_CHAT_STREAMING_ENABLED !== "false";
    if (streamingEnabled) {
      await handleSendMessageStreaming(text, tempId, thinkingId, isFirstMessage);
    } else {
      await handleSendMessageNonStreaming(text, tempId, thinkingId, isFirstMessage);
    }
  }, [messages, handleSendMessageStreaming, handleSendMessageNonStreaming]);

  const handleRateMessage = useCallback(async (messageId: string, rating: "up" | "down") => {
    try {
      const resp = await authFetch(CHAT_API_BASE + "/messages/" + messageId + "/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating }),
      });
      if (resp.ok || resp.status === 409) {
        const data = await resp.json();
        const feedback: Feedback = resp.ok ? data : data.detail;
        setMessages((prev) =>
          prev.map((m) => (m.id === messageId ? { ...m, feedback } : m))
        );
      } else {
        showError("Failed to submit feedback. Please try again.");
      }
    } catch {
      showError("Network error. Please check your connection and try again.");
    }
  }, [showError]);

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
            <MessageThread
              messages={messages}
              loading={loading}
              canRate={user?.role === "business_user"}
              onRateMessage={handleRateMessage}
            />
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
      <Suspense fallback={null}>
        <ChatPageInner />
      </Suspense>
    </RequireAuth>
  );
}
