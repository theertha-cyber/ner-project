import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ExtractionPage } from "./ExtractionPage";

vi.mock("./PlaygroundTab", () => ({
  PlaygroundTab: () => <div data-testid="playground-tab">Playground content</div>,
}));

vi.mock("./BatchRunsTab", () => ({
  BatchRunsTab: () => <div data-testid="batch-tab">Batch Runs content</div>,
}));

vi.mock("./EntityReviewTab", () => ({
  EntityReviewTab: () => <div data-testid="entities-tab">Entity Review content</div>,
}));

describe("ExtractionPage", () => {
  it("Test 1: renders Extraction heading, three tabs, Playground content, Playground tab active by default", () => {
    render(<ExtractionPage />);

    expect(screen.getByRole("heading", { level: 1 })).toBeDefined();
    expect(screen.getByText("Extraction")).toBeDefined();

    expect(screen.getByText("Playground")).toBeDefined();
    expect(screen.getByText("Batch Runs")).toBeDefined();
    expect(screen.getByText("Entity Review")).toBeDefined();

    expect(screen.getByTestId("playground-tab")).toBeDefined();
    expect(screen.queryByTestId("batch-tab")).toBeNull();
    expect(screen.queryByTestId("entities-tab")).toBeNull();

    const playgroundBtn = screen.getByText("Playground");
    expect(playgroundBtn.getAttribute("aria-pressed")).toBe("true");
  });

  it("Test 2: clicking Batch Runs shows batch content and Playground is absent from DOM", () => {
    render(<ExtractionPage />);

    fireEvent.click(screen.getByText("Batch Runs"));

    expect(screen.queryByTestId("playground-tab")).toBeNull();
    expect(screen.getByTestId("batch-tab")).toBeDefined();

    const batchBtn = screen.getByText("Batch Runs");
    expect(batchBtn.getAttribute("aria-pressed")).toBe("true");
  });
});
