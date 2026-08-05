import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { BatchDocumentSelectModal } from "./BatchDocumentSelectModal";
import type { EligibleDocument } from "@/types/extraction";

const mockUseEligibleDocuments = vi.fn();
vi.mock("@/hooks/use-eligible-documents", () => ({
  useEligibleDocuments: (...args: unknown[]) => mockUseEligibleDocuments(...args),
}));

const FRESH_DOC: EligibleDocument = { id: "doc-fresh", filename: "fresh.pdf", already_extracted: false };
const EXTRACTED_DOC: EligibleDocument = { id: "doc-old", filename: "old.pdf", already_extracted: true };

describe("BatchDocumentSelectModal", () => {
  beforeEach(() => {
    mockUseEligibleDocuments.mockReturnValue({
      documents: [FRESH_DOC, EXTRACTED_DOC],
      isLoading: false,
    });
  });

  it("fetches eligible documents when opened", () => {
    render(<BatchDocumentSelectModal onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(mockUseEligibleDocuments).toHaveBeenCalledWith(true);
  });

  it("disables the checkbox for already-extracted documents and labels them", () => {
    render(<BatchDocumentSelectModal onConfirm={vi.fn()} onCancel={vi.fn()} />);

    const disabledCheckbox = screen.getByLabelText(/old\.pdf/) as HTMLInputElement;
    expect(disabledCheckbox.disabled).toBe(true);
    expect(screen.getByText(/already processed/i)).toBeDefined();
  });

  it("cannot select an already-extracted document even by clicking it", () => {
    render(<BatchDocumentSelectModal onConfirm={vi.fn()} onCancel={vi.fn()} />);

    const disabledCheckbox = screen.getByLabelText(/old\.pdf/) as HTMLInputElement;
    fireEvent.click(disabledCheckbox);
    expect(disabledCheckbox.checked).toBe(false);
  });

  it("disables confirm when nothing is selected", () => {
    render(<BatchDocumentSelectModal onConfirm={vi.fn()} onCancel={vi.fn()} />);

    const confirmButton = screen.getByRole("button", { name: /run extraction/i });
    expect(confirmButton).toHaveProperty("disabled", true);
  });

  it("enables confirm and submits only checked, not-yet-extracted ids", () => {
    const onConfirm = vi.fn();
    render(<BatchDocumentSelectModal onConfirm={onConfirm} onCancel={vi.fn()} />);

    fireEvent.click(screen.getByLabelText("fresh.pdf"));
    const confirmButton = screen.getByRole("button", { name: /run extraction/i });
    expect(confirmButton).toHaveProperty("disabled", false);

    fireEvent.click(confirmButton);
    expect(onConfirm).toHaveBeenCalledWith(["doc-fresh"]);
  });

  it("cancel closes without calling onConfirm", () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(<BatchDocumentSelectModal onConfirm={onConfirm} onCancel={onCancel} />);

    fireEvent.click(screen.getByLabelText("fresh.pdf"));
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

    expect(onCancel).toHaveBeenCalled();
    expect(onConfirm).not.toHaveBeenCalled();
  });
});
