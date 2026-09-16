import { describe, it, expect, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TruncatableReply } from "./TruncatableReply";

// jsdom never lays out real boxes, so scrollHeight/clientHeight are always 0.
// Stub them per-test to simulate whether the clamp actually clipped anything —
// this is the same scrollHeight-vs-clientHeight technique the component itself
// uses against a real browser.
function mockOverflow(overflowing: boolean) {
  Object.defineProperty(HTMLElement.prototype, "scrollHeight", {
    configurable: true,
    value: overflowing ? 400 : 100,
  });
  Object.defineProperty(HTMLElement.prototype, "clientHeight", {
    configurable: true,
    value: 100,
  });
}

afterEach(() => {
  // @ts-expect-error -- restore to jsdom's own (non-configurable-safe) defaults
  delete HTMLElement.prototype.scrollHeight;
  // @ts-expect-error
  delete HTMLElement.prototype.clientHeight;
});

describe("TruncatableReply", () => {
  it("clips and shows a See more toggle when the rendered content overflows", () => {
    mockOverflow(true);
    render(<TruncatableReply content="A very long reply that overflows its bounded height." />);
    expect(screen.getByText("See more")).toBeInTheDocument();
  });

  it("does not show a toggle when the rendered content fits", () => {
    mockOverflow(false);
    render(<TruncatableReply content="A short reply." />);
    expect(screen.queryByText(/See more/)).not.toBeInTheDocument();
  });

  it("clicking See more reveals the full reply and flips the toggle to See less; clicking again re-collapses it", () => {
    mockOverflow(true);
    render(<TruncatableReply content="Long content that overflows." />);

    fireEvent.click(screen.getByText("See more"));
    expect(screen.getByText("See less")).toBeInTheDocument();

    fireEvent.click(screen.getByText("See less"));
    expect(screen.getByText("See more")).toBeInTheDocument();
  });

  it("applies the clamp class by default, before any overflow measurement resolves", () => {
    mockOverflow(true);
    const { container } = render(<TruncatableReply content="Some content." />);
    expect(container.querySelector(".chat-reply-clamp")).toBeTruthy();
  });

  it("removes the clamp class once expanded", () => {
    mockOverflow(true);
    const { container } = render(<TruncatableReply content="Some content." />);
    fireEvent.click(screen.getByText("See more"));
    expect(container.querySelector(".chat-reply-clamp")).toBeNull();
  });
});
