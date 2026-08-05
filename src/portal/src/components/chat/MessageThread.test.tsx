import { describe, it, expect, vi, beforeAll } from "vitest";
import { render, screen } from "@testing-library/react";
import { MessageThread } from "./MessageThread";

beforeAll(() => {
  // jsdom doesn't implement scrollIntoView; MessageThread calls it on mount.
  Element.prototype.scrollIntoView = vi.fn();
});

describe("MessageThread", () => {
  const baseMessages = [
    { id: "u1", role: "user" as const, content: "Hi there", created_at: "2026-01-01" },
    {
      id: "a1",
      role: "assistant" as const,
      content: "Hello, how can I help?",
      created_at: "2026-01-01",
      answer_kind: "answer" as const,
    },
    {
      id: "a2",
      role: "assistant" as const,
      content: "Which John do you mean?",
      created_at: "2026-01-01",
      answer_kind: "clarification" as const,
    },
    {
      id: "a3",
      role: "assistant" as const,
      content: "I can't help with that.",
      created_at: "2026-01-01",
      answer_kind: "guardrail_blocked" as const,
    },
  ];

  it("renders messages and citations as before", () => {
    render(<MessageThread messages={baseMessages} loading={false} />);
    expect(screen.getByText("Hi there")).toBeInTheDocument();
    expect(screen.getByText("Hello, how can I help?")).toBeInTheDocument();
  });

  it("does not render feedback controls when canRate is false", () => {
    render(<MessageThread messages={baseMessages} loading={false} canRate={false} onRateMessage={vi.fn()} />);
    expect(screen.queryByLabelText("Thumbs up")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Thumbs down")).not.toBeInTheDocument();
  });

  it("renders feedback controls only on eligible (answer_kind=answer) assistant messages when canRate is true", () => {
    render(<MessageThread messages={baseMessages} loading={false} canRate={true} onRateMessage={vi.fn()} />);
    // Only one assistant message has answer_kind "answer" -> exactly one pair of icons
    expect(screen.getAllByLabelText("Thumbs up")).toHaveLength(1);
    expect(screen.getAllByLabelText("Thumbs down")).toHaveLength(1);
  });

  it("does not render feedback controls on user messages even when canRate is true", () => {
    const onlyUser = [{ id: "u1", role: "user" as const, content: "Hi", created_at: "2026-01-01" }];
    render(<MessageThread messages={onlyUser} loading={false} canRate={true} onRateMessage={vi.fn()} />);
    expect(screen.queryByLabelText("Thumbs up")).not.toBeInTheDocument();
  });

  it("shows the fixed rating and disables both icons once a message is rated", () => {
    const rated = [
      {
        id: "a1",
        role: "assistant" as const,
        content: "Answer",
        created_at: "2026-01-01",
        answer_kind: "answer" as const,
        feedback: { message_id: "a1", rating: "up" as const, created_at: "2026-01-01" },
      },
    ];
    render(<MessageThread messages={rated} loading={false} canRate={true} onRateMessage={vi.fn()} />);
    expect(screen.getByLabelText("Thumbs up")).toBeDisabled();
    expect(screen.getByLabelText("Thumbs down")).toBeDisabled();
    expect(screen.getByLabelText("Thumbs up")).toHaveAttribute("aria-pressed", "true");
  });
});
