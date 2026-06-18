import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ToastProvider, useToast } from "./use-toast";

function ToastButton({ message, kind }: { message: string; kind?: "ok" | "bad" }) {
  const { toast } = useToast();
  return <button onClick={() => toast(message, kind)}>fire</button>;
}

describe("useToast (real timers)", () => {
  it("toast appears in DOM after call", async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <ToastButton message="Operation succeeded" kind="ok" />
      </ToastProvider>,
    );
    await user.click(screen.getByRole("button", { name: "fire" }));
    expect(screen.getByText("Operation succeeded")).toBeInTheDocument();
  });

  it("ok kind renders with success colour class", async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <ToastButton message="Saved" kind="ok" />
      </ToastProvider>,
    );
    await user.click(screen.getByRole("button", { name: "fire" }));
    expect(screen.getByRole("alert")).toHaveClass("bg-success");
  });

  it("bad kind renders with error colour class", async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <ToastButton message="Failed" kind="bad" />
      </ToastProvider>,
    );
    await user.click(screen.getByRole("button", { name: "fire" }));
    expect(screen.getByRole("alert")).toHaveClass("bg-error");
  });

  it("throws when useToast is called outside ToastProvider", () => {
    function Bare() {
      useToast();
      return null;
    }
    expect(() => render(<Bare />)).toThrow("useToast must be used within ToastProvider");
  });
});

describe("useToast (fake timers)", () => {
  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it("banner is removed after 4000ms", () => {
    vi.useFakeTimers();
    render(
      <ToastProvider>
        <ToastButton message="Processing" />
      </ToastProvider>,
    );
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "fire" }));
    });
    expect(screen.getByText("Processing")).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(4000);
    });
    expect(screen.queryByText("Processing")).not.toBeInTheDocument();
  });

  it("fourth toast replaces oldest, keeps count at 3", () => {
    vi.useFakeTimers();
    function MultiToast() {
      const { toast } = useToast();
      return (
        <button
          onClick={() => {
            toast("msg1");
            toast("msg2");
            toast("msg3");
            toast("msg4");
          }}
        >
          fire
        </button>
      );
    }
    render(
      <ToastProvider>
        <MultiToast />
      </ToastProvider>,
    );
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "fire" }));
    });
    expect(screen.getAllByRole("alert")).toHaveLength(3);
    expect(screen.queryByText("msg1")).not.toBeInTheDocument();
    expect(screen.getByText("msg4")).toBeInTheDocument();
  });
});

describe("useToast hook barrel", () => {
  it("useToast is importable from hooks barrel", async () => {
    const mod = await import("@/hooks");
    expect(typeof mod.useToast).toBe("function");
    expect(typeof mod.ToastProvider).toBe("function");
  });
});
