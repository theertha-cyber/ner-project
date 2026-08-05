import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ActivityPanel } from "./ActivityPanel";
import type { ActivityRow } from "@/types/dashboard";

const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: pushMock }) }));

const rows: ActivityRow[] = [
  { title: "Job 1", sub: "details 1", tag: "running", tk: "running", go: "training" },
  { title: "Job 2", sub: "details 2", tag: "pending", tk: "pending_approval", go: "training" },
  { title: "—", sub: "—", tag: "—", tk: "queued", go: "training" },
  { title: "—", sub: "—", tag: "—", tk: "queued", go: "training" },
];

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient();
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("ActivityPanel", () => {
  it("renders title and meta", () => {
    renderWithClient(<ActivityPanel pTitle="Approval queue" pMeta="system_admin" pRows={rows} />);
    expect(screen.getByText("Approval queue")).toBeInTheDocument();
    expect(screen.getByText("system_admin")).toBeInTheDocument();
  });

  it("renders all 4 rows", () => {
    renderWithClient(<ActivityPanel pTitle="Title" pMeta="meta" pRows={rows} />);
    expect(screen.getByText("Job 1")).toBeInTheDocument();
    expect(screen.getByText("Job 2")).toBeInTheDocument();
  });

  it("renders running tag with colour", () => {
    renderWithClient(<ActivityPanel pTitle="Title" pMeta="meta" pRows={rows} />);
    const tag = screen.getByText("running");
    expect(tag).toBeInTheDocument();
  });

  it("tag is right-aligned (after title/sub)", () => {
    const { container } = renderWithClient(<ActivityPanel pTitle="Title" pMeta="meta" pRows={rows} />);
    const buttons = container.querySelectorAll("button");
    const firstButton = buttons[0];
    const children = Array.from(firstButton.children);
    const lastChild = children[children.length - 1] as HTMLElement;
    expect(lastChild.textContent).toBe("running");
  });

  it("has dot indicator before title (first child of each row)", () => {
    const { container } = renderWithClient(<ActivityPanel pTitle="Title" pMeta="meta" pRows={rows} />);
    const buttons = container.querySelectorAll("button");
    const firstButton = buttons[0];
    const firstChild = firstButton.firstChild as HTMLElement;
    expect(firstChild.style.borderRadius).toBe("50%");
    expect(firstChild.style.width).toBe("8px");
    expect(firstChild.style.height).toBe("8px");
  });

  it("row uses 12px padding", () => {
    const { container } = renderWithClient(<ActivityPanel pTitle="Title" pMeta="meta" pRows={rows} />);
    const buttons = container.querySelectorAll("button");
    const firstButton = buttons[0];
    expect(firstButton.style.padding).toBe("12px");
  });

  it("shows View all button when expandable", () => {
    renderWithClient(
      <ActivityPanel pTitle="Pipeline activity" pMeta="recent activity" pRows={rows} expandable />,
    );
    expect(screen.getByText("View all")).toBeInTheDocument();
  });

  it("does not show View all button by default", () => {
    renderWithClient(<ActivityPanel pTitle="Title" pMeta="meta" pRows={rows} />);
    expect(screen.queryByText("View all")).not.toBeInTheDocument();
  });

  it("renders icon and relative timestamp", () => {
    const curatedRows: ActivityRow[] = [
      { title: "Model deployment", sub: "Version abc123... deployed", tag: "deployed", tk: "promoted", go: "models", icon: "deploy", time: "2 hours ago" },
    ];
    const { container } = renderWithClient(
      <ActivityPanel pTitle="Recent Activity" pMeta="recent activity" pRows={curatedRows} />,
    );
    expect(screen.getByText("· 2 hours ago")).toBeInTheDocument();
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("business_user conversation row navigates to /chat?conversation={id}", () => {
    pushMock.mockClear();
    const conversationRows: ActivityRow[] = [
      { title: "How do I export invoices", sub: "3 messages", tag: "conversation", tk: "completed", go: "chat", id: "conv-123" },
    ];
    renderWithClient(<ActivityPanel pTitle="Recent Conversations" pMeta="business_user" pRows={conversationRows} />);
    fireEvent.click(screen.getByText("How do I export invoices"));
    expect(pushMock).toHaveBeenCalledWith("/chat?conversation=conv-123");
  });
});
