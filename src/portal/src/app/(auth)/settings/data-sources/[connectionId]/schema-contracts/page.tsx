"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { RequireAuth } from "@/components/require-auth";
import { ContractHistoryTable, ContractUpload } from "@/components/data-sources/contracts";
import { SafeOutcomeNotice, SafeStatusBadge } from "@/components/data-sources/status";
import {
  SafeApiHttpError,
  publishContract,
  uploadContract,
  useDataSource,
  useSchemaContracts,
} from "@/hooks/use-data-sources";
import { PROVIDER_LABELS, type ContractDraft } from "@/lib/data-sources";

export default function SchemaContractsPage() {
  return (
    <RequireAuth roles={["tenant_admin"]}>
      <ContractsContent />
    </RequireAuth>
  );
}

function ContractsContent() {
  const params = useParams<{ connectionId: string }>();
  const connectionId = params.connectionId;
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const page = Math.max(1, Number(searchParams.get("page") ?? "1") || 1);
  const [draft, setDraft] = useState<ContractDraft | null>(null);
  const [uploadPending, setUploadPending] = useState(false);
  const [uploadError, setUploadError] = useState<SafeApiHttpError | null>(null);
  const [publishingVersion, setPublishingVersion] = useState<number | null>(null);
  const [publishError, setPublishError] = useState<SafeApiHttpError | null>(null);

  const detail = useDataSource(connectionId);
  const history = useSchemaContracts(detail.data?.provider === "azure_postgresql" ? connectionId : null, page);

  async function handleUpload(document: unknown) {
    setUploadPending(true);
    setUploadError(null);
    setDraft(null);
    try {
      const stored = await uploadContract(connectionId, document);
      setDraft(stored);
      history.refetch();
    } catch (e) {
      setUploadError(e as SafeApiHttpError);
    } finally {
      setUploadPending(false);
    }
  }

  async function handlePublish(version: number) {
    setPublishingVersion(version);
    setPublishError(null);
    try {
      await publishContract(connectionId, version);
      history.refetch();
    } catch (e) {
      setPublishError(e as SafeApiHttpError);
    } finally {
      setPublishingVersion(null);
    }
  }

  function handlePage(next: number) {
    const params = new URLSearchParams(searchParams.toString());
    if (next <= 1) params.delete("page");
    else params.set("page", String(next));
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname);
  }

  const connection = detail.data;
  const wrongProvider = connection && connection.provider !== "azure_postgresql";
  const driftBlocked = publishError?.code === "PUBLISH_PRECONDITION_FAILED";

  return (
    <div className="animate-fade-up mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 py-8">
      <Link href={`/settings/data-sources/${connectionId}`} className="w-fit rounded-sm text-sm font-medium underline outline-none focus-visible:ring-2" style={{ color: "var(--primary)" }}>
        Back to connection
      </Link>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-[-0.01em]" style={{ color: "var(--ink)" }}>
          Schema contracts
        </h1>
        {connection && <SafeStatusBadge status={connection.status} />}
      </div>
      <p className="max-w-[65ch] text-sm leading-6" style={{ color: "var(--ink-2)" }}>
        {connection ? `${PROVIDER_LABELS[connection.provider]} · ` : ""}Upload, validate, and publish the versioned
        JSON contract that governs direct chat. Only version metadata and safe validation state appear here —
        never database rows or SQL text.
      </p>

      {detail.isError && (
        <SafeOutcomeNotice
          variant="error"
          title="Connection unavailable"
          code={(detail.error as SafeApiHttpError)?.code ?? "INTERNAL_ERROR"}
          requestId={(detail.error as SafeApiHttpError)?.requestId}
        />
      )}

      {wrongProvider && (
        <SafeOutcomeNotice variant="blocked" title="Not a PostgreSQL connection" code="INVALID_REQUEST">
          Schema contracts govern Azure Database for PostgreSQL connections only.
        </SafeOutcomeNotice>
      )}

      {!wrongProvider && connection && (
        <>
          <ContractUpload pending={uploadPending} error={uploadError} result={draft} onUpload={(doc) => void handleUpload(doc)} />
          {history.isError ? (
            <SafeOutcomeNotice
              variant="error"
              title="Contract history unavailable"
              code={(history.error as SafeApiHttpError)?.code ?? "INTERNAL_ERROR"}
              requestId={(history.error as SafeApiHttpError)?.requestId}
            >
              <button type="button" onClick={() => history.refetch()} className="mt-2 rounded-md border px-3 py-1.5 text-sm font-medium outline-none focus-visible:ring-2" style={{ borderColor: "var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}>
                Retry
              </button>
            </SafeOutcomeNotice>
          ) : (
            <ContractHistoryTable
              history={history.data}
              connectionActive={connection.status === "active"}
              publishingVersion={publishingVersion}
              publishError={driftBlocked ? null : publishError}
              onPage={handlePage}
              onPublish={(v) => void handlePublish(v)}
            />
          )}
          {driftBlocked && publishError && (
            <SafeOutcomeNotice variant="blocked" title="Drift blocks publishing" code={publishError.code} requestId={publishError.requestId}>
              The live database no longer matches the validated contract. Review the connection detail, upload a
              replacement contract, and publish again.{" "}
              <Link href={`/settings/data-sources/${connectionId}`} className="underline">
                Open connection detail
              </Link>
            </SafeOutcomeNotice>
          )}
        </>
      )}
    </div>
  );
}
