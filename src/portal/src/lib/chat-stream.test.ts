import { describe, it, expect, vi } from "vitest";
import { readChatStream } from "./chat-stream";

function streamResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
  return new Response(stream);
}

describe("readChatStream", () => {
  it("dispatches token, done, and error frames to their callbacks", async () => {
    const resp = streamResponse([
      'event: token\ndata: {"delta": "Based"}\n\n' +
        'event: token\ndata: {"delta": " on"}\n\n' +
        'event: done\ndata: {"reply": "Based on"}\n\n',
    ]);

    const onToken = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();

    await readChatStream(resp, { onToken, onDone, onError });

    expect(onToken.mock.calls.map((c) => c[0])).toEqual(["Based", " on"]);
    expect(onDone).toHaveBeenCalledWith({ reply: "Based on" });
    expect(onError).not.toHaveBeenCalled();
  });

  it("reassembles a frame split across multiple chunk boundaries", async () => {
    const resp = streamResponse([
      "event: to",
      'ken\ndata: {"delta": "Based on the docume',
      'nts"}\n\n',
    ]);

    const onToken = vi.fn();
    await readChatStream(resp, { onToken });

    expect(onToken).toHaveBeenCalledWith("Based on the documents");
  });

  it("ignores SSE comment lines", async () => {
    const resp = streamResponse([
      ": heartbeat\n\n" + 'event: token\ndata: {"delta": "hi"}\n\n',
    ]);

    const onToken = vi.fn();
    await readChatStream(resp, { onToken });

    expect(onToken).toHaveBeenCalledWith("hi");
    expect(onToken).toHaveBeenCalledTimes(1);
  });

  it("dispatches an error frame with code and message", async () => {
    const resp = streamResponse([
      'event: error\ndata: {"code": "GENERATION_FAILED", "message": "boom"}\n\n',
    ]);

    const onError = vi.fn();
    await readChatStream(resp, { onError });

    expect(onError).toHaveBeenCalledWith({ code: "GENERATION_FAILED", message: "boom" });
  });

  it("resolves without calling done or error when the stream ends abruptly", async () => {
    const resp = streamResponse(['event: token\ndata: {"delta": "partial"}\n\n']);

    const onDone = vi.fn();
    const onError = vi.fn();
    await readChatStream(resp, { onDone, onError });

    expect(onDone).not.toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
  });
});
