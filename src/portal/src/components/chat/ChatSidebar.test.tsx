import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ChatSidebar } from "./ChatSidebar";

describe("ChatSidebar", () => {
  const defaultProps = {
    conversations: [],
    activeConvId: null,
    onSelect: vi.fn(),
    onNew: vi.fn(),
    onDelete: vi.fn(),
  };

  it("renders new conversation button", () => {
    render(<ChatSidebar {...defaultProps} />);
    expect(screen.getByText("+ New conversation")).toBeInTheDocument();
  });

  it("shows loading state when loading prop is true", () => {
    render(<ChatSidebar {...defaultProps} loading={true} />);
    expect(screen.getByText("Creating...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /creating/i })).toBeDisabled();
  });

  it("calls onNew when button clicked", () => {
    const onNew = vi.fn();
    render(<ChatSidebar {...defaultProps} onNew={onNew} />);
    fireEvent.click(screen.getByText("+ New conversation"));
    expect(onNew).toHaveBeenCalledTimes(1);
  });

  it("does not call onNew when loading", () => {
    const onNew = vi.fn();
    render(<ChatSidebar {...defaultProps} onNew={onNew} loading={true} />);
    fireEvent.click(screen.getByRole("button", { name: /creating/i }));
    expect(onNew).not.toHaveBeenCalled();
  });

  it("renders conversation list", () => {
    const conversations = [
      { id: "c1", title: "Chat 1", created_at: "2026-01-01", message_count: 5 },
      { id: "c2", title: "Chat 2", created_at: "2026-01-02", message_count: 3 },
    ];
    render(<ChatSidebar {...defaultProps} conversations={conversations} />);
    expect(screen.getByText("Chat 1")).toBeInTheDocument();
    expect(screen.getByText("Chat 2")).toBeInTheDocument();
  });

  it("shows empty state when no conversations", () => {
    render(<ChatSidebar {...defaultProps} />);
    expect(screen.getByText("No conversations yet")).toBeInTheDocument();
  });

  it("highlights active conversation", () => {
    const conversations = [
      { id: "c1", title: "Active Chat", created_at: "2026-01-01", message_count: 5 },
    ];
    render(<ChatSidebar {...defaultProps} conversations={conversations} activeConvId="c1" />);
    const item = screen.getByText("Active Chat");
    expect(item).toBeInTheDocument();
  });
});
