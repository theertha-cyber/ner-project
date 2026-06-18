import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Spinner } from "./spinner";

describe("Spinner", () => {
  it("renders with md size class by default", () => {
    const { container } = render(<Spinner />);
    expect(container.firstChild).toHaveClass("size-6");
  });

  it("renders with sm size class when size=sm", () => {
    const { container } = render(<Spinner size="sm" />);
    expect(container.firstChild).toHaveClass("size-4");
    expect(container.firstChild).not.toHaveClass("size-6");
  });
});
