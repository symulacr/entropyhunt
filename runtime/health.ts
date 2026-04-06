import { promises as fs } from "node:fs";
import * as path from "node:path";

function isRuntimeSnapshotFile(name: string): boolean {
  return name.endsWith(".json") && name !== "control.json";
}

async function readRuntimeJson(response: Response): Promise<unknown> {
  return await response.json();
}

function hasExpectedPeerCount(payload: unknown, expectedPeerCount: number): boolean {
  if (!payload || typeof payload !== "object") {
    return false;
  }
  const summary = (payload as { summary?: unknown }).summary;
  if (!summary || typeof summary !== "object") {
    return false;
  }
  const peerCount = Number((summary as { peer_count?: unknown }).peer_count ?? 0);
  const drones = Array.isArray((summary as { drones?: unknown[] }).drones)
    ? (summary as { drones: unknown[] }).drones
    : [];
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
      // directory may not exist yet
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

export async function waitForRuntimeReady(
  snapshotDir: string,
  snapshotUrl: string,
  timeoutMs: number,
  pollMs: number,
  expectedPeerCount?: number,
): Promise<void> {
  await waitForSnapshots(snapshotDir, Math.max(1, expectedPeerCount ?? 1), timeoutMs, pollMs);
  await waitForHttpReady(snapshotUrl, timeoutMs, pollMs, expectedPeerCount);
}
