import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "./badge";

describe("Badge", () => {
  it("renders correct colour class for running variant", () => {
    const { container } = render(<Badge variant="running" />);
    expect(container.firstChild).toHaveClass("bg-status-running");
  });

  it("displays variant string as default label", () => {
    render(<Badge variant="pending_approval" />);
    expect(screen.getByText("pending approval")).toBeInTheDocument();
  });

  it("displays custom label when provided", () => {
    render(<Badge variant="pending_approval" label="Needs Review" />);
    expect(screen.getByText("Needs Review")).toBeInTheDocument();
    expect(screen.queryByText("pending approval")).not.toBeInTheDocument();
  });

  it("renders without runtime error for each valid variant", () => {
    const variants = [
      "active",
      "inactive",
      "running",
      "completed",
      "failed",
      "pending_approval",
      "queued",
      "rejected",
      "cancelled",
      "promoted",
    ] as const;
    for (const variant of variants) {
      expect(() => render(<Badge variant={variant} />)).not.toThrow();
    }
  });
});
