"use client";

import { useMemo, useState } from "react";
import { Spinner } from "@/components/ui";
import { useDocuments } from "@/hooks/use-documents";
import { useToast } from "@/hooks/use-toast";
import {
  useApproveCandidate,
  useEditCandidate,
  useRejectCandidate,
  useRequestSchemaProposal,
  useSchemaProposal,
} from "@/hooks/use-schema-proposal";
import type { SchemaProposalCandidate } from "@/types/seed-bootstrap";

const DISPOSITION_LABEL: Record<SchemaProposalCandidate["disposition"], string> = {
  pending: "Awaiting review",
  edited: "Edited",
  approved: "Approved",
  rejected: "Rejected",
};

/**
 * One candidate, its evidence, and the three things a reviewer can do with it.
 *
 * The examples are rendered as prominently as the name because they are the reviewer's only
 * evidence that the candidate is real: every one has been checked to appear verbatim in a seed
 * document, so a candidate with convincing examples is a candidate that was found rather than
 * imagined. Hiding them would leave a plausible-sounding name to be approved on trust, which is
 * exactly what the verbatim rule exists to prevent.
 */
function CandidateCard({
  candidate,
  onApprove,
  onReject,
  onEdit,
  busy,
}: {
  candidate: SchemaProposalCandidate;
  onApprove: () => void;
  onReject: () => void;
  onEdit: (changes: { name?: string; description?: string }) => void;
  busy: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(candidate.name);
  const [description, setDescription] = useState(candidate.description ?? "");

  const decided = candidate.disposition === "approved" || candidate.disposition === "rejected";

  return (
    <div
      className="rounded-lg border border-border bg-surface p-4 flex flex-col gap-3"
      style={{ opacity: candidate.disposition === "rejected" ? 0.6 : 1 }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {editing ? (
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded border border-border px-2 py-1 font-body text-sm"
              style={{ background: "var(--surface-2)", color: "var(--ink)" }}
              aria-label="Candidate name"
            />
          ) : (
            <h3 className="font-display text-base font-semibold" style={{ color: "var(--ink)" }}>
              {candidate.name}
            </h3>
          )}
        </div>
        <span
          className="shrink-0 rounded-full px-2 py-0.5 font-body text-xs"
          style={{ background: "var(--surface-3)", color: "var(--ink-2)" }}
        >
          {DISPOSITION_LABEL[candidate.disposition]}
        </span>
      </div>

      {editing ? (
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
          className="w-full rounded border border-border px-2 py-1 font-body text-sm"
          style={{ background: "var(--surface-2)", color: "var(--ink)" }}
          aria-label="Candidate description"
        />
      ) : (
        <p className="font-body text-sm" style={{ color: "var(--ink-2)" }}>
          {candidate.description ?? "No description"}
        </p>
      )}

      <div>
        <div className="font-body text-xs mb-1" style={{ color: "var(--ink-3)" }}>
          Found in your documents
        </div>
        <div className="flex flex-wrap gap-1.5">
          {candidate.examples.map((example) => (
            <span
              key={example}
              className="rounded px-2 py-0.5 font-mono text-xs"
              style={{ background: "var(--surface-3)", color: "var(--ink-2)" }}
            >
              {example}
            </span>
          ))}
        </div>
      </div>

      {candidate.created_entity_type && (
        <div className="font-body text-xs" style={{ color: "var(--good)" }}>
          Created entity type “{candidate.created_entity_type}”
        </div>
      )}

      {!decided && (
        <div className="flex gap-2 mt-auto pt-1">
          {editing ? (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={() => {
                  onEdit({ name, description });
                  setEditing(false);
                }}
                className="rounded bg-brand-primary px-3 py-1.5 font-body text-xs font-medium text-white disabled:opacity-50"
              >
                Save
              </button>
              <button
                type="button"
                onClick={() => {
                  setName(candidate.name);
                  setDescription(candidate.description ?? "");
                  setEditing(false);
                }}
                className="rounded border border-border px-3 py-1.5 font-body text-xs"
                style={{ color: "var(--ink-2)" }}
              >
                Cancel
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={onApprove}
                className="rounded bg-brand-primary px-3 py-1.5 font-body text-xs font-medium text-white disabled:opacity-50"
              >
                Approve
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => setEditing(true)}
                className="rounded border border-border px-3 py-1.5 font-body text-xs disabled:opacity-50"
                style={{ color: "var(--ink-2)" }}
              >
                Edit
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={onReject}
                className="rounded border border-border px-3 py-1.5 font-body text-xs disabled:opacity-50"
                style={{ color: "var(--ink-3)" }}
              >
                Reject
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export function SchemaProposalPage() {
  const { toast } = useToast();
  const { data: documentsData, isLoading: documentsLoading } = useDocuments(1, 100, "processed");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [qaPairId, setQaPairId] = useState<string>("");
  const [proposalId, setProposalId] = useState<string | null>(null);

  const requestProposal = useRequestSchemaProposal();
  const { data: proposal, isLoading: proposalLoading } = useSchemaProposal(proposalId);
  const approve = useApproveCandidate();
  const reject = useRejectCandidate();
  const edit = useEditCandidate();

  const documents = useMemo(
    () => (documentsData?.documents ?? []).filter((doc) => doc.purpose !== "query" && doc.purpose !== "qa_pair"),
    [documentsData],
  );

  const qaPairDocuments = useMemo(
    () => (documentsData?.documents ?? []).filter((doc) => doc.purpose === "qa_pair"),
    [documentsData],
  );

  const busy = approve.isPending || reject.isPending || edit.isPending;
  const running = proposal?.status === "queued" || proposal?.status === "running";

  function toggle(docId: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(docId)) next.delete(docId);
      else next.add(docId);
      return next;
    });
  }

  function handleRequest() {
    requestProposal.mutate(
      { documentIds: [...selected], qaPairDocumentId: qaPairId || null },
      {
        onSuccess: (data) => setProposalId(data.proposal_id),
        onError: (err) => toast(err.message, "bad"),
      },
    );
  }

  function handleApprove(candidate: SchemaProposalCandidate) {
    approve.mutate(candidate.id, {
      onSuccess: () => toast(`${candidate.name} created`),
      // A duplicate name arrives here as an ordinary error. Surfacing the server's message
      // rather than a generic one is what tells the reviewer the type already exists, which is
      // an outcome they can act on, instead of that something went wrong.
      onError: (err) => toast(err.message, "bad"),
    });
  }

  function handleReject(candidate: SchemaProposalCandidate) {
    reject.mutate(candidate.id, {
      onSuccess: () => toast(`${candidate.name} rejected`),
      onError: (err) => toast(err.message, "bad"),
    });
  }

  function handleEdit(
    candidate: SchemaProposalCandidate,
    changes: { name?: string; description?: string },
  ) {
    edit.mutate(
      { candidateId: candidate.id, ...changes },
      {
        onSuccess: () => toast("Candidate updated"),
        onError: (err) => toast(err.message, "bad"),
      },
    );
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="font-display text-2xl font-semibold" style={{ color: "var(--ink)" }}>
          Suggest Entity Types
        </h1>
        <p className="font-body text-sm mt-1" style={{ color: "var(--ink-2)" }}>
          Pick a handful of representative documents. Every suggestion comes back with values
          quoted from those documents, and nothing is created until you approve it.
        </p>
      </div>

      {!proposalId && (
        <section className="flex flex-col gap-3">
          <h2 className="font-display text-base font-semibold" style={{ color: "var(--ink)" }}>
            Seed documents
          </h2>
          {documentsLoading ? (
            <Spinner size="sm" />
          ) : documents.length === 0 ? (
            <p className="font-body text-sm" style={{ color: "var(--ink-3)" }}>
              No processed training documents yet. Upload some first.
            </p>
          ) : (
            <div className="flex flex-col gap-1 max-h-80 overflow-y-auto rounded-lg border border-border p-2">
              {documents.map((doc) => (
                <label
                  key={doc.id}
                  className="flex items-center gap-2 rounded px-2 py-1.5 font-body text-sm cursor-pointer"
                  style={{ color: "var(--ink-2)" }}
                >
                  <input
                    type="checkbox"
                    checked={selected.has(doc.id)}
                    onChange={() => toggle(doc.id)}
                  />
                  <span className="truncate">{doc.filename}</span>
                </label>
              ))}
            </div>
          )}
          <div className="flex flex-col gap-1">
            <label className="font-body text-xs" style={{ color: "var(--ink-3)" }}>
              Q&amp;A pair (optional) — guides which entity types are proposed
            </label>
            <select
              aria-label="Q&A pair document"
              value={qaPairId}
              onChange={(e) => setQaPairId(e.target.value)}
              className="rounded-lg border border-border px-2 py-1.5 font-body text-sm"
              style={{ color: "var(--ink-2)", background: "var(--surface-1)" }}
            >
              <option value="">None</option>
              {qaPairDocuments.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.filename}
                </option>
              ))}
            </select>
            {qaPairDocuments.length === 0 && (
              <span className="font-body text-xs" style={{ color: "var(--ink-3)" }}>
                Upload a PDF/DOC/DOCX/TXT with purpose &ldquo;Q&amp;A pair&rdquo; from Uploaded Documents to use one.
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              disabled={selected.size === 0 || requestProposal.isPending}
              onClick={handleRequest}
              className="rounded-lg bg-brand-primary px-4 py-2 font-body text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              {requestProposal.isPending ? "Requesting…" : "Suggest entity types"}
            </button>
            <span className="font-body text-sm" style={{ color: "var(--ink-3)" }}>
              {selected.size} selected
            </span>
          </div>
        </section>
      )}

      {proposalId && (
        <section className="flex flex-col gap-3">
          {(proposalLoading || running) && (
            <div className="flex items-center gap-2 font-body text-sm" style={{ color: "var(--ink-2)" }}>
              <Spinner size="sm" /> Reading your documents…
            </div>
          )}

          {proposal?.status === "failed" && (
            <div
              className="rounded-lg p-3 font-body text-sm"
              style={{ background: "var(--bad-soft)", border: "1px solid var(--bad)", color: "var(--bad)" }}
            >
              {proposal.error_message ?? "Proposal failed"}
            </div>
          )}

          {proposal?.status === "completed" && proposal.candidates.length === 0 && (
            <p className="font-body text-sm" style={{ color: "var(--ink-3)" }}>
              No candidates survived verification against your documents. Try a larger or more
              representative seed set.
            </p>
          )}

          {proposal && proposal.candidates.length > 0 && (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {proposal.candidates.map((candidate) => (
                <CandidateCard
                  key={candidate.id}
                  candidate={candidate}
                  busy={busy}
                  onApprove={() => handleApprove(candidate)}
                  onReject={() => handleReject(candidate)}
                  onEdit={(changes) => handleEdit(candidate, changes)}
                />
              ))}
            </div>
          )}

          <button
            type="button"
            onClick={() => {
              setProposalId(null);
              setSelected(new Set());
            }}
            className="self-start rounded border border-border px-3 py-1.5 font-body text-xs"
            style={{ color: "var(--ink-2)" }}
          >
            Start another proposal
          </button>
        </section>
      )}
    </div>
  );
}
