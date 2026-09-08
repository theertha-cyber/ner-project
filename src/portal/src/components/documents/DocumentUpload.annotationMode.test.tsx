import { describe, it, expect, vi, beforeEach } from "vitest";
import { useState, useCallback } from "react";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DocumentUpload } from "./DocumentUpload";
import type { EntityType } from "@/types/entity-types";

/**
 * Covers verification.md § Spec Alignment rows 1-16.
 *
 * The upload hook is mocked (as in `DocumentUpload.test.tsx`) so a batch can be driven
 * deterministically, but the component under test is the real one — Scenario 6's "zero
 * pre-label requests in Manual" claim is worthless against a stub.
 */

let uploadCalls: string[] = [];
let uploadFailures: Record<string, string> = {};
let prelabelCalls: string[] = [];
let prelabelFailures: Record<string, string> = {};
/** Every upload and trigger call in issue order, so interleaving is detectable. */
let callLog: string[] = [];
let prelabelGate: (() => void) | null = null;

function useUploadMock() {
  const [progress, setProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);

  const upload = useCallback(async (file: File) => {
    uploadCalls.push(file.name);
    callLog.push(`upload:${file.name}`);
    setIsUploading(true);
    setProgress(0);
    await Promise.resolve();
    setIsUploading(false);
    setProgress(100);
    if (uploadFailures[file.name]) {
      throw new Error(uploadFailures[file.name]);
    }
    return { id: `doc-${file.name}` };
  }, []);

  const reset = useCallback(() => {
    setProgress(0);
    setIsUploading(false);
  }, []);

  return { upload, progress, isUploading, error: null, reset, cancel: vi.fn() };
}

vi.mock("@/hooks/use-upload", () => ({
  useUpload: () => useUploadMock(),
}));

vi.mock("@/hooks/use-prelabel-trigger", () => ({
  usePrelabelTrigger: () => ({
    trigger: async (docId: string) => {
      prelabelCalls.push(docId);
      callLog.push(`prelabel:${docId}`);
      if (prelabelGate) {
        await new Promise<void>((resolve) => {
          prelabelGate = resolve;
        });
      }
      await Promise.resolve();
      if (prelabelFailures[docId]) {
        throw new Error(prelabelFailures[docId]);
      }
    },
  }),
}));

let entityTypes: EntityType[] = [];

vi.mock("@/hooks/use-entity-types", () => ({
  useEntityTypes: () => ({ data: { entity_types: entityTypes } }),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(() => ({
    getAccessToken: vi.fn(() => "mock-token"),
    user: { tenantSlug: "acme-corp" },
  })),
}));

function entityType(name: string, overrides: Partial<EntityType> = {}): EntityType {
  return {
    id: `et-${name}`,
    name,
    description: "",
    examples: [],
    base_label_mapping: {},
    target_table: null,
    required_flag: false,
    is_active: true,
    version: 1,
    cardinality: "multi",
    value_kind: "text",
    sql_identifier: `e_${name}`,
    ...overrides,
  };
}

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

function createFile(name: string, type = "application/pdf", size = 100): File {
  const blob = new Blob([new ArrayBuffer(size)], { type });
  return new File([blob], name, { type });
}

function modeRadio(name: "Manual" | "Automated"): HTMLInputElement {
  return screen.getByLabelText(name) as HTMLInputElement;
}

function dropFiles(files: File[]) {
  const zone = screen.getByText(/Click to upload/).closest("div")!;
  fireEvent.drop(zone, { dataTransfer: { files } });
}

function renderUpload(purpose: "training" | "query" = "training") {
  return render(<DocumentUpload purpose={purpose} />, { wrapper: createWrapper() });
}

describe("DocumentUpload — annotation mode", () => {
  beforeEach(() => {
    uploadCalls = [];
    uploadFailures = {};
    prelabelCalls = [];
    prelabelFailures = {};
    callLog = [];
    prelabelGate = null;
    entityTypes = [entityType("vendor_name"), entityType("invoice_total")];
  });

  // Row 1
  it("shows_selector_for_training_purpose", () => {
    renderUpload("training");
    expect(modeRadio("Manual")).toBeDefined();
    expect(modeRadio("Automated")).toBeDefined();
    expect(modeRadio("Manual").checked).toBe(true);
    expect(modeRadio("Automated").checked).toBe(false);
  });

  // Row 2
  it("hides_selector_for_query_purpose", () => {
    renderUpload("query");
    expect(screen.queryByLabelText("Manual")).toBeNull();
    expect(screen.queryByLabelText("Automated")).toBeNull();
    expect(screen.queryByText(/Annotation mode/i)).toBeNull();
  });

  // Row 3
  it("resets_to_manual_after_batch", async () => {
    renderUpload("training");
    fireEvent.click(modeRadio("Automated"));
    expect(modeRadio("Automated").checked).toBe(true);

    dropFiles([createFile("a.pdf")]);

    await waitFor(() => expect(screen.getByText(/uploaded successfully|Upload successful/)).toBeDefined());
    await waitFor(() => expect(modeRadio("Manual").checked).toBe(true));
    expect(modeRadio("Automated").checked).toBe(false);
  });

  // Row 4
  it("disables_automated_without_entity_types", () => {
    entityTypes = [];
    renderUpload("training");
    expect(modeRadio("Automated").disabled).toBe(true);
    expect(modeRadio("Manual").disabled).toBe(false);
    expect(screen.getByText(/at least one active entity type/i)).toBeDefined();
  });

  // Row 5 — QA pairs are an enhancement, never a precondition (design.md Decision 5).
  it("enables_automated_without_qa_pairs", () => {
    entityTypes = [
      entityType("vendor_name", { qa_examples: [] }),
      entityType("invoice_total", { qa_examples: [] }),
    ];
    renderUpload("training");
    expect(modeRadio("Automated").disabled).toBe(false);
    expect(screen.queryByText(/at least one active entity type/i)).toBeNull();
  });

  // Row 6
  it("manual_issues_no_prelabel_requests", async () => {
    renderUpload("training");
    dropFiles([createFile("a.pdf"), createFile("b.pdf"), createFile("c.pdf")]);

    await waitFor(() => expect(uploadCalls).toEqual(["a.pdf", "b.pdf", "c.pdf"]));
    await waitFor(() => expect(screen.getByText(/3 of 3 uploaded successfully/)).toBeDefined());
    expect(prelabelCalls).toEqual([]);
  });

  // Row 7
  it("automated_triggers_one_request_per_document", async () => {
    renderUpload("training");
    fireEvent.click(modeRadio("Automated"));
    dropFiles([createFile("a.pdf"), createFile("b.pdf"), createFile("c.pdf")]);

    await waitFor(() =>
      expect(prelabelCalls).toEqual(["doc-a.pdf", "doc-b.pdf", "doc-c.pdf"]),
    );
    expect(new Set(prelabelCalls).size).toBe(3);
  });

  // Row 8
  it("skips_prelabel_for_failed_uploads", async () => {
    uploadFailures["b.pdf"] = "Upload failed: 500";
    renderUpload("training");
    fireEvent.click(modeRadio("Automated"));
    dropFiles([createFile("a.pdf"), createFile("b.pdf"), createFile("c.pdf")]);

    await waitFor(() => expect(prelabelCalls).toEqual(["doc-a.pdf", "doc-c.pdf"]));
  });

  // Row 9
  it("skips_prelabel_for_rejected_files", async () => {
    renderUpload("training");
    fireEvent.click(modeRadio("Automated"));
    dropFiles([
      createFile("a.pdf"),
      createFile("b.pdf"),
      createFile("bad.exe", "application/x-msdownload"),
    ]);

    await waitFor(() => expect(prelabelCalls).toEqual(["doc-a.pdf", "doc-b.pdf"]));
    expect(uploadCalls).toEqual(["a.pdf", "b.pdf"]);
  });

  // Row 10 — the trigger phase is a separate pass, not interleaved (design.md Decision 4).
  it("triggers_run_after_all_uploads", async () => {
    renderUpload("training");
    fireEvent.click(modeRadio("Automated"));
    dropFiles([createFile("a.pdf"), createFile("b.pdf")]);

    await waitFor(() => expect(prelabelCalls.length).toBe(2));
    expect(callLog).toEqual([
      "upload:a.pdf",
      "upload:b.pdf",
      "prelabel:doc-a.pdf",
      "prelabel:doc-b.pdf",
    ]);
  });

  // Row 11
  it("trigger_failure_does_not_halt_batch", async () => {
    prelabelFailures["doc-b.pdf"] = "Pre-labeling request failed: 500";
    renderUpload("training");
    fireEvent.click(modeRadio("Automated"));
    dropFiles([createFile("a.pdf"), createFile("b.pdf"), createFile("c.pdf")]);

    await waitFor(() =>
      expect(prelabelCalls).toEqual(["doc-a.pdf", "doc-b.pdf", "doc-c.pdf"]),
    );
    await waitFor(() => expect(screen.getByText(/3 of 3 uploaded successfully/)).toBeDefined());
  });

  // Row 12
  it("trigger_failure_not_reported_as_upload_failure", async () => {
    prelabelFailures["doc-b.pdf"] = "Pre-labeling request failed: 500";
    renderUpload("training");
    fireEvent.click(modeRadio("Automated"));
    dropFiles([createFile("a.pdf"), createFile("b.pdf"), createFile("c.pdf")]);

    await waitFor(() => expect(screen.getByText(/3 of 3 uploaded successfully/)).toBeDefined());
    // The document appears in the pre-label failure list, never in the upload failure list.
    const uploadFailureList = screen.queryAllByRole("alert");
    for (const node of uploadFailureList) {
      expect(within(node).queryByText(/b\.pdf: Pre-labeling request failed/)).toBeNull();
    }
    expect(screen.getByText(/b\.pdf: Pre-labeling request failed: 500/)).toBeDefined();
  });

  // Row 13
  it("reports_queued_count_on_success", async () => {
    renderUpload("training");
    fireEvent.click(modeRadio("Automated"));
    dropFiles([createFile("a.pdf"), createFile("b.pdf"), createFile("c.pdf")]);

    await waitFor(() => expect(screen.getByText(/3 of 3 uploaded successfully/)).toBeDefined());
    expect(screen.getByText("3 queued for pre-labeling")).toBeDefined();
  });

  // Row 14
  it("reports_partial_trigger_failure", async () => {
    prelabelFailures["doc-b.pdf"] = "Pre-labeling request failed: 500";
    renderUpload("training");
    fireEvent.click(modeRadio("Automated"));
    dropFiles([createFile("a.pdf"), createFile("b.pdf"), createFile("c.pdf")]);

    await waitFor(() => expect(screen.getByText(/3 of 3 uploaded successfully/)).toBeDefined());
    expect(screen.getByText("2 queued for pre-labeling")).toBeDefined();
    expect(screen.getByText("1 failed to queue for pre-labeling")).toBeDefined();
    expect(screen.getByText(/b\.pdf: Pre-labeling request failed: 500/)).toBeDefined();
  });

  // Row 15
  it("shows_trigger_phase_progress", async () => {
    prelabelGate = () => {};
    renderUpload("training");
    fireEvent.click(modeRadio("Automated"));
    dropFiles([
      createFile("a.pdf"),
      createFile("b.pdf"),
      createFile("c.pdf"),
      createFile("d.pdf"),
      createFile("e.pdf"),
    ]);

    // Held inside the first trigger call: the phase indicator names the trigger phase and its
    // position, and is not the "% uploaded" bar.
    const indicator = await screen.findByText(/Queueing 1 of 5 for pre-labeling/);
    expect(indicator).toBeDefined();
    expect(screen.queryByText(/% uploaded/)).toBeNull();

    const release = prelabelGate as unknown as () => void;
    prelabelGate = null;
    release?.();
  });

  // Row 16
  it("manual_summary_omits_prelabeling", async () => {
    renderUpload("training");
    dropFiles([createFile("a.pdf"), createFile("b.pdf"), createFile("c.pdf")]);

    await waitFor(() => expect(screen.getByText(/3 of 3 uploaded successfully/)).toBeDefined());
    expect(screen.queryByText(/pre-labeling/i)).toBeNull();
    expect(screen.queryByText(/queued/i)).toBeNull();
  });
});
