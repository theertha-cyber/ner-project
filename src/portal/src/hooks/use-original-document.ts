"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { authFetch } from "@/lib/auth-fetch";

/**
 * Fetches a document's original bytes and holds them as an object URL.
 *
 * Deliberately not React Query, unlike every other fetch in this portal. An object URL is
 * a resource with a lifetime, not a cached value: caching one means either revoking on
 * unmount — leaving the cache holding a dangling string that renders as a broken frame on
 * the next mount — or never revoking and leaking the buffer for the session. The probe
 * result is cacheable; the bytes are not.
 *
 * The portal cannot put an Authorization header on an `<iframe src>`, so the bytes have to
 * be fetched by JavaScript and rendered from memory. That is also why the media type used
 * to build the Blob comes from the probe rather than from the response or the filename:
 * an object URL inherits this origin, where the access token lives, so the type the
 * document is rendered as must be the one the server decided.
 */

export type RenderMode = "pdf" | "image" | "convert" | "download";

export interface DocumentAvailability {
  document_id: string;
  filename: string | null;
  media_type: string;
  render_mode: RenderMode;
  file_size: number | null;
  retention_mode: string;
  available: boolean;
  reason: string | null;
  message: string | null;
}

export type DocumentState =
  | { status: "idle" }
  | { status: "loading"; filename: string | null }
  | {
      status: "ready";
      url: string;
      mediaType: string;
      renderMode: RenderMode;
      filename: string | null;
    }
  | { status: "unavailable"; code: string; message: string; filename: string | null };

// Reasons the server reports that are permanent: the document will not become viewable
// by trying again. Offering a retry for these would be a lie.
const PERMANENT_REASONS = new Set([
  "ORIGINAL_RELEASED",
  "ORIGINAL_MISSING",
  "DOCUMENT_NOT_FOUND",
  "DOCUMENT_NOT_PERMITTED",
  "SOURCE_NOT_REOPENABLE",
]);

export function isRetryable(code: string | null | undefined): boolean {
  return !!code && !PERMANENT_REASONS.has(code);
}

const GENERIC_FAILURE = {
  code: "CONTENT_UNAVAILABLE",
  message: "This document could not be opened.",
};

async function readFailure(response: Response) {
  try {
    const body = await response.json();
    const detail = body?.detail ?? body;
    if (detail?.code) {
      return { code: detail.code as string, message: (detail.message as string) ?? GENERIC_FAILURE.message };
    }
  } catch {
    // A non-JSON error body is itself a finite outcome; fall through to the generic one.
  }
  return GENERIC_FAILURE;
}

export function useOriginalDocument(documentId: string | null) {
  const [state, setState] = useState<DocumentState>({ status: "idle" });

  // The URL is tracked in a ref as well as in state because revocation must target the
  // generation that created it. A closure over the state value revokes whatever is
  // current when the cleanup runs, which during a rapid reopen is the *new* document.
  const urlRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [attempt, setAttempt] = useState(0);

  const release = useCallback(() => {
    if (urlRef.current) {
      URL.revokeObjectURL(urlRef.current);
      urlRef.current = null;
    }
  }, []);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  useEffect(() => {
    // Any change of document supersedes what is in flight. Abort first, then release, so
    // a response that arrives during teardown cannot install a URL nothing will revoke.
    abortRef.current?.abort();
    release();

    if (!documentId) {
      setState({ status: "idle" });
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;
    let cancelled = false;

    (async () => {
      setState({ status: "loading", filename: null });
      try {
        const probeResponse = await authFetch(
          `/api/v1/documents/${documentId}/content/status`,
          { signal: controller.signal },
        );
        if (!probeResponse.ok) {
          const failure = await readFailure(probeResponse);
          if (!cancelled) {
            setState({ status: "unavailable", ...failure, filename: null });
          }
          return;
        }

        const probe: DocumentAvailability = await probeResponse.json();
        if (cancelled) return;
        setState({ status: "loading", filename: probe.filename });

        if (!probe.available) {
          setState({
            status: "unavailable",
            code: probe.reason ?? GENERIC_FAILURE.code,
            message: probe.message ?? GENERIC_FAILURE.message,
            filename: probe.filename,
          });
          return;
        }

        const bytesResponse = await authFetch(`/api/v1/documents/${documentId}/content`, {
          signal: controller.signal,
        });
        if (!bytesResponse.ok) {
          const failure = await readFailure(bytesResponse);
          if (!cancelled) {
            setState({ status: "unavailable", ...failure, filename: probe.filename });
          }
          return;
        }

        const raw = await bytesResponse.blob();
        if (cancelled) return;

        // Re-typed from the probe rather than trusting the Blob's own type: the server is
        // the authority on what this document may be rendered as.
        const typed = new Blob([raw], { type: probe.media_type });
        const url = URL.createObjectURL(typed);
        urlRef.current = url;
        setState({
          status: "ready",
          url,
          mediaType: probe.media_type,
          renderMode: probe.render_mode,
          filename: probe.filename,
        });
      } catch (error) {
        // An abort is the rapid-reopen path, not a failure worth showing.
        if ((error as Error)?.name === "AbortError" || cancelled) return;
        setState({ status: "unavailable", ...GENERIC_FAILURE, filename: null });
      }
    })();

    return () => {
      cancelled = true;
      controller.abort();
      release();
    };
  }, [documentId, attempt, release]);

  return { state, retry };
}
