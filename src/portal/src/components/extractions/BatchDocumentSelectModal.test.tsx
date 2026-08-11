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

const MIXED_DOCS: EligibleDocument[] = [
  { id: "doc-a", filename: "Resume A.pdf", already_extracted: false },
  { id: "doc-b", filename: "Resume B.pdf", already_extracted: false },
  { id: "doc-c", filename: "Resume C.pdf", already_extracted: false },
  { id: "doc-d", filename: "Resume D.pdf", already_extracted: true },
  { id: "doc-e", filename: "Resume E.pdf", already_extracted: true },
];

function checkbox(label: string | RegExp): HTMLInputElement {
  return screen.getByLabelText(label) as HTMLInputElement;
}

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
    expect(screen.getByText(/^processed$/i)).toBeDefined();
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

  describe("bulk selection", () => {
    beforeEach(() => {
      mockUseEligibleDocuments.mockReturnValue({ documents: MIXED_DOCS, isLoading: false });
    });

    it("makes not-yet-extracted documents selectable and counts them", () => {
      render(<BatchDocumentSelectModal onConfirm={vi.fn()} onCancel={vi.fn()} />);

      const first = checkbox("Resume A.pdf");
      expect(first.disabled).toBe(false);
      fireEvent.click(first);

      expect(first.checked).toBe(true);
      expect(screen.getByText("1 document selected")).toBeDefined();
    });

    it("keeps already-extracted documents visible but disabled", () => {
      render(<BatchDocumentSelectModal onConfirm={vi.fn()} onCancel={vi.fn()} />);

      expect(screen.getByText("Resume D.pdf")).toBeDefined();
      expect(screen.getByText("Resume E.pdf")).toBeDefined();
      expect(checkbox(/Resume D.pdf/).disabled).toBe(true);
      expect(checkbox(/Resume E.pdf/).disabled).toBe(true);
    });

    it("select all selects every eligible document and excludes already-extracted ones", () => {
      render(<BatchDocumentSelectModal onConfirm={vi.fn()} onCancel={vi.fn()} />);

      fireEvent.click(checkbox("Select all"));

      expect(checkbox("Resume A.pdf").checked).toBe(true);
      expect(checkbox("Resume B.pdf").checked).toBe(true);
      expect(checkbox("Resume C.pdf").checked).toBe(true);
      expect(checkbox(/Resume D.pdf/).checked).toBe(false);
      expect(checkbox(/Resume E.pdf/).checked).toBe(false);
      expect(screen.getByText("3 documents selected")).toBeDefined();
    });

    it("clearing select all deselects eligible documents without affecting disabled ones", () => {
      render(<BatchDocumentSelectModal onConfirm={vi.fn()} onCancel={vi.fn()} />);

      fireEvent.click(checkbox("Select all"));
      fireEvent.click(checkbox("Select all"));

      expect(checkbox("Resume A.pdf").checked).toBe(false);
      expect(checkbox("Resume B.pdf").checked).toBe(false);
      expect(checkbox("Resume C.pdf").checked).toBe(false);
      expect(checkbox(/Resume D.pdf/).checked).toBe(false);
      expect(checkbox(/Resume D.pdf/).disabled).toBe(true);
      expect(screen.getByText("0 documents selected")).toBeDefined();
      expect(screen.getByRole("button", { name: /run extraction/i })).toHaveProperty("disabled", true);
    });

    it("reflects the current selection state in the select-all checkbox", () => {
      render(<BatchDocumentSelectModal onConfirm={vi.fn()} onCancel={vi.fn()} />);

      expect(checkbox("Select all").checked).toBe(false);

      fireEvent.click(checkbox("Resume A.pdf"));
      fireEvent.click(checkbox("Resume B.pdf"));
      fireEvent.click(checkbox("Resume C.pdf"));
      expect(checkbox("Select all").checked).toBe(true);

      fireEvent.click(checkbox("Resume B.pdf"));
      expect(checkbox("Select all").checked).toBe(false);
    });

    it("run extraction submits only eligible selected documents", () => {
      const onConfirm = vi.fn();
      render(<BatchDocumentSelectModal onConfirm={onConfirm} onCancel={vi.fn()} />);

      fireEvent.click(checkbox("Select all"));
      fireEvent.click(screen.getByRole("button", { name: /run extraction/i }));

      expect(onConfirm).toHaveBeenCalledWith(["doc-a", "doc-b", "doc-c"]);
    });

    it("disables select all when there are no eligible documents", () => {
      mockUseEligibleDocuments.mockReturnValue({
        documents: MIXED_DOCS.filter((d) => d.already_extracted),
        isLoading: false,
      });
      render(<BatchDocumentSelectModal onConfirm={vi.fn()} onCancel={vi.fn()} />);

      const selectAll = checkbox("Select all");
      expect(selectAll.disabled).toBe(true);
      expect(selectAll.checked).toBe(false);

      fireEvent.click(selectAll);
      expect(checkbox(/Resume D.pdf/).checked).toBe(false);
      expect(screen.getByRole("button", { name: /run extraction/i })).toHaveProperty("disabled", true);
    });
  });
});
