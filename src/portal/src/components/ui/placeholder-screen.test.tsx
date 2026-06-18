import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PlaceholderScreen } from "./placeholder-screen";

describe("PlaceholderScreen", () => {
  it("renders the title text", () => {
    render(<PlaceholderScreen title="Model Registry" />);
    expect(screen.getByText("Model Registry")).toBeInTheDocument();
  });

  it("renders without error given only a title", () => {
    expect(() => render(<PlaceholderScreen title="Documents" />)).not.toThrow();
  });
});
