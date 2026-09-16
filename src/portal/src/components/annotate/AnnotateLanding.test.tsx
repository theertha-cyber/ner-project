import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { AnnotateLanding, WorkCard } from "./AnnotateLanding";

vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({ push: vi.fn() })),
}));

const workCards: WorkCard[] = [
  { title: "1. Do a thing", description: "First step.", cta: "Do it", href: "/somewhere" },
];

describe("AnnotateLanding — primary action placement", () => {
  it("defaults to rendering the primary action beside the heading", () => {
    const { container } = render(
      <AnnotateLanding
        heading="Test"
        intro="intro"
        primaryAction={{ label: "Go", onClick: vi.fn() }}
        workCards={workCards}
      />,
    );

    const headingRow = screen.getByText("Test").closest("div")?.parentElement;
    expect(headingRow?.textContent).toContain("Go");
  });

  it("renders the primary action below the work cards when positioned there", () => {
    render(
      <AnnotateLanding
        heading="Test"
        intro="intro"
        primaryAction={{ label: "Start with step 1", onClick: vi.fn() }}
        primaryActionPosition="belowWorkCards"
        workCards={workCards}
        workCardsLabel="Before you begin"
      />,
    );

    const button = screen.getByText("Start with step 1");
    const workCardsHeading = screen.getByText("Before you begin");

    // The button's position in the DOM comes after the work-cards section, not beside the
    // heading — the exact confusion ("which do I click first?") this option exists to remove.
    expect(
      workCardsHeading.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();

    const headingRow = screen.getByText("Test").closest("div")?.parentElement;
    expect(headingRow?.textContent).not.toContain("Start with step 1");
  });

  it("still shows the disabled reason when positioned below the work cards", () => {
    render(
      <AnnotateLanding
        heading="Test"
        intro="intro"
        primaryAction={{
          label: "Go",
          onClick: vi.fn(),
          disabled: true,
          disabledReason: "Blocked: no seed documents",
        }}
        primaryActionPosition="belowWorkCards"
        workCards={workCards}
      />,
    );

    expect(screen.getByText("Go")).toBeDisabled();
    expect(screen.getByText("Blocked: no seed documents")).toBeDefined();
  });
});
