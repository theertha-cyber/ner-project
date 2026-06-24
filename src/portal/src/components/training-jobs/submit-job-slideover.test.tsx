import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SubmitJobSlideover } from "./submit-job-slideover";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("SubmitJobSlideover", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValue(
      new Response("token1\ntoken2\ntoken3\n", { status: 200 }),
    );
  });

  it("shows preflight check with span count", async () => {
    render(
      <SubmitJobSlideover open={true} onClose={vi.fn()} />,
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(screen.getByText(/3 confirmed spans/)).toBeDefined();
    });
  });

  it("shows warning for insufficient spans", async () => {
    mockFetch.mockResolvedValue(
      new Response("span1\nspan2\n", { status: 200 }),
    );

    render(
      <SubmitJobSlideover open={true} onClose={vi.fn()} />,
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(screen.getByText(/requires 500 minimum/)).toBeDefined();
    });
  });

  it("shows field-level validation for negative epochs", async () => {
    mockFetch.mockResolvedValue(
      new Response(new Array(600).fill("x").join("\n"), { status: 200 }),
    );

    render(
      <SubmitJobSlideover open={true} onClose={vi.fn()} />,
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(screen.getByText(/meets the 500-span minimum/)).toBeDefined();
    });
  });

  it("calls onClose after successful submission", async () => {
    mockFetch
      .mockResolvedValueOnce(new Response(new Array(600).fill("x").join("\n"), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: "new-job", status: "pending_approval" }), { status: 201 }),
      );

    const onClose = vi.fn();

    render(
      <SubmitJobSlideover open={true} onClose={onClose} />,
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /submit training job/i })).toBeDefined();
    });

    const submitBtn = screen.getByRole("button", { name: /submit training job/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(onClose).toHaveBeenCalled();
    });
  });
});
