import { expect, it, vi } from "vitest";

import { setToken } from "../src/lib/auth";
import { openTraceStream } from "../src/lib/sse";

it("keeps the trace token in the Authorization header", async () => {
  setToken("secret-access-token");
  const payload = new TextEncoder().encode("event: done\ndata: {}\n\n");
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(payload);
      controller.close();
    },
  });
  const fetchMock = vi.fn().mockResolvedValue(new Response(body, { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);

  await new Promise<void>((resolve) => {
    openTraceStream("case-1", () => {}, undefined, undefined, { onDone: resolve });
  });

  expect(fetchMock).toHaveBeenCalledOnce();
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/v1/cases/case-1/stream");
  expect(url).not.toContain("token=");
  expect((init.headers as Record<string, string>).Authorization).toBe(
    "Bearer secret-access-token",
  );
  vi.unstubAllGlobals();
});
