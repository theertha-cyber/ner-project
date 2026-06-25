import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ActivityPanel } from "./ActivityPanel";
import type { ActivityRow } from "@/types/dashboard";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const rows: ActivityRow[] = [
  { title: "Job 1", sub: "details 1", tag: "running", tk: "running", go: "training" },
  { title: "Job 2", sub: "details 2", tag: "pending", tk: "pending_approval", go: "training" },
  { title: "\u2014", sub: "\u2014", tag: "\u2014", tk: "queued", go: "training" },
  { title: "\u2014", sub: "\u2014", tag: "\u2014", tk: "queued", go: "training" },
];

describe("ActivityPanel", () => {
  it("renders title and meta", () => {
    render(<ActivityPanel pTitle="Approval queue" pMeta="system_admin" pRows={rows} />);
    expect(screen.getByText("Approval queue")).toBeInTheDocument();
    expect(screen.getByText("system_admin")).toBeInTheDocument();
  });

  it("renders all 4 rows", () => {
    render(<ActivityPanel pTitle="Title" pMeta="meta" pRows={rows} />);
    expect(screen.getByText("Job 1")).toBeInTheDocument();
    expect(screen.getByText("Job 2")).toBeInTheDocument();
  });

  it("renders running tag with colour", () => {
    render(<ActivityPanel pTitle="Title" pMeta="meta" pRows={rows} />);
    const tag = screen.getByText("running");
    expect(tag).toBeInTheDocument();
  });

  it("tag is right-aligned (after title/sub)", () => {
    const { container } = render(<ActivityPanel pTitle="Title" pMeta="meta" pRows={rows} />);
    const buttons = container.querySelectorAll("button");
    const firstButton = buttons[0];
    const children = Array.from(firstButton.children);
    const lastChild = children[children.length - 1] as HTMLElement;
    expect(lastChild.textContent).toBe("running");
  });

  it("has dot indicator before title (first child of each row)", () => {
    const { container } = render(<ActivityPanel pTitle="Title" pMeta="meta" pRows={rows} />);
    const buttons = container.querySelectorAll("button");
    const firstButton = buttons[0];
    const firstChild = firstButton.firstChild as HTMLElement;
    expect(firstChild.style.borderRadius).toBe("50%");
    expect(firstChild.style.width).toBe("8px");
    expect(firstChild.style.height).toBe("8px");
  });

  it("row uses 12px padding", () => {
    const { container } = render(<ActivityPanel pTitle="Title" pMeta="meta" pRows={rows} />);
    const buttons = container.querySelectorAll("button");
    const firstButton = buttons[0];
    expect(firstButton.style.padding).toBe("12px");
  });
});
