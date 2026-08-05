import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { BaseModelCard, BASE_MODEL_NAME } from "./base-model-card";
import { BaseModelPanel } from "./base-model-panel";

describe("BaseModelCard", () => {
  it("renders the base model name and fires onClick", () => {
    const onClick = vi.fn();
    render(<BaseModelCard isActive={false} isSelected={false} onClick={onClick} />);
    expect(screen.getByText("Base Model")).toBeDefined();
    expect(screen.getByText(BASE_MODEL_NAME)).toBeDefined();
    fireEvent.click(screen.getByText("Base Model"));
    expect(onClick).toHaveBeenCalled();
  });

  it("shows a promoted badge while the base model is serving", () => {
    render(<BaseModelCard isActive={true} isSelected={false} onClick={() => {}} />);
    expect(screen.getByText("promoted")).toBeDefined();
  });

  it("shows an archived badge once a fine-tuned model serves", () => {
    render(<BaseModelCard isActive={false} isSelected={false} onClick={() => {}} />);
    expect(screen.getByText("archived")).toBeDefined();
  });
});

describe("BaseModelPanel", () => {
  it("renders the supported CoNLL labels", () => {
    render(<BaseModelPanel />);
    expect(screen.getByText(BASE_MODEL_NAME)).toBeDefined();
    for (const label of ["PER", "ORG", "LOC", "MISC"]) {
      expect(screen.getByText(label)).toBeDefined();
    }
  });
});
