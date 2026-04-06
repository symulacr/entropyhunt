import { promises as fs } from "node:fs";
import * as path from "node:path";

export async function waitForSnapshots(snapshotDir: string, minCount: number, timeoutMs: number, pollMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const entries = await fs.readdir(snapshotDir);
      const jsonCount = entries.filter((name) => name.endsWith(".json")).length;
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

export async function waitForHttpReady(url: string, timeoutMs: number, pollMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let lastError = "unreachable";
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url, { cache: "no-store" });
      if (response.ok) {
        await response.json();
        return;
      }
      lastError = `HTTP ${response.status}`;
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    }
    await new Promise((resolve) => setTimeout(resolve, pollMs));
  }
  throw new Error(`Timed out waiting for snapshot server ${url}: ${lastError}`);
}

export async function waitForRuntimeReady(snapshotDir: string, snapshotUrl: string, timeoutMs: number, pollMs: number): Promise<void> {
  await waitForSnapshots(snapshotDir, 1, timeoutMs, pollMs);
  await waitForHttpReady(snapshotUrl, timeoutMs, pollMs);
}
