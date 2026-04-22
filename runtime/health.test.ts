import { afterEach, expect, test } from "bun:test";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { createServer, type Server } from "node:http";
import { tmpdir } from "node:os";
import * as path from "node:path";
import { waitForRuntimeReady } from "./health";

const cleanupPaths: string[] = [];

afterEach(async () => {
  while (cleanupPaths.length > 0) {
    const target = cleanupPaths.pop();
    if (!target) continue;
    await rm(target, { recursive: true, force: true });
  }
});

function startJsonServer(readPayload: () => unknown): Promise<{ server: Server; url: string }> {
  return new Promise((resolve) => {
    const server = createServer((_request, response) => {
      const encoded = JSON.stringify(readPayload());
      response.writeHead(200, { "Content-Type": "application/json" });
      response.end(encoded);
    });
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        throw new Error("Failed to resolve readiness test server address");
      }
      resolve({ server, url: `http://127.0.0.1:${address.port}/snapshot.json` });
    });
  });
}

test("waitForRuntimeReady ignores control.json and waits for the full peer swarm", async () => {
  const snapshotDir = await mkdtemp(path.join(tmpdir(), "entropy-health-"));
  cleanupPaths.push(snapshotDir);

  let payload: unknown = { summary: { peer_count: 0, drones: [] } };
  const { server, url } = await startJsonServer(() => payload);
  try {
    await writeFile(path.join(snapshotDir, "control.json"), "{}\n");
    const startedAt = Date.now();
    const ready = waitForRuntimeReady(snapshotDir, url, 1_000, 20, 2);

    setTimeout(() => {
      writeFile(path.join(snapshotDir, "drone_1.json"), JSON.stringify({ summary: { peer_id: "drone_1" } })).catch(() => {});
      payload = { summary: { peer_count: 1, drones: [{ id: "drone_1" }] } };
    }, 60);

    setTimeout(() => {
      writeFile(path.join(snapshotDir, "drone_2.json"), JSON.stringify({ summary: { peer_id: "drone_2" } })).catch(() => {});
      payload = {
        summary: {
          peer_count: 2,
          drones: [{ id: "drone_1" }, { id: "drone_2" }],
        },
      };
    }, 140);

    await ready;
    expect(Date.now() - startedAt).toBeGreaterThanOrEqual(120);
  } finally {
    await new Promise<void>((resolve) => server.close(() => resolve()));
  }
});
