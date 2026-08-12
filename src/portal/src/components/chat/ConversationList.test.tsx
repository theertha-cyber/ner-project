import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { ConversationList } from "./ConversationList";

describe("ConversationList", () => {
  const defaultProps = {
    conversations: [],
    onSelect: vi.fn(),
    onNew: vi.fn(),
    onDelete: vi.fn(),
  };

  const conversations = [
    { id: "c1", title: "Original title", created_at: "2026-01-01", message_count: 5 },
    { id: "c2", title: "Chat 2", created_at: "2026-01-02", message_count: 3 },
  ];

  function rowFor(title: string): HTMLElement {
    return screen.getByText(title).closest("div[style]") as HTMLElement;
  }

  // Every row carries an options trigger, so menu actions are scoped to the row
  // they belong to.
  function openMenu(title: string) {
    const row = rowFor(title);
    fireEvent.mouseEnter(row);
    fireEvent.click(within(row).getByLabelText("Conversation options"));
  }

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the header actions without repeating the topbar page title", () => {
    render(<ConversationList {...defaultProps} />);
    expect(screen.getByRole("button", { name: /new chat/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Search chats" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Chats" })).not.toBeInTheDocument();
  });

  it("shows loading state when loading prop is true", () => {
    render(<ConversationList {...defaultProps} loading={true} />);
    expect(screen.getByText("Creating...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /creating/i })).toBeDisabled();
  });

  it("calls onNew when the new chat button is clicked", () => {
    const onNew = vi.fn();
    render(<ConversationList {...defaultProps} onNew={onNew} />);
    fireEvent.click(screen.getByRole("button", { name: /new chat/i }));
    expect(onNew).toHaveBeenCalledTimes(1);
  });

  it("does not call onNew when loading", () => {
    const onNew = vi.fn();
    render(<ConversationList {...defaultProps} onNew={onNew} loading={true} />);
    fireEvent.click(screen.getByRole("button", { name: /creating/i }));
    expect(onNew).not.toHaveBeenCalled();
  });

  it("renders the conversation list with metadata", () => {
    render(<ConversationList {...defaultProps} conversations={conversations} />);
    expect(screen.getByText("Original title")).toBeInTheDocument();
    expect(screen.getByText("Chat 2")).toBeInTheDocument();
    expect(screen.getByText(/5 messages/)).toBeInTheDocument();
  });

  it("calls onSelect when a conversation row is clicked", () => {
    const onSelect = vi.fn();
    render(<ConversationList {...defaultProps} conversations={conversations} onSelect={onSelect} />);
    fireEvent.click(screen.getByText("Chat 2"));
    expect(onSelect).toHaveBeenCalledWith("c2");
  });

  it("shows empty state when no conversations", () => {
    render(<ConversationList {...defaultProps} />);
    expect(screen.getByText("No conversations yet")).toBeInTheDocument();
  });

  it("filters conversations by search query", () => {
    render(<ConversationList {...defaultProps} conversations={conversations} />);
    fireEvent.click(screen.getByRole("button", { name: "Search chats" }));
    fireEvent.change(screen.getByLabelText("Search chats"), { target: { value: "chat 2" } });
    expect(screen.getByText("Chat 2")).toBeInTheDocument();
    expect(screen.queryByText("Original title")).not.toBeInTheDocument();
  });

  it("keeps the message count and date visible while the row is hovered", () => {
    render(<ConversationList {...defaultProps} conversations={conversations} onRename={vi.fn()} />);
    const row = rowFor("Original title");
    fireEvent.mouseEnter(row);
    expect(within(row).getByText(/5 messages/)).toBeInTheDocument();
    expect(within(row).getByLabelText("Conversation options")).toBeVisible();
  });

  it("closes the menu on a mousedown outside it", () => {
    render(<ConversationList {...defaultProps} conversations={conversations} onRename={vi.fn()} />);
    openMenu("Original title");
    expect(screen.getByRole("menu")).toBeInTheDocument();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("keeps the menu open through the mousedown that precedes a menu item click", () => {
    // Regression: dismiss-on-outside-mousedown used to fire for presses inside
    // the menu too, so the item unmounted before its click ever landed.
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const onDelete = vi.fn();
    render(
      <ConversationList {...defaultProps} conversations={conversations} onDelete={onDelete} onRename={vi.fn()} />
    );
    openMenu("Original title");
    const item = screen.getByTitle("Delete conversation");
    fireEvent.mouseDown(item);
    expect(screen.getByRole("menu")).toBeInTheDocument();
    fireEvent.click(item);
    expect(onDelete).toHaveBeenCalledWith("c1");
  });

  it("only offers rename and delete in the row menu", () => {
    render(<ConversationList {...defaultProps} conversations={conversations} onRename={vi.fn()} />);
    openMenu("Original title");
    const items = screen.getAllByRole("menuitem").map((el) => el.textContent);
    expect(items).toEqual(["Rename", "Delete"]);
  });

  describe("rename", () => {
    it("opens inline edit from the menu", () => {
      render(<ConversationList {...defaultProps} conversations={conversations} onRename={vi.fn()} />);
      openMenu("Original title");
      fireEvent.click(screen.getByTitle("Rename conversation"));
      expect(screen.getByDisplayValue("Original title")).toBeInTheDocument();
    });

    it("confirms rename with Enter and calls onRename with the new title", () => {
      const onRename = vi.fn();
      render(<ConversationList {...defaultProps} conversations={conversations} onRename={onRename} />);
      openMenu("Original title");
      fireEvent.click(screen.getByTitle("Rename conversation"));
      const input = screen.getByDisplayValue("Original title");
      fireEvent.change(input, { target: { value: "Renamed chat" } });
      fireEvent.keyDown(input, { key: "Enter" });
      expect(onRename).toHaveBeenCalledWith("c1", "Renamed chat");
      expect(screen.queryByDisplayValue("Renamed chat")).not.toBeInTheDocument();
    });

    it("cancels rename with Escape without calling onRename", () => {
      const onRename = vi.fn();
      render(<ConversationList {...defaultProps} conversations={conversations} onRename={onRename} />);
      openMenu("Original title");
      fireEvent.click(screen.getByTitle("Rename conversation"));
      const input = screen.getByDisplayValue("Original title");
      fireEvent.change(input, { target: { value: "Some draft" } });
      fireEvent.keyDown(input, { key: "Escape" });
      expect(onRename).not.toHaveBeenCalled();
      expect(screen.getByText("Original title")).toBeInTheDocument();
    });

    it("does not offer rename when onRename is not provided", () => {
      render(<ConversationList {...defaultProps} conversations={conversations} />);
      openMenu("Original title");
      expect(screen.queryByTitle("Rename conversation")).not.toBeInTheDocument();
      expect(screen.getByTitle("Delete conversation")).toBeInTheDocument();
    });

    it("keeps the previous title displayed when the rename call fails", () => {
      // Simulates the page-level failure path: onRename is called, but since the
      // API call failed, the parent never updates the conversations prop, so the
      // list continues to render the previous title.
      const onRename = vi.fn();
      const { rerender } = render(
        <ConversationList {...defaultProps} conversations={conversations} onRename={onRename} />
      );
      openMenu("Original title");
      fireEvent.click(screen.getByTitle("Rename conversation"));
      const input = screen.getByDisplayValue("Original title");
      fireEvent.change(input, { target: { value: "Renamed chat" } });
      fireEvent.keyDown(input, { key: "Enter" });
      expect(onRename).toHaveBeenCalledWith("c1", "Renamed chat");

      rerender(<ConversationList {...defaultProps} conversations={conversations} onRename={onRename} />);
      expect(screen.getByText("Original title")).toBeInTheDocument();
    });
  });

  describe("delete", () => {
    it("calls onDelete when the confirmation is accepted", () => {
      vi.spyOn(window, "confirm").mockReturnValue(true);
      const onDelete = vi.fn();
      render(<ConversationList {...defaultProps} conversations={conversations} onDelete={onDelete} />);
      openMenu("Original title");
      fireEvent.click(screen.getByTitle("Delete conversation"));
      expect(onDelete).toHaveBeenCalledWith("c1");
    });

    it("does not call onDelete when the confirmation is dismissed", () => {
      vi.spyOn(window, "confirm").mockReturnValue(false);
      const onDelete = vi.fn();
      render(<ConversationList {...defaultProps} conversations={conversations} onDelete={onDelete} />);
      openMenu("Original title");
      fireEvent.click(screen.getByTitle("Delete conversation"));
      expect(onDelete).not.toHaveBeenCalled();
    });
  });
});
