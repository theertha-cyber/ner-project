"use client";

import { useState, useCallback, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { DOCUMENT_URL } from "@/lib/api";

export function useUpload() {
  const [progress, setProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const xhrRef = useRef<XMLHttpRequest | null>(null);
  const queryClient = useQueryClient();
  const { getAccessToken } = useAuth();

  const upload = useCallback(
    async (file: File) => {
      setProgress(0);
      setError(null);
      setIsUploading(true);

      const xhr = new XMLHttpRequest();
      xhrRef.current = xhr;

      return new Promise<void>((resolve, reject) => {
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
            resolve();
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

        const token = getAccessToken();
        const formData = new FormData();
        formData.append("file", file);

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

  return { upload, progress, isUploading, error, reset };
}
