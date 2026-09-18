import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ChatInput, type StagedFile } from "./ChatInput";

function makeFile(name: string, type = "application/pdf", size = 128) {
  return new File(["x".repeat(size)], name, { type });
}

function staged(id: string, name: string): StagedFile {
  return { id, name, size: 128, type: "application/pdf", file: makeFile(name) };
}

const noop = () => undefined;

// Covers verification.md § Spec Alignment rows for scenarios 1, 2, 3, 6, 7
// (chat-composer-attachments spec).
describe("ChatInput — attachment staging", () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn();
  });

  it("renders one tray entry per staged file plus the reserve hint (Scenario 1)", () => {
    render(
      <ChatInput
        onSend={noop}
        disabled={false}
        stagedFiles={[staged("1", "invoice.pdf"), staged("2", "data.csv")]}
        onAttach={noop}
        onRemoveFile={noop}
      />
    );

    const tray = screen.getByRole("region", { name: "Staged attachments" });
    expect(tray).toBeInTheDocument();
    expect(screen.getByText("invoice.pdf")).toBeInTheDocument();
    expect(screen.getByText("data.csv")).toBeInTheDocument();
    expect(
      screen.getByText("Staging does not reserve the conversation until send.")
    ).toBeInTheDocument();
  });

  it("makes no network calls when files are staged (ADR-011 / FR-006)", () => {
    const fetchMock = vi.mocked(globalThis.fetch);
    const onAttach = vi.fn();
    const { container } = render(
      <ChatInput
        onSend={noop}
        disabled={false}
        stagedFiles={[]}
        onAttach={onAttach}
        onRemoveFile={noop}
      />
    );

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = makeFile("invoice.pdf");
    fireEvent.change(input, { target: { files: [file] } });

    expect(onAttach).toHaveBeenCalledWith([file]);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("removing a staged file leaves the other staged files (Scenario 2)", () => {
    const onRemoveFile = vi.fn();
    render(
      <ChatInput
        onSend={noop}
        disabled={false}
        stagedFiles={[staged("1", "a.pdf"), staged("2", "b.csv")]}
        onAttach={noop}
        onRemoveFile={onRemoveFile}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Remove a.pdf" }));

    expect(onRemoveFile).toHaveBeenCalledWith("1");
    expect(screen.getByText("a.pdf")).toBeInTheDocument();
    expect(screen.getByText("b.csv")).toBeInTheDocument();
  });

  it("rejects an unsupported extension with an inline alert and does not stage it (Scenario 3)", () => {
    const onAttach = vi.fn();
    const { container } = render(
      <ChatInput
        onSend={noop}
        disabled={false}
        stagedFiles={[]}
        onAttach={onAttach}
        onRemoveFile={noop}
      />
    );

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeFile("evil.exe")] } });

    expect(onAttach).not.toHaveBeenCalled();
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("Supported types");
    expect(alert.textContent).toContain("PDF");
  });

  it("stages only supported files from a mixed pick and alerts the rejection", () => {
    const onAttach = vi.fn();
    const { container } = render(
      <ChatInput
        onSend={noop}
        disabled={false}
        stagedFiles={[]}
        onAttach={onAttach}
        onRemoveFile={noop}
      />
    );

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const good = makeFile("ok.pdf");
    const bad = makeFile("bad.exe");
    fireEvent.change(input, { target: { files: [good, bad] } });

    expect(onAttach).toHaveBeenCalledWith([good]);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("attach and remove controls expose accessible names and activate (Scenario 6)", () => {
    const clickSpy = vi
      .spyOn(HTMLInputElement.prototype, "click")
      .mockImplementation(() => undefined);
    const onAttach = vi.fn();

    try {
      const { container } = render(
        <ChatInput
          onSend={noop}
          disabled={false}
          stagedFiles={[staged("1", "a.pdf")]}
          onAttach={onAttach}
          onRemoveFile={noop}
        />
      );

      const attach = screen.getByRole("button", { name: "Attach a file" });
      expect(attach).toBeEnabled();
      fireEvent.click(attach);
      expect(clickSpy).toHaveBeenCalledTimes(1);

      const remove = screen.getByRole("button", { name: "Remove a.pdf" });
      expect(remove).toBeEnabled();

      const input = container.querySelector('input[type="file"]') as HTMLInputElement;
      expect(input).not.toBeNull();
    } finally {
      clickSpy.mockRestore();
    }
  });

  it("keeps send disabled with files staged but no message text (Scenario 7)", () => {
    const onSend = vi.fn();
    render(
      <ChatInput
        onSend={onSend}
        disabled={false}
        stagedFiles={[staged("1", "a.pdf")]}
        onAttach={noop}
        onRemoveFile={noop}
      />
    );

    const send = screen.getByRole("button", { name: "Send message" });
    expect(send).toBeDisabled();

    const textarea = screen.getByPlaceholderText("Type your question...");
    fireEvent.keyDown(textarea, { key: "Enter" });
    expect(onSend).not.toHaveBeenCalled();
  });

  it("keeps send disabled while the disabled prop is set even with text", () => {
    render(
      <ChatInput
        onSend={noop}
        disabled={true}
        stagedFiles={[staged("1", "a.pdf")]}
        onAttach={noop}
        onRemoveFile={noop}
      />
    );

    const textarea = screen.getByPlaceholderText("Type your question...");
    fireEvent.change(textarea, { target: { value: "hello" } });

    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
  });
});
// Covers verification.md row 38 (chat-composer-attachments: in-flight progress).
describe("ChatInput — attachment send progress", () => {
  it("replaces the staging hint with an upload status while the send is in flight", () => {
    const { rerender } = render(
      <ChatInput
        onSend={noop}
        disabled={false}
        stagedFiles={[staged("1", "jd.pdf")]}
        onAttach={noop}
        onRemoveFile={noop}
      />
    );

    expect(
      screen.getByText("Staging does not reserve the conversation until send.")
    ).toBeInTheDocument();

    rerender(
      <ChatInput
        onSend={noop}
        disabled={true}
        stagedFiles={[staged("1", "jd.pdf")]}
        onAttach={noop}
        onRemoveFile={noop}
        uploading
      />
    );

    expect(
      screen.getByRole("status")
    ).toHaveTextContent("Uploading and preparing attachments");
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
    // Removing a file mid-flight would desync the tray from the request already sent.
    expect(screen.getByRole("button", { name: "Remove jd.pdf" })).toBeDisabled();
  });
});
