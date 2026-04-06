import type { Snapshot } from "./tui_types.ts";
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
  const args: MonitorArgs = {
    source: "http://127.0.0.1:8765/snapshot.json",
    intervalMs: Number(TUI_LAYOUT.pollIntervalMs),
  };

  for (let index = 0; index < argv.length; index += 1) {
    if (argv[index] === "--source" && argv[index + 1]) {
      args.source = argv[index + 1]!;
      index += 1;
    } else if (argv[index] === "--interval-ms" && argv[index + 1]) {
      const value = Number(argv[index + 1]);
      if (Number.isFinite(value) && value > 0) args.intervalMs = value;
      index += 1;
    }
  }

  return args;
}

export async function fetchMonitorSnapshot(url: string): Promise<Snapshot> {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return (await response.json()) as Snapshot;
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
  return (await response.json()) as Record<string, unknown>;
}
