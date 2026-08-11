import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const mockReplace = vi.fn();

vi.mock("next/navigation", () => ({
  useSearchParams: vi.fn(() => new URLSearchParams("conversation=conv-1")),
  useRouter: vi.fn(() => ({ replace: mockReplace })),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(() => ({
    user: { role: "business_user", tenantId: "t1", userId: "u1", email: "a@b.com", tenantSlug: null },
  })),
}));

import ChatPage from "./page";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch as unknown as typeof fetch;

function sseResponse(frames: string[], status = 200): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const frame of frames) {
        controller.enqueue(encoder.encode(frame));
      }
      controller.close();
    },
  });
  return new Response(stream, { status, headers: { "content-type": "text/event-stream" } });
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

beforeEach(() => {
  mockFetch.mockReset();
  mockReplace.mockReset();
  Element.prototype.scrollIntoView = vi.fn();

  mockFetch.mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/api/v1/chat/conversations/conv-1")) {
      return Promise.resolve(
        jsonResponse({ id: "conv-1", title: "Test", created_at: "2026-01-01", messages: [] }),
      );
    }
    if (url.includes("/api/v1/chat/conversations")) {
      return Promise.resolve(jsonResponse([]));
    }
    return Promise.resolve(jsonResponse({}));
  });
});

afterEach(() => {
  vi.unstubAllEnvs();
});

async function renderChatAndWaitForInput() {
  render(<ChatPage />);
  return screen.findByPlaceholderText("Type your question...");
}

async function sendMessage(text: string) {
  const input = await renderChatAndWaitForInput();
  fireEvent.change(input, { target: { value: text } });
  fireEvent.keyDown(input, { key: "Enter" });
}

// Covers verification.md rows 19, 20, 39 (chat-response-token-streaming task 4.8).
describe("Chat page — streaming failure cleanup", () => {
  it("clears the Thinking indicator and shows an error toast when the stream emits an error frame", async () => {
    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/chat/stream")) {
        return Promise.resolve(
          sseResponse([
            'event: token\ndata: {"delta": "partial"}\n\n',
            'event: error\ndata: {"code": "GENERATION_FAILED", "message": "boom"}\n\n',
          ]),
        );
      }
      if (url.includes("/api/v1/chat/conversations/conv-1")) {
        return Promise.resolve(jsonResponse({ id: "conv-1", title: "Test", created_at: "2026-01-01", messages: [] }));
      }
      if (url.includes("/api/v1/chat/conversations")) {
        return Promise.resolve(jsonResponse([]));
      }
      return Promise.resolve(jsonResponse({}));
    });

    await sendMessage("How many organizations?");

    await waitFor(() => {
      expect(screen.getByText(/Failed to get a response/)).toBeInTheDocument();
    });
    expect(screen.queryByText("Thinking...")).not.toBeInTheDocument();
    expect(screen.queryByText("How many organizations?")).not.toBeInTheDocument();
  });

  it("clears the Thinking indicator and shows an error toast when the stream closes with neither done nor error", async () => {
    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/chat/stream")) {
        return Promise.resolve(sseResponse(['event: token\ndata: {"delta": "partial"}\n\n']));
      }
      if (url.includes("/api/v1/chat/conversations/conv-1")) {
        return Promise.resolve(jsonResponse({ id: "conv-1", title: "Test", created_at: "2026-01-01", messages: [] }));
      }
      if (url.includes("/api/v1/chat/conversations")) {
        return Promise.resolve(jsonResponse([]));
      }
      return Promise.resolve(jsonResponse({}));
    });

    await sendMessage("How many organizations?");

    await waitFor(() => {
      expect(screen.getByText(/Failed to get a response/)).toBeInTheDocument();
    });
    expect(screen.queryByText("Thinking...")).not.toBeInTheDocument();
    expect(screen.queryByText("How many organizations?")).not.toBeInTheDocument();
  });
});

// Covers verification.md rows 26, 27 (chat-response-token-streaming task 4.9).
describe("Chat page — streaming kill switch", () => {
  it("sends to /api/v1/chat/stream when NEXT_PUBLIC_CHAT_STREAMING_ENABLED is unset", async () => {
    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/chat/stream")) {
        return Promise.resolve(
          sseResponse([
            'event: token\ndata: {"delta": "5"}\n\n',
            'event: done\ndata: {"reply": "5", "sources": [], "conversation_id": "conv-1", "message_id": "m1", "answer_kind": "answer"}\n\n',
          ]),
        );
      }
      if (url.includes("/api/v1/chat/conversations/conv-1")) {
        return Promise.resolve(jsonResponse({ id: "conv-1", title: "Test", created_at: "2026-01-01", messages: [] }));
      }
      if (url.includes("/api/v1/chat/conversations")) {
        return Promise.resolve(jsonResponse([]));
      }
      return Promise.resolve(jsonResponse({}));
    });

    await sendMessage("How many organizations?");

    await waitFor(() => {
      const streamCall = mockFetch.mock.calls.find(([u]) => String(u).includes("/api/v1/chat/stream"));
      expect(streamCall).toBeDefined();
    });
    const nonStreamCall = mockFetch.mock.calls.find(
      ([u]) => String(u).endsWith("/api/v1/chat"),
    );
    expect(nonStreamCall).toBeUndefined();
  });

  it("sends to /api/v1/chat and keeps Thinking until the complete response when disabled", async () => {
    vi.stubEnv("NEXT_PUBLIC_CHAT_STREAMING_ENABLED", "false");

    let resolveChat: (r: Response) => void = () => {};
    const chatPromise = new Promise<Response>((resolve) => {
      resolveChat = resolve;
    });

    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/v1/chat")) {
        return chatPromise;
      }
      if (url.includes("/api/v1/chat/conversations/conv-1")) {
        return Promise.resolve(jsonResponse({ id: "conv-1", title: "Test", created_at: "2026-01-01", messages: [] }));
      }
      if (url.includes("/api/v1/chat/conversations")) {
        return Promise.resolve(jsonResponse([]));
      }
      return Promise.resolve(jsonResponse({}));
    });

    await sendMessage("How many organizations?");

    await waitFor(() => {
      const chatCall = mockFetch.mock.calls.find(([u]) => String(u).endsWith("/api/v1/chat"));
      expect(chatCall).toBeDefined();
    });
    const streamCall = mockFetch.mock.calls.find(([u]) => String(u).includes("/api/v1/chat/stream"));
    expect(streamCall).toBeUndefined();

    // Response hasn't resolved yet — Thinking must still be visible.
    expect(screen.getByText("Thinking...")).toBeInTheDocument();

    resolveChat(
      jsonResponse({
        reply: "5", sources: [], conversation_id: "conv-1", message_id: "m1", answer_kind: "answer",
      }),
    );

    await waitFor(() => {
      expect(screen.queryByText("Thinking...")).not.toBeInTheDocument();
    });
  });
});
