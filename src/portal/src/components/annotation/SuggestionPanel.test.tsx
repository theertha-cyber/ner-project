import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { SuggestionPanel } from "./SuggestionPanel";
import type { SuggestedSpan } from "./span-reducer";

const suggestions: SuggestedSpan[] = [
  { id: "s-1", entityType: "vendor_name", charStart: 0, charEnd: 9, text: "Acme Corp", confidence: 0.85 },
  { id: "s-2", entityType: "customer_name", charStart: 10, charEnd: 20, text: "BigCo Ltd", confidence: 0.72 },
];

const entityColors = {
  vendor_name: "#6366f1",
  customer_name: "#f59e0b",
};

// ── Scenario 21 (task 8.3): Dashed cards with text/type/confidence ───────────

describe("Scenario 21 — Pre-label populates dashed-border suggestion cards", () => {
  it("renders each suggestion as a card with span text, entity type, and confidence", () => {
    render(
      <SuggestionPanel
        suggestions={suggestions}
        entityColors={entityColors}
        onPromote={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );

    // First suggestion
    expect(screen.getByTestId("suggestion-card-s-1")).toBeInTheDocument();
    expect(screen.getByTestId("suggestion-text-s-1")).toHaveTextContent("Acme Corp");
    expect(screen.getByTestId("suggestion-meta-s-1")).toHaveTextContent("vendor_name · conf 0.85");

    // Second suggestion
    expect(screen.getByTestId("suggestion-card-s-2")).toBeInTheDocument();
    expect(screen.getByTestId("suggestion-text-s-2")).toHaveTextContent("BigCo Ltd");
    expect(screen.getByTestId("suggestion-meta-s-2")).toHaveTextContent("customer_name · conf 0.72");
  });

  it("renders dashed border cards (Promote and ✕ buttons)", () => {
    render(
      <SuggestionPanel
        suggestions={suggestions}
        entityColors={entityColors}
        onPromote={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );

    expect(screen.getByTestId("promote-btn-s-1")).toBeInTheDocument();
    expect(screen.getByTestId("dismiss-btn-s-1")).toBeInTheDocument();
  });
});

// ── Scenario 22 (task 8.3): Promote calls onPromote ─────────────────────────

describe("Scenario 22 — Promote converts a suggestion to a confirmed span", () => {
  it("clicking Promote calls onPromote with the suggestion id", () => {
    const onPromote = vi.fn();
    render(
      <SuggestionPanel
        suggestions={suggestions}
        entityColors={entityColors}
        onPromote={onPromote}
        onDismiss={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByTestId("promote-btn-s-1"));
    expect(onPromote).toHaveBeenCalledWith("s-1");
    expect(onPromote).toHaveBeenCalledOnce();
  });
});

// ── Scenario 23 (task 8.3): Dismiss removes card without API call ────────────

describe("Scenario 23 — Dismiss removes suggestion locally", () => {
  it("clicking ✕ calls onDismiss with the suggestion id (no API call)", () => {
    const onDismiss = vi.fn();
    render(
      <SuggestionPanel
        suggestions={suggestions}
        entityColors={entityColors}
        onPromote={vi.fn()}
        onDismiss={onDismiss}
      />,
    );

    fireEvent.click(screen.getByTestId("dismiss-btn-s-1"));
    expect(onDismiss).toHaveBeenCalledWith("s-1");
    expect(onDismiss).toHaveBeenCalledOnce();
  });
});
