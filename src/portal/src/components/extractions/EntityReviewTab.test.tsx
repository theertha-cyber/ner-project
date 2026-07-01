import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { EntityReviewTab } from "./EntityReviewTab";
import type { EntityItem } from "@/types/extraction";

const mockAuthFetch = vi.fn();
vi.mock("@/lib/auth-fetch", () => ({
  authFetch: (...args: unknown[]) => mockAuthFetch(...args),
}));

function makeEntityListResponse(items: EntityItem[]) {
  return new Response(
    JSON.stringify({ items, total: items.length, page: 1, per_page: 20 }),
    { status: 200 }
  );
}

const ENTITY_FIXTURE: EntityItem = {
  id: "ent-001",
  run_id: "run-001",
  entity_id: "B-ORG",
  value: "Acme Corp",
  confidence: 0.998,
  review_status: "unreviewed",
  document_filename: "invoice-2026-00417.pdf",
};

describe("EntityReviewTab", () => {
  beforeEach(() => {
    mockAuthFetch.mockReset();
    mockAuthFetch.mockResolvedValue(makeEntityListResponse([]));
  });

  it("Test 12: GET /api/v1/entities called without reviewStatus param on mount; 'all' pill active", async () => {
    mockAuthFetch.mockResolvedValue(makeEntityListResponse([]));
    render(<EntityReviewTab />);

    await waitFor(() => expect(mockAuthFetch).toHaveBeenCalled());
    const callUrl = String(mockAuthFetch.mock.calls[0][0]);
    expect(callUrl).toBe("/api/v1/entities");
    expect(callUrl).not.toContain("reviewStatus");

    const allBtn = screen.getByRole("button", { name: "all" });
    expect(allBtn.hasAttribute("aria-pressed") || allBtn.style.background !== "").toBeTruthy();
  });

  it("Test 13: clicking 'unreviewed' pill triggers GET with reviewStatus=unreviewed", async () => {
    render(<EntityReviewTab />);
    await waitFor(() => expect(mockAuthFetch).toHaveBeenCalled());

    mockAuthFetch.mockReset();
    mockAuthFetch.mockResolvedValue(makeEntityListResponse([]));

    fireEvent.click(screen.getByRole("button", { name: "unreviewed" }));

    await waitFor(() => expect(mockAuthFetch).toHaveBeenCalled());
    const callUrl = String(mockAuthFetch.mock.calls[0][0]);
    expect(callUrl).toContain("reviewStatus=unreviewed");
  });

  it("Test 14: renders entity fixture with all four columns correct", async () => {
    mockAuthFetch.mockResolvedValue(makeEntityListResponse([ENTITY_FIXTURE]));
    render(<EntityReviewTab />);

    await waitFor(() => expect(screen.getByText("Acme Corp")).toBeDefined());

    expect(screen.getByText("B-ORG")).toBeDefined();
    expect(screen.getByText("invoice-2026-00417.pdf")).toBeDefined();
    expect(screen.getByText("0.998")).toBeDefined();
    expect(screen.getAllByText("unreviewed")[0]).toBeDefined();
  });

  it("Test 15: confirm button sends PATCH with review_status confirmed, updates optimistically", async () => {
    mockAuthFetch.mockResolvedValue(makeEntityListResponse([ENTITY_FIXTURE]));
    render(<EntityReviewTab />);

    await waitFor(() => expect(screen.getByLabelText("Confirm entity")).toBeDefined());

    mockAuthFetch.mockResolvedValue(
      new Response(JSON.stringify({ ...ENTITY_FIXTURE, review_status: "confirmed" }), { status: 200 })
    );

    fireEvent.click(screen.getByLabelText("Confirm entity"));

    await waitFor(() => expect(screen.getAllByText("confirmed")[0]).toBeDefined());

    const patchCall = mockAuthFetch.mock.calls.find((c) =>
      String(c[0]).includes("/api/v1/entities/ent-001")
    );
    expect(patchCall).toBeDefined();
    const body = JSON.parse(patchCall![1].body);
    expect(body.review_status).toBe("confirmed");
  });

  it("Test 16: reject button sends PATCH with review_status rejected, updates optimistically", async () => {
    mockAuthFetch.mockResolvedValue(makeEntityListResponse([ENTITY_FIXTURE]));
    render(<EntityReviewTab />);

    await waitFor(() => expect(screen.getByLabelText("Reject entity")).toBeDefined());

    mockAuthFetch.mockResolvedValue(
      new Response(JSON.stringify({ ...ENTITY_FIXTURE, review_status: "rejected" }), { status: 200 })
    );

    fireEvent.click(screen.getByLabelText("Reject entity"));

    await waitFor(() => expect(screen.getAllByText("rejected")[0]).toBeDefined());

    const patchCall = mockAuthFetch.mock.calls.find((c) =>
      String(c[0]).includes("/api/v1/entities/ent-001")
    );
    expect(patchCall).toBeDefined();
    const body = JSON.parse(patchCall![1].body);
    expect(body.review_status).toBe("rejected");
  });

  it("Test 17: confidence colors — 0.94 good, 0.75 warn, 0.62 bad, 0.90 good (boundary)", async () => {
    const entities: EntityItem[] = [
      { ...ENTITY_FIXTURE, id: "e1", value: "Alpha", confidence: 0.94 },
      { ...ENTITY_FIXTURE, id: "e2", value: "Beta", confidence: 0.75 },
      { ...ENTITY_FIXTURE, id: "e3", value: "Gamma", confidence: 0.62 },
      { ...ENTITY_FIXTURE, id: "e4", value: "Delta", confidence: 0.90 },
    ];
    mockAuthFetch.mockResolvedValue(makeEntityListResponse(entities));
    render(<EntityReviewTab />);

    await waitFor(() => expect(screen.getByText("0.940")).toBeDefined());

    const conf094 = screen.getByText("0.940");
    expect(conf094.className).toContain("text-success");

    const conf075 = screen.getByText("0.750");
    expect(conf075.className).toContain("text-warning");

    const conf062 = screen.getByText("0.620");
    expect(conf062.className).toContain("text-error");

    const conf090 = screen.getByText("0.900");
    expect(conf090.className).toContain("text-success");
  });

  it("Test 18: empty entity list shows empty state message", async () => {
    mockAuthFetch.mockResolvedValue(makeEntityListResponse([]));
    render(<EntityReviewTab />);

    await waitFor(() => expect(screen.getByText(/no entities found/i)).toBeDefined());
  });
});
