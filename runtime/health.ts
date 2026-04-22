import { promises as fs } from "node:fs";
import * as path from "node:path";

function isRuntimeSnapshotFile(name: string): boolean {
  return name.endsWith(".json") && name !== "control.json";
}

async function readRuntimeJson(response: Response): Promise<unknown> {
  return await response.json();
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function hasExpectedPeerCount(payload: unknown, expectedPeerCount: number): boolean {
  if (!isRecord(payload)) {
    return false;
  }
  const summary = payload.summary;
  if (!isRecord(summary)) {
    return false;
  }
  const peerCount = Number(summary.peer_count ?? 0);
  const drones = Array.isArray(summary.drones) ? summary.drones : [];
  return peerCount >= expectedPeerCount && drones.length >= expectedPeerCount;
}

export async function waitForSnapshots(snapshotDir: string, minCount: number, timeoutMs: number, pollMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const entries = await fs.readdir(snapshotDir);
      const jsonCount = entries.filter(isRuntimeSnapshotFile).length;
      if (jsonCount >= minCount) {
        return;
      }
    } catch {
    }
    await new Promise((resolve) => setTimeout(resolve, pollMs));
  }
  throw new Error(`Timed out waiting for ${minCount} snapshot files in ${path.resolve(snapshotDir)}`);
}

export async function waitForHttpReady(
  url: string,
  timeoutMs: number,
  pollMs: number,
  expectedPeerCount?: number,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let lastError = "unreachable";
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url, { cache: "no-store" });
      if (response.ok) {
        const payload = await readRuntimeJson(response);
        if (expectedPeerCount === undefined || hasExpectedPeerCount(payload, expectedPeerCount)) {
          return;
        }
        lastError = `runtime not yet reporting ${expectedPeerCount} ready peers`;
      } else {
        lastError = `HTTP ${response.status}`;
      }
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    }
    await new Promise((resolve) => setTimeout(resolve, pollMs));
  }
  throw new Error(`Timed out waiting for snapshot server ${url}: ${lastError}`);
}

async function fetchPeerStatus(host: string, port: number): Promise<{ peer_id: string; peers_seen: string[] } | null> {
  try {
    const response = await fetch(`http://${host}:${port}/status`, { cache: "no-store" });
    if (response.ok) {
      return await response.json() as { peer_id: string; peers_seen: string[] };
    }
  } catch {}
  return null;
}

export async function waitForPeerMeshReady(
  host: string,
  basePort: number,
  expectedPeerCount: number,
  timeoutMs: number,
  pollMs: number,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let lastError = "";
  while (Date.now() < deadline) {
    const statuses = await Promise.all(
      Array.from({ length: expectedPeerCount }, async (_, i) => {
        const port = basePort + i;
        return fetchPeerStatus(host, port);
      }),
    );
    const allReady = statuses.every((status) => {
      if (!status) return false;
      return status.peers_seen.length >= expectedPeerCount;
    });
    if (allReady) {
      return;
    }
    const missing = statuses
      .map((s, i) => ({ peer_id: s?.peer_id ?? `drone_${i + 1}`, seen: s?.peers_seen?.length ?? 0 }))
      .filter((p) => p.seen < expectedPeerCount);
    lastError = missing.map((m) => `${m.peer_id} sees ${m.seen}/${expectedPeerCount} peers`).join(", ");
    await new Promise((resolve) => setTimeout(resolve, pollMs));
  }
  throw new Error(`Timed out waiting for peer mesh visibility: ${lastError}`);
}

export async function waitForRuntimeReady(
  snapshotDir: string,
  snapshotUrl: string,
  timeoutMs: number,
  pollMs: number,
  expectedPeerCount?: number,
  peerHost?: string,
  peerBasePort?: number,
): Promise<void> {
  if (expectedPeerCount && expectedPeerCount > 1 && peerHost && typeof peerBasePort === "number") {
    const meshDeadline = Date.now() + Math.min(timeoutMs, 10_000);
    const meshTimeout = Math.max(0, meshDeadline - Date.now());
    await waitForPeerMeshReady(peerHost, peerBasePort, expectedPeerCount, meshTimeout, pollMs);
  }
  await waitForSnapshots(snapshotDir, Math.max(1, expectedPeerCount ?? 1), timeoutMs, pollMs);
  await waitForHttpReady(snapshotUrl, timeoutMs, pollMs, expectedPeerCount);
}
