"use client";

import { useLayoutEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface TruncatableReplyProps {
  content: string;
}

// Whether a reply truncates is decided by actual rendered overflow, not by any
// line/row count: `chat-reply-clamp` (globals.css) clips the reply to a fixed
// number of visual lines by default, and a useLayoutEffect measurement (before
// the clamped state, so it always starts truncated and never flashes full-height
// content) compares scrollHeight against clientHeight to detect whether the clamp
// actually cut anything off. Only then does the "See more" toggle appear.
export function TruncatableReply({ content }: TruncatableReplyProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [overflows, setOverflows] = useState(false);
  const [expanded, setExpanded] = useState(false);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    setOverflows(el.scrollHeight > el.clientHeight + 1);
    // Re-measure only when the reply itself changes; expand/collapse toggling
    // doesn't need to re-derive whether the content overflows in principle.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [content]);

  return (
    <div>
      <div
        ref={ref}
        className={`chat-markdown chat-doc${expanded ? "" : " chat-reply-clamp"}`}
      >
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
      {overflows && (
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          style={{
            marginTop: 8,
            padding: 0,
            border: "none",
            background: "transparent",
            color: "var(--primary)",
            fontSize: 13,
            fontWeight: 500,
            cursor: "pointer",
          }}
        >
          {expanded ? "See less" : "See more"}
        </button>
      )}
    </div>
  );
}
