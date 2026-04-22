import type { Snapshot } from "./tui_types.ts";
import { isSnapshot, isObject } from "./tui_types.ts";
import { TUI_LAYOUT } from "./tui_theme.ts";

export type MonitorArgs = {
  source: string;
  intervalMs: number;
};

export type MonitorControlPatch = {
  tick_seconds?: number;
  tick_delay_seconds?: number;
  requested_drone_count?: number;
};

export function parseMonitorArgs(argv: string[]): MonitorArgs {
  const args: Partial<MonitorArgs> = {
    source: "http://127.0.0.1:8765/snapshot.json",
    intervalMs: Number(TUI_LAYOUT.pollIntervalMs),
  };

  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--source" && argv[i + 1]) {
      args.source = argv[++i];
      continue;
    }
    if (argv[i] === "--interval-ms" && argv[i + 1]) {
      const value = Number(argv[++i]);
      if (Number.isFinite(value) && value > 0) args.intervalMs = value;
      continue;
    }
  }

  return args as MonitorArgs;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchWithTimeout(url: string, options: RequestInit = {}): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    return response;
  } finally {
    clearTimeout(timeout);
  }
}

async function fetchWithRetry(url: string, options: RequestInit = {}): Promise<Response> {
  const delays = [500, 1000];
  for (let attempt = 0; attempt <= delays.length; attempt++) {
    try {
      const response = await fetchWithTimeout(url, options);
      if (!response.ok && response.status >= 500 && attempt < delays.length) {
        await delay(delays[attempt]);
        continue;
      }
      return response;
    } catch (error) {
      if (error instanceof TypeError && attempt < delays.length) {
        await delay(delays[attempt]);
        continue;
      }
      throw error;
    }
  }
  throw new Error("Unexpected end of retry loop");
}

export async function fetchMonitorSnapshot(url: string): Promise<Snapshot> {
  const response = await fetchWithRetry(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const data = await response.json();
  if (!isSnapshot(data)) throw new Error("Invalid snapshot response");
  return data;
}

function controlUrlForSnapshot(sourceUrl: string): string {
  const url = new URL(sourceUrl);
  url.pathname = "/control";
  url.search = "";
  url.hash = "";
  return url.toString();
}

export async function postMonitorControl(sourceUrl: string, patch: MonitorControlPatch): Promise<Record<string, unknown>> {
  const response = await fetch(controlUrlForSnapshot(sourceUrl), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const payload = await response.json();
  if (!isObject(payload)) throw new Error("Invalid control response");
  return payload;
}
