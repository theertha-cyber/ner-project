import { describe, it, expect, vi, beforeAll } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
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

    // The rating reads off the glyph itself: the chosen thumb is filled and the
    // button stays transparent (no coloured pill behind the icon).
    const up = screen.getByLabelText("Thumbs up");
    const down = screen.getByLabelText("Thumbs down");
    expect(up.querySelector("svg")).toHaveAttribute("fill", "currentColor");
    expect(down.querySelector("svg")).toHaveAttribute("fill", "none");
    expect(up).toHaveStyle({ background: "transparent" });
  });

  it("does not scroll to the newest message when an older message is rated", () => {
    const scrollSpy = vi.spyOn(Element.prototype, "scrollIntoView");
    const withFeedback = baseMessages.map((m) =>
      m.id === "a1" ? { ...m, feedback: { message_id: "a1", rating: "up" as const, created_at: "2026-01-01" } } : m
    );

    const { rerender } = render(
      <MessageThread messages={baseMessages} loading={false} canRate={true} onRateMessage={vi.fn()} />
    );
    scrollSpy.mockClear();

    // Rating replaces the array (new object identity, same tail) — the thread must stay put.
    rerender(<MessageThread messages={withFeedback} loading={false} canRate={true} onRateMessage={vi.fn()} />);
    expect(scrollSpy).not.toHaveBeenCalled();

    // A genuinely new message still scrolls.
    rerender(
      <MessageThread
        messages={[...withFeedback, { id: "a4", role: "assistant" as const, content: "Newest", created_at: "2026-01-01" }]}
        loading={false}
        canRate={true}
        onRateMessage={vi.fn()}
      />
    );
    expect(scrollSpy).toHaveBeenCalled();
    scrollSpy.mockRestore();
  });

  it("scrolls as streamed tokens extend the last message", () => {
    const scrollSpy = vi.spyOn(Element.prototype, "scrollIntoView");
    const streaming = [
      { id: "a1", role: "assistant" as const, content: "Based", created_at: "2026-01-01", isStreaming: true },
    ];
    const { rerender } = render(<MessageThread messages={streaming} loading={false} />);
    scrollSpy.mockClear();

    rerender(
      <MessageThread
        messages={[{ ...streaming[0], content: "Based on the documents" }]}
        loading={false}
      />
    );
    expect(scrollSpy).toHaveBeenCalled();
    scrollSpy.mockRestore();
  });
});

// Covers verification.md rows 36, 37 (chat-response-token-streaming task 4.7).
describe("MessageThread streaming lifecycle", () => {
  it("shows the Thinking indicator before any token arrives", () => {
    const messages = [
      { id: "a1", role: "assistant" as const, content: "", created_at: "2026-01-01", isThinking: true },
    ];
    render(<MessageThread messages={messages} loading={false} />);
    expect(screen.getByText("Thinking...")).toBeInTheDocument();
  });

  it("replaces Thinking with the first fragment on the first token, then appends subsequent tokens", () => {
    const initial = [
      { id: "a1", role: "assistant" as const, content: "", created_at: "2026-01-01", isThinking: true },
    ];
    const { rerender } = render(<MessageThread messages={initial} loading={false} />);
    expect(screen.getByText("Thinking...")).toBeInTheDocument();

    const firstToken = [
      {
        id: "a1", role: "assistant" as const, content: "Based",
        created_at: "2026-01-01", isThinking: false, isStreaming: true,
      },
    ];
    rerender(<MessageThread messages={firstToken} loading={false} />);
    expect(screen.queryByText("Thinking...")).not.toBeInTheDocument();
    expect(screen.getByText("Based")).toBeInTheDocument();

    const moreTokens = [
      {
        id: "a1", role: "assistant" as const, content: "Based on the documents",
        created_at: "2026-01-01", isThinking: false, isStreaming: true,
      },
    ];
    rerender(<MessageThread messages={moreTokens} loading={false} />);
    expect(screen.getByText("Based on the documents")).toBeInTheDocument();
  });

  it("withholds citation chips and the rating control while a message is streaming", () => {
    const streaming = [
      {
        id: "a1", role: "assistant" as const, content: "Based on the documents",
        created_at: "2026-01-01", isThinking: false, isStreaming: true, answer_kind: "answer" as const,
        sources: [{ document_name: "report.pdf", source_type: "document_chunk" }],
      },
    ];
    render(<MessageThread messages={streaming} loading={false} canRate={true} onRateMessage={vi.fn()} />);
    expect(screen.queryByLabelText("Thumbs up")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Thumbs down")).not.toBeInTheDocument();
    expect(screen.queryByText("report.pdf")).not.toBeInTheDocument();
  });

  it("shows the full reply with citations and the rating control once the turn completes", () => {
    const done = [
      {
        id: "a1", role: "assistant" as const, content: "Based on the documents, there are 5.",
        created_at: "2026-01-01", answer_kind: "answer" as const,
        sources: [{ document_name: "report.pdf", source_type: "document_chunk" }],
      },
    ];
    render(<MessageThread messages={done} loading={false} canRate={true} onRateMessage={vi.fn()} />);
    expect(screen.getByText("Based on the documents, there are 5.")).toBeInTheDocument();
    expect(screen.getByText("report.pdf")).toBeInTheDocument();
    expect(screen.getByLabelText("Thumbs up")).toBeInTheDocument();
  });

  describe("long-answer truncation, export card, and See more", () => {
    const longContent = [
      "**Name One** - Engineer",
      "**Name Two** - Developer",
      "**Name Three** - Engineer",
      "**Name Four** - Developer",
      "**Name Five** - Engineer",
      "**Name Six** - Developer",
      "**Name Seven** - Engineer",
      "**Name Eight** - Developer",
    ].join("\n\n");
    const shortContent = ["**Name One** - Engineer", "**Name Two** - Developer"].join("\n\n");

    it("previews only the first 5 lines, with an export card and a See more toggle, when the answer has more than 5 lines and export data", () => {
      const messages = [
        {
          id: "a1", role: "assistant" as const, content: longContent,
          created_at: "2026-01-01", answer_kind: "answer" as const,
          export: { message_id: "a1", row_count: 8, formats: ["csv", "xlsx"] },
        },
      ];
      render(<MessageThread messages={messages} loading={false} />);
      expect(screen.getByText("Name Five", { exact: false })).toBeInTheDocument();
      expect(screen.queryByText("Name Six", { exact: false })).not.toBeInTheDocument();
      expect(screen.getByLabelText("Download CSV")).toBeInTheDocument();
      expect(screen.getByLabelText("Download XLSX")).toBeInTheDocument();
      expect(screen.getByText("See more (3 more)")).toBeInTheDocument();
    });

    it("reveals the full answer and switches the toggle to See less when clicked", () => {
      const messages = [
        {
          id: "a1", role: "assistant" as const, content: longContent,
          created_at: "2026-01-01", answer_kind: "answer" as const,
          export: { message_id: "a1", row_count: 8, formats: ["csv", "xlsx"] },
        },
      ];
      render(<MessageThread messages={messages} loading={false} />);
      fireEvent.click(screen.getByText("See more (3 more)"));
      expect(screen.getByText("Name Eight", { exact: false })).toBeInTheDocument();
      expect(screen.getByText("See less")).toBeInTheDocument();
    });

    it("does not truncate a long answer that has no export/result-count data at all", () => {
      // Truncation is driven by result count (export.row_count), not raw line
      // count — a long free-text answer with no structured result behind it
      // (e.g. answered from document chunks) has no "how many results" signal
      // to truncate against, so it renders in full regardless of length.
      const messages = [
        {
          id: "a1", role: "assistant" as const, content: longContent,
          created_at: "2026-01-01", answer_kind: "answer" as const,
        },
      ];
      render(<MessageThread messages={messages} loading={false} />);
      expect(screen.getByText("Name Eight", { exact: false })).toBeInTheDocument();
      expect(screen.queryByText(/See more/)).not.toBeInTheDocument();
      expect(screen.queryByLabelText("Download CSV")).not.toBeInTheDocument();
    });

    it("does not truncate, and shows no export card or See more, for a short answer even with export data", () => {
      const messages = [
        {
          id: "a1", role: "assistant" as const, content: shortContent,
          created_at: "2026-01-01", answer_kind: "answer" as const,
          export: { message_id: "a1", row_count: 250, formats: ["csv", "xlsx"] },
        },
      ];
      render(<MessageThread messages={messages} loading={false} />);
      expect(screen.queryByLabelText("Download CSV")).not.toBeInTheDocument();
      expect(screen.queryByText(/See more/)).not.toBeInTheDocument();
    });

    it("does not truncate a detailed single-result answer, even with many lines", () => {
      // Regression: "give me one single candidate" renders a multi-line detail
      // breakdown (job title, experience, education...) about ONE result — this
      // must show in full, not be treated as a long list just because the text
      // happens to span more than 5 lines.
      const singleCandidateDetail = [
        "The most apt candidate for a React JS Developer role is **Allwin J Andrews**.",
        "**Job Title:** React JS Developer",
        "**Experience:**",
        "Currently working at Labglo, Trivandrum since December 2018.",
        "**Education:**",
        "B.Tech in Computer Science",
        "**Skills:** React, JavaScript, Redux",
      ].join("\n\n");
      const messages = [
        {
          id: "a1", role: "assistant" as const, content: singleCandidateDetail,
          created_at: "2026-01-01", answer_kind: "answer" as const,
          export: { message_id: "a1", row_count: 1, formats: ["csv", "xlsx"] },
        },
      ];
      render(<MessageThread messages={messages} loading={false} />);
      expect(screen.getByText(/Computer Science/)).toBeInTheDocument();
      expect(screen.getByText(/React, JavaScript, Redux/)).toBeInTheDocument();
      expect(screen.queryByLabelText("Download CSV")).not.toBeInTheDocument();
      expect(screen.queryByText(/See more/)).not.toBeInTheDocument();
    });

    it("hides truncation and the export card while the message is still streaming", () => {
      const messages = [
        {
          id: "a1", role: "assistant" as const, content: longContent,
          created_at: "2026-01-01", isStreaming: true,
          export: { message_id: "a1", row_count: 8, formats: ["csv", "xlsx"] },
        },
      ];
      render(<MessageThread messages={messages} loading={false} />);
      expect(screen.queryByLabelText("Download CSV")).not.toBeInTheDocument();
      expect(screen.queryByText(/See more/)).not.toBeInTheDocument();
    });
  });
});
