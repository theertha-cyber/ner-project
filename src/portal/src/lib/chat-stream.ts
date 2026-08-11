export interface ChatStreamEvents {
  onToken?: (delta: string) => void;
  onDone?: (data: Record<string, unknown>) => void;
  onError?: (data: { code?: string; message?: string }) => void;
}

/**
 * Reads a `text/event-stream` response body and dispatches parsed SSE frames to
 * typed callbacks. Buffers partial frames across chunk boundaries (a `\n\n`-delimited
 * frame can arrive split across multiple `reader.read()` calls) and ignores SSE
 * comment lines (leading `:`, used for heartbeats). Resolves once the stream ends,
 * whether or not a `done` or `error` frame was ever seen — callers determine
 * "ended without a terminal event" themselves by tracking whether a callback fired.
 */
export async function readChatStream(response: Response, events: ChatStreamEvents): Promise<void> {
  if (!response.body) {
    throw new Error("Response has no readable body");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const rawFrame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        dispatchFrame(rawFrame, events);
        boundary = buffer.indexOf("\n\n");
      }
    }

    const trailing = buffer.trim();
    if (trailing) {
      dispatchFrame(trailing, events);
    }
  } finally {
    reader.releaseLock();
  }
}

function dispatchFrame(rawFrame: string, events: ChatStreamEvents): void {
  let eventName: string | null = null;
  const dataLines: string[] = [];

  for (const line of rawFrame.split("\n")) {
    if (line.startsWith(":")) continue;
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
  }

  if (!eventName) return;

  let data: Record<string, unknown> = {};
  const rawData = dataLines.join("\n");
  if (rawData) {
    try {
      data = JSON.parse(rawData);
    } catch {
      return;
    }
  }

  if (eventName === "token") {
    events.onToken?.(typeof data.delta === "string" ? data.delta : "");
  } else if (eventName === "done") {
    events.onDone?.(data);
  } else if (eventName === "error") {
    events.onError?.(data as { code?: string; message?: string });
  }
}
