import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CitationCard } from "./CitationCard";

describe("CitationCard", () => {
  it("renders document name as heading", () => {
    render(
      <CitationCard
        citation={{
          document_name: "report.pdf",
          entity_type: "organization",
          entity_value: "Acme Corp",
          confidence: 0.95,
        }}
      />
    );
    expect(screen.getByText("report.pdf")).toBeInTheDocument();
  });

  it("renders entity type, value and confidence", () => {
    render(
      <CitationCard
        citation={{
          document_name: "report.pdf",
          entity_type: "organization",
          entity_value: "Acme Corp",
          confidence: 0.95,
        }}
      />
    );
    expect(screen.getByText("organization:")).toBeInTheDocument();
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("(95%)")).toBeInTheDocument();
  });

  it("shows expand toggle when context_snippet is present", () => {
    render(
      <CitationCard
        citation={{
          document_name: "report.pdf",
          context_snippet: "Some context text here",
        }}
      />
    );
    expect(screen.getByText("Show context")).toBeInTheDocument();
  });

  it("expands to show context on toggle click", () => {
    render(
      <CitationCard
        citation={{
          document_name: "report.pdf",
          context_snippet: "Expanded context text",
        }}
      />
    );
    fireEvent.click(screen.getByText("Show context"));
    expect(screen.getByText("Hide context")).toBeInTheDocument();
    expect(screen.getByText("Expanded context text")).toBeInTheDocument();
  });

  it("does not show expand toggle without context_snippet", () => {
    render(
      <CitationCard
        citation={{
          document_name: "report.pdf",
          entity_type: "organization",
        }}
      />
    );
    expect(screen.queryByText("Show context")).not.toBeInTheDocument();
    expect(screen.queryByText("Hide context")).not.toBeInTheDocument();
  });

  it("falls back to truncated document_id when no document_name", () => {
    render(
      <CitationCard
        citation={{
          document_id: "doc-abc-123",
          entity_type: "person",
          entity_value: "John Doe",
        }}
      />
    );
    expect(screen.getByText(/doc-abc.../)).toBeInTheDocument();
  });

  it("shows 'Unknown document' when neither document_name nor document_id", () => {
    render(
      <CitationCard
        citation={{
          entity_type: "person",
          entity_value: "Jane Doe",
        }}
      />
    );
    expect(screen.getByText("Unknown document")).toBeInTheDocument();
  });
});
