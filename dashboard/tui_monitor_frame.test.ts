import { expect, test } from "bun:test";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { renderMonitorTestFrame } from "./tui_monitor_frame_support.ts";

const HERE = dirname(fileURLToPath(import.meta.url));
const FIXTURE_DIR = join(HERE, "__fixtures__");

function fixturePath(name: string): string {
  return join(FIXTURE_DIR, name);
}

function readFixture(name: string): string {
  return readFileSync(fixturePath(name), "utf8");
}

async function assertFrameFixture(name: string, frame: Promise<string>) {
  const rendered = await frame;
  if (process.env.UPDATE_TUI_FIXTURES === "1") {
    mkdirSync(FIXTURE_DIR, { recursive: true });
    writeFileSync(fixturePath(name), rendered);
  }
  expect(rendered).toBe(readFixture(name));
}

test("wide overview frame matches fixture", async () => {
  await assertFrameFixture(
    "tui_monitor_wide.txt",
    renderMonitorTestFrame({
      width: 120,
      height: 32,
      ui: {
        displayMode: "overview",
        focusedPanel: "heatmap",
        cursorX: 2,
        cursorY: 2,
        selectedDrone: 0,
        selectedEvent: 0,
      },
      latencyMs: 9,
    }),
  );
});

test("compact detail frame matches fixture", async () => {
  await assertFrameFixture(
    "tui_monitor_compact.txt",
    renderMonitorTestFrame({
      width: 80,
      height: 24,
      ui: {
        displayMode: "detail",
        focusedPanel: "roster",
        cursorX: 1,
        cursorY: 0,
        selectedDrone: 1,
        selectedEvent: 0,
      },
      latencyMs: 14,
    }),
  );
});

test("wide map frame matches fixture", async () => {
  await assertFrameFixture(
    "tui_monitor_map.txt",
    renderMonitorTestFrame({
      width: 120,
      height: 32,
      ui: {
        displayMode: "map",
        focusedPanel: "heatmap",
        cursorX: 3,
        cursorY: 2,
        selectedDrone: 0,
        selectedEvent: 0,
      },
      latencyMs: 7,
    }),
  );
});

test("wide config frame matches fixture", async () => {
  await assertFrameFixture(
    "tui_monitor_config.txt",
    renderMonitorTestFrame({
      width: 120,
      height: 32,
      ui: {
        displayMode: "config",
        focusedPanel: "heatmap",
        cursorX: 0,
        cursorY: 0,
        selectedDrone: 0,
        selectedEvent: 0,
      },
      latencyMs: 8,
    }),
  );
});

test("wide graphs frame matches fixture", async () => {
  await assertFrameFixture(
    "tui_monitor_graphs.txt",
    renderMonitorTestFrame({
      width: 120,
      height: 32,
      ui: {
        displayMode: "graphs",
        focusedPanel: "heatmap",
        cursorX: 0,
        cursorY: 0,
        selectedDrone: 0,
        selectedEvent: 0,
      },
      latencyMs: 8,
    }),
  );
});
