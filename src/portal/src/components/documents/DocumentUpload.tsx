"use client";

import { useState, useRef, useCallback } from "react";
import { useUpload } from "@/hooks/use-upload";

const ACCEPTED_TYPES = ["application/pdf", "image/jpeg", "image/png", "image/tiff"];
const MAX_SIZE = 50 * 1024 * 1024;

export function DocumentUpload() {
  const [dragOver, setDragOver] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const { upload, progress, isUploading, error, reset } = useUpload();

  const validate = useCallback((file: File): string | null => {
    if (!ACCEPTED_TYPES.includes(file.type)) {
      return `File type "${file.type}" is not supported. Accepted: PDF, JPEG, PNG, TIFF.`;
    }
    if (file.size > MAX_SIZE) {
      return `File exceeds the 50MB limit (${(file.size / (1024 * 1024)).toFixed(1)}MB).`;
    }
    return null;
  }, []);

  const handleFile = useCallback(
    async (file: File) => {
      setValidationError(null);
      setUploadSuccess(false);
      reset();

      const err = validate(file);
      if (err) {
        setValidationError(err);
        return;
      }

      try {
        await upload(file);
        setUploadSuccess(true);
      } catch {
        // error state is managed by the hook
      }
    },
    [upload, validate, reset],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragOver(false);

      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
      if (inputRef.current) inputRef.current.value = "";
    },
    [handleFile],
  );

  const handleClick = useCallback(() => {
    if (!isUploading) inputRef.current?.click();
  }, [isUploading]);

  const displayError = validationError ?? error;

  return (
    <div className="flex flex-col gap-3">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") handleClick();
        }}
        className={[
          "flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors",
          dragOver
            ? "border-brand-primary bg-brand-primary/5"
            : "border-gray-300 bg-gray-50 hover:border-gray-400",
          isUploading ? "pointer-events-none" : "",
        ].join(" ")}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.jpg,.jpeg,.png,.tiff,.tif"
          className="hidden"
          onChange={handleInputChange}
        />

        {isUploading ? (
          <div className="flex w-full max-w-xs flex-col items-center gap-2">
            <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200">
              <div
                className="h-full rounded-full bg-brand-primary transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
            <span className="text-sm text-gray-500">{progress}% uploaded</span>
          </div>
        ) : uploadSuccess ? (
          <div className="flex items-center gap-2 text-green-600">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="size-5">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
            </svg>
            <span className="text-sm font-medium">Upload successful</span>
          </div>
        ) : (
          <>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="mb-2 size-8 text-gray-400">
              <path d="M9.25 13.25a.75.75 0 001.5 0V4.636l2.955 3.128a.75.75 0 001.09-1.03l-4.25-4.5a.75.75 0 00-1.09 0l-4.25 4.5a.75.75 0 101.09 1.03L9.25 4.636V13.25z" />
              <path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z" />
            </svg>
            <p className="text-sm text-gray-600">
              <span className="font-medium text-brand-primary">Click to upload</span> or drag and drop
            </p>
            <p className="mt-1 text-xs text-gray-400">
              PDF, JPEG, PNG, or TIFF (max 50MB)
            </p>
          </>
        )}
      </div>

      {displayError && (
        <p className="text-sm text-red-600" role="alert">
          {displayError}
        </p>
      )}
    </div>
  );
}
