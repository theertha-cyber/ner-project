"use client";

import { useState, useCallback } from "react";
import {
  ImportedDocumentsList,
  ImportedDocumentReview,
} from "@/components/imported-documents/ImportedDocuments";

export default function ImportedDocumentsPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const handleSelectRow = useCallback((id: string) => {
    setSelectedId(id);
  }, []);

  const handleBack = useCallback(() => {
    setSelectedId(null);
  }, []);

  if (selectedId) {
    return <ImportedDocumentReview annotationId={selectedId} onBack={handleBack} />;
  }

  return <ImportedDocumentsList onSelectRow={handleSelectRow} />;
}
