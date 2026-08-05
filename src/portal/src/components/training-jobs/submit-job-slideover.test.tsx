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

  it("enables submit with span count below 500", async () => {
    mockFetch.mockResolvedValue(
      new Response("span1\nspan2\n", { status: 200 }),
    );

    render(
      <SubmitJobSlideover open={true} onClose={vi.fn()} />,
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(screen.getByText(/2 confirmed spans/)).toBeDefined();
    });
    expect(screen.queryByText(/minimum/)).toBeNull();
    expect(screen.getByRole("button", { name: /submit training job/i })).not.toBeDisabled();
  });

  it("shows plain span count with no threshold language when count is high", async () => {
    mockFetch.mockResolvedValue(
      new Response(new Array(600).fill("x").join("\n"), { status: 200 }),
    );

    render(
      <SubmitJobSlideover open={true} onClose={vi.fn()} />,
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(screen.getByText(/600 confirmed spans/)).toBeDefined();
    });
    expect(screen.queryByText(/minimum/)).toBeNull();
  });

  it("keeps submit enabled when span count fetch fails", async () => {
    mockFetch.mockResolvedValue(new Response("", { status: 500 }));

    render(
      <SubmitJobSlideover open={true} onClose={vi.fn()} />,
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(screen.getByText(/unable to check span count/i)).toBeDefined();
    });
    expect(screen.getByRole("button", { name: /submit training job/i })).not.toBeDisabled();
  });

  it("surfaces server error and keeps form open on 422 insufficient entities", async () => {
    mockFetch
      .mockResolvedValueOnce(new Response("span1\nspan2\n", { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ detail: "Insufficient annotated entities: 2. Minimum 500 required." }),
          { status: 422 },
        ),
      );

    render(
      <SubmitJobSlideover open={true} onClose={vi.fn()} />,
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /submit training job/i })).toBeDefined();
    });

    fireEvent.click(screen.getByRole("button", { name: /submit training job/i }));

    await waitFor(() => {
      expect(screen.getByText(/Insufficient annotated entities: 2\. Minimum 500 required\./)).toBeDefined();
    });
    expect(screen.getByRole("button", { name: /submit training job/i })).toBeDefined();
  });

  it("calls onClose after successful submission", async () => {
    mockFetch
      .mockResolvedValueOnce(new Response("span1\nspan2\n", { status: 200 }))
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

  it("renders no hyperparameter inputs and submits a hyperparameter-free body", async () => {
    mockFetch
      .mockResolvedValueOnce(new Response("span1\nspan2\n", { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: "new-job", status: "pending_approval" }), { status: 201 }),
      );

    const { container } = render(
      <SubmitJobSlideover open={true} onClose={vi.fn()} />,
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(screen.getByText(/2 confirmed spans/)).toBeDefined();
    });

    expect(container.querySelector('input[type="range"]')).toBeNull();
    expect(container.querySelectorAll("select")).toHaveLength(0);
    expect(screen.queryByLabelText(/learning rate/i)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /submit training job/i }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/v1/training-jobs",
        expect.objectContaining({ method: "POST", body: JSON.stringify({}) }),
      );
    });
  });
});
