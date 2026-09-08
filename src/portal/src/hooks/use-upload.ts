"use client";

import { useState, useCallback, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { DOCUMENT_URL } from "@/lib/api";

export interface UploadResult {
  id: string;
}

export function useUpload() {
  const [progress, setProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const xhrRef = useRef<XMLHttpRequest | null>(null);
  const queryClient = useQueryClient();
  const { getAccessToken } = useAuth();

  const upload = useCallback(
    async (file: File, purpose: "query" | "training" = "query") => {
      setProgress(0);
      setError(null);
      setIsUploading(true);

      const xhr = new XMLHttpRequest();
      xhrRef.current = xhr;

      // Resolves with the created document's id rather than `void`: the annotation-mode
      // trigger loop needs it to address the per-document pre-label endpoint. Callers that
      // do not need it simply ignore the value.
      return new Promise<UploadResult>((resolve, reject) => {
        xhr.upload.onprogress = (e: ProgressEvent) => {
          if (e.lengthComputable) {
            setProgress(Math.round((e.loaded / e.total) * 100));
          }
        };

        xhr.onload = () => {
          if (xhr.status === 201) {
            setProgress(100);
            setIsUploading(false);
            queryClient.invalidateQueries({ queryKey: ["documents"] });
            let id = "";
            try {
              id = JSON.parse(xhr.responseText)?.id ?? "";
            } catch {}
            resolve({ id });
          } else {
            let msg = `Upload failed: ${xhr.status}`;
            try {
              const body = JSON.parse(xhr.responseText);
              msg = body.detail ?? body.message ?? msg;
            } catch {}
            setError(msg);
            setIsUploading(false);
            reject(new Error(msg));
          }
        };

        xhr.onerror = () => {
          setError("Network error during upload");
          setIsUploading(false);
          reject(new Error("Network error"));
        };

        xhr.onabort = () => {
          setIsUploading(false);
          reject(new DOMException("Upload cancelled", "AbortError"));
        };

        const token = getAccessToken();
        const formData = new FormData();
        formData.append("file", file);
        formData.append("purpose", purpose);

        const baseUrl = DOCUMENT_URL || "";
        xhr.open("POST", `${baseUrl}/api/v1/documents`);
        if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
        xhr.send(formData);
      });
    },
    [getAccessToken, queryClient],
  );

  const reset = useCallback(() => {
    setProgress(0);
    setError(null);
    setIsUploading(false);
    xhrRef.current?.abort();
    xhrRef.current = null;
  }, []);

  const cancel = useCallback(() => {
    xhrRef.current?.abort();
  }, []);

  return { upload, progress, isUploading, error, reset, cancel };
}
