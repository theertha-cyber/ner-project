import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({ push: mockPush })),
}));

import AutomatedLandingPage from "./page";

describe("AutomatedLandingPage", () => {
  beforeEach(() => {
    mockPush.mockClear();
  });

  it("shows upload entry points before step 1, each routing with the right purpose/mode", () => {
    render(<AutomatedLandingPage />);

    expect(screen.getByText("Before you begin")).toBeDefined();
    expect(screen.getByText("Upload documents")).toBeDefined();
    expect(screen.getByText("Upload Q&A pair")).toBeDefined();

    fireEvent.click(screen.getByText("Upload documents →"));
    expect(mockPush).toHaveBeenCalledWith("/documents?upload=1&purpose=training&mode=automated");

    fireEvent.click(screen.getByText("Upload Q&A pair →"));
    expect(mockPush).toHaveBeenCalledWith("/documents?upload=1&purpose=qa_pair");
  });

  it("still routes to step 1 from the primary action", () => {
    render(<AutomatedLandingPage />);

    fireEvent.click(screen.getByText("Start with step 1"));
    expect(mockPush).toHaveBeenCalledWith("/annotate/automated/schema");
  });

  it("places 'Start with step 1' after the 'Before you begin' cards, not beside the heading", () => {
    render(<AutomatedLandingPage />);

    const workCardsHeading = screen.getByText("Before you begin");
    const button = screen.getByText("Start with step 1");
    expect(
      workCardsHeading.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("names retraining as a separate, optional decision reachable from Models & Training", () => {
    render(<AutomatedLandingPage />);

    expect(
      screen.getByText(/Retraining itself is a separate, optional decision/),
    ).toBeDefined();
    expect(screen.getByText(/find it under Models & Training/)).toBeDefined();
    expect(screen.queryByText(/retraining unlocks/i)).toBeNull();
  });
});
