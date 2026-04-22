import { test, expect } from "bun:test";
import {
  advanceDisplayMode,
  advanceUiState,
  hitTestHeatmapCell,
  logicalHeatmapRowForRenderIndex,
  normalizeSnapshot,
  type MonitorUiState,
  type ViewState,
} from "./tui_monitor.ts";
import { computeMonitorLayout } from "./tui_monitor_model.ts";
import { isSnapshot } from "./tui_types.ts";
import { renderHeatmapRow } from "./tui_heatmap.ts";
import type { MonitorState } from "./tui_types.ts";
import { handleMonitorKeyDown } from "./tui_monitor_input.ts";
import { buildMonitorFooterMessage } from "./tui_monitor_chrome.ts";
import { buildCompactSubheaderLine } from "./tui_monitor_presenters.ts";
import { sampleViewState } from "./tui_monitor_frame_support.ts";
import { hasLostControllingParent, hasLostSource, hasLostWatchedParent } from "./tui_monitor_runtime.ts";

const baseUi: MonitorUiState = {
  displayMode: "overview",
  focusedPanel: "heatmap",
  cursorX: 0,
  cursorY: 0,
  selectedDrone: 0,
  selectedEvent: 0,
};

const baseState = {
  gridSize: 5,
  drones: [
    { id: "drone_1", x: 0, y: 0, tx: null, ty: null, status: "idle", offline: false, entropy: 0.5, searchedCells: 1 },
    { id: "drone_2", x: 1, y: 1, tx: null, ty: null, status: "idle", offline: false, entropy: 0.5, searchedCells: 2 },
  ],
  events: [
    { t: 1, type: "info", msg: "one" },
    { t: 2, type: "info", msg: "two" },
    { t: 3, type: "info", msg: "three" },
  ],
} satisfies Pick<ViewState, "gridSize" | "drones" | "events">;

test("display mode cycles forward and backward", () => {
  expect(advanceDisplayMode("overview")).toBe("detail");
  expect(advanceDisplayMode("detail")).toBe("map");
  expect(advanceDisplayMode("map")).toBe("config");
  expect(advanceDisplayMode("config")).toBe("graphs");
  expect(advanceDisplayMode("overview", true)).toBe("graphs");
  expect(advanceDisplayMode("graphs")).toBe("overview");
});

test("arrow keys move heatmap focus within bounds", () => {
  let ui = advanceUiState(baseUi, baseState, "right");
  ui = advanceUiState(ui, baseState, "right");
  ui = advanceUiState(ui, baseState, "down");
  expect(ui.cursorX).toBe(2);
  expect(ui.cursorY).toBe(1);
  ui = advanceUiState(ui, baseState, "left");
  ui = advanceUiState(ui, baseState, "up");
  expect(ui.cursorX).toBe(1);
  expect(ui.cursorY).toBe(0);
});

test("roster and event navigation clamp correctly", () => {
  let ui: MonitorUiState = { ...baseUi, focusedPanel: "roster", selectedDrone: 0, selectedEvent: 0 };
  ui = advanceUiState(ui, baseState, "down");
  ui = advanceUiState(ui, baseState, "down");
  expect(ui.selectedDrone).toBe(1);
  ui = advanceUiState(ui, baseState, "right");
  expect(ui.focusedPanel).toBe("events");
  ui = advanceUiState(ui, baseState, "down");
  ui = advanceUiState(ui, baseState, "down");
  ui = advanceUiState(ui, baseState, "down");
  expect(ui.selectedEvent).toBe(2);
});

test("heatmap hit testing maps mouse x to a valid cell", () => {
  expect(hitTestHeatmapCell(15, 4, 4, 5)).toBe(2);
  expect(hitTestHeatmapCell(999, 4, 4, 5)).toBe(4);
  expect(hitTestHeatmapCell(0, 4, 4, 5)).toBe(0);
});

test("rendered heatmap rows map back to logical grid rows for mouse focus", () => {
  expect(logicalHeatmapRowForRenderIndex(0, 2, 5)).toBe(0);
  expect(logicalHeatmapRowForRenderIndex(1, 2, 5)).toBe(0);
  expect(logicalHeatmapRowForRenderIndex(2, 2, 5)).toBe(1);
  expect(logicalHeatmapRowForRenderIndex(9, 2, 5)).toBe(4);
});

test("config mode keys emit control patches", () => {
  const result = handleMonitorKeyDown({
    key: { name: "]", raw: "]" },
    ui: { ...baseUi, displayMode: "config" },
    state: { ...baseState, tickSeconds: 1, tickDelaySeconds: 0.2, requestedDroneCount: 2, droneCount: 2, controlCapabilities: { tick_seconds: "live", tick_delay_seconds: "live", requested_drone_count: "next_run" } },
  });
  expect(result.kind).toBe("control");
  if (result.kind === "control") {
    expect(result.patch.tick_delay_seconds).toBe(0.15);
  }
});

test("config mode up/down changes selected config row", () => {
  const result = handleMonitorKeyDown({
    key: { name: "down", raw: "" },
    ui: { ...baseUi, displayMode: "config", selectedEvent: 0 },
    state: { ...baseState, tickSeconds: 1, tickDelaySeconds: 0.2, requestedDroneCount: 2, droneCount: 2, controlCapabilities: { tick_seconds: "live", tick_delay_seconds: "live", requested_drone_count: "next_run" } },
  });
  expect(result.kind).toBe("ui");
  if (result.kind === "ui") {
    expect(result.ui.selectedEvent).toBe(1);
  }
});

test("graphs mode up/down changes selected drone", () => {
  const result = handleMonitorKeyDown({
    key: { name: "down", raw: "" },
    ui: { ...baseUi, displayMode: "graphs", selectedDrone: 0 },
    state: { ...baseState, tickSeconds: 1, tickDelaySeconds: 0.2, requestedDroneCount: 2, droneCount: 2, controlCapabilities: { tick_seconds: "live", tick_delay_seconds: "live", requested_drone_count: "next_run" } },
  });
  expect(result.kind).toBe("ui");
  if (result.kind === "ui") {
    expect(result.ui.selectedDrone).toBe(1);
  }
});

test("config mode left/right adjusts the selected row", () => {
  const droneResult = handleMonitorKeyDown({
    key: { name: "right", raw: "" },
    ui: { ...baseUi, displayMode: "config", selectedEvent: 1 },
    state: { ...baseState, tickSeconds: 1, tickDelaySeconds: 0.2, requestedDroneCount: 2, droneCount: 2, controlCapabilities: { tick_seconds: "live", tick_delay_seconds: "live", requested_drone_count: "next_run" } },
  });
  expect(droneResult.kind).toBe("control");
  if (droneResult.kind === "control") {
    expect(droneResult.patch.requested_drone_count).toBe(3);
  }
});

test("config mode speed control falls back to tick_seconds when delay control is unavailable", () => {
  const result = handleMonitorKeyDown({
    key: { name: "right", raw: "" },
    ui: { ...baseUi, displayMode: "config", selectedEvent: 0 },
    state: {
      ...baseState,
      tickSeconds: 1,
      tickDelaySeconds: 0.2,
      requestedDroneCount: 2,
      droneCount: 2,
      controlCapabilities: { tick_seconds: "live", tick_delay_seconds: "unavailable", requested_drone_count: "next_run" },
    },
  });
  expect(result.kind).toBe("control");
  if (result.kind === "control") {
    expect(result.patch.tick_seconds).toBe(0.75);
  }
});

test("config footer reports live control status", () => {
  const message = buildMonitorFooterMessage({
    state: sampleViewState(),
    compactLayout: false,
    displayMode: "config",
    controlStatus: "applied",
    focusedPanel: "heatmap",
    cursorX: 0,
    cursorY: 0,
    selectedDrone: 0,
    selectedEvent: 1,
    tickLatencyMs: 8,
  });
  expect(message).toContain("config next run");
  expect(message).toContain("next-run drone count");
  expect(message).toContain("applied");
});

test("config footer reports read-only ROS-style control state", () => {
  const message = buildMonitorFooterMessage({
    state: {
      ...sampleViewState(),
      controlCapabilities: {
        tick_seconds: "unavailable",
        tick_delay_seconds: "unavailable",
        requested_drone_count: "unavailable",
      },
    },
    compactLayout: false,
    displayMode: "config",
    focusedPanel: "heatmap",
    cursorX: 0,
    cursorY: 0,
    selectedDrone: 0,
    selectedEvent: 0,
    tickLatencyMs: 8,
  });
  expect(message).toContain("config read-only");
});

test("config footer treats tick_seconds fallback as live speed control", () => {
  const message = buildMonitorFooterMessage({
    state: {
      ...sampleViewState(),
      controlCapabilities: {
        tick_seconds: "live",
        tick_delay_seconds: "unavailable",
        requested_drone_count: "next_run",
      },
    },
    compactLayout: false,
    displayMode: "config",
    focusedPanel: "heatmap",
    cursorX: 0,
    cursorY: 0,
    selectedDrone: 0,
    selectedEvent: 0,
    tickLatencyMs: 8,
  });
  expect(message).toContain("config live");
});

test("normalizeSnapshot preserves claimed cells and discloses truncation", () => {
  const state = normalizeSnapshot(
    {
      config: { grid_size: 12, drone_count: 7 },
      summary: {
        drones: [
          { id: "drone_1", position: [1, 1], claimed_cell: [2, 2], searched_cells: 4 },
          { id: "drone_2", position: [3, 3], searched_cells: 2 },
          { id: "drone_3", position: [4, 4] },
          { id: "drone_4", position: [5, 5] },
          { id: "drone_5", position: [6, 6] },
          { id: "drone_6", position: [7, 7] },
        ],
      },
      grid: Array.from({ length: 12 }, (_, y) =>
        Array.from({ length: 12 }, (_, x) => ({ x, y, certainty: 0.5 })),
      ),
      events: Array.from({ length: 20 }, (_, index) => ({ t: index, type: "info", message: `e${index}` })),
    },
    "http://127.0.0.1:8765/snapshot.json",
    false,
  );

  expect(state.grid[2]?.[2]?.owner).toBe(0);
  expect(state.drones[0]?.claimedCell).toEqual({ x: 2, y: 2 });
  expect(state.gridTruncated).toBe(true);
  expect(state.hiddenDroneCount).toBeGreaterThan(0);
  expect(state.hiddenEventCount).toBeGreaterThan(0);
});

test("overview footer makes hidden large-run limits explicit", () => {
  const message = buildMonitorFooterMessage({
    state: {
      ...sampleViewState(),
      gridTruncated: true,
      gridSize: 10,
      hiddenDroneCount: 2,
      hiddenEventCount: 7,
    },
    compactLayout: false,
    displayMode: "overview",
    focusedPanel: "heatmap",
    cursorX: 0,
    cursorY: 0,
    selectedDrone: 0,
    selectedEvent: 0,
    tickLatencyMs: 8,
  });
  expect(message).toContain("grid capped to 10x10");
  expect(message).toContain("+2 drones off-screen");
  expect(message).toContain("+7 older events hidden");
});

test("compact TUI subheader makes controls discoverable", () => {
  const text = buildCompactSubheaderLine(sampleViewState())
    .chunks
    .map((chunk) => chunk.text)
    .join("");
  expect(text).toContain("arrows move");
  expect(text).toContain("1-5/tab views");
  expect(text).toContain("h/r/e panels");
  expect(text).toContain("enter follow");
  expect(text).toContain("q quit");
});


test("layout metrics expand heatmap on wide terminals and stack on compact terminals", () => {
  const wide = computeMonitorLayout(200, 46, "overview", 10, 5, 10);
  expect(wide.breakpoint).not.toBe("compact");
  expect(wide.heatmap.width).toBeGreaterThanOrEqual(100);

  const medium = computeMonitorLayout(80, 24, "overview", 10, 5, 10);
  expect(medium.breakpoint).not.toBe("compact");
  expect(medium.heatmap.width).toBeGreaterThanOrEqual(50);
  expect(medium.statsHeight).toBe(1);
  expect(medium.headerHeight).toBe(3);
  expect(medium.footerHeight).toBe(1);

  const compact = computeMonitorLayout(50, 18, "overview", 10, 5, 10);
  expect(compact.breakpoint).toBe("compact");
  expect(compact.heatmap.width).toBe(50);
  expect(compact.events.rowCount).toBe(4);
  expect(compact.roster.height).toBe(4);
  expect(compact.headerHeight).toBe(2);
  expect(compact.statsHeight).toBe(1);
  expect(compact.footerHeight).toBe(1);
  expect(compact.heatmap.cellWidth).toBe(4);
});

test("focused heatmap cells preserve target and drone semantics", () => {
  const baseState = {
    elapsed: 0,
    coverage: 0,
    avgEntropy: 0,
    auctions: 0,
    dropouts: 0,
    bftRounds: 0,
    meshMode: "stub",
    grid: [
      [{ certainty: 0.5, owner: -1 }, { certainty: 0.5, owner: -1 }],
      [{ certainty: 0.5, owner: 0 }, { certainty: 0.5, owner: -1 }],
    ],
    drones: [{ id: "drone_1", x: 0, y: 0, tx: null, ty: null, status: "idle", offline: false, entropy: 0.5, searchedCells: 1 }],
    target: { x: 1, y: 0 },
    events: [],
    survivorFound: false,
    staleData: false,
  } as const satisfies MonitorState;

  const droneRow = renderHeatmapRow({
    y: 0,
    state: baseState,
    flashTarget: false,
    focusedCell: { x: 0, y: 0 },
    focusedPanel: true,
    cellWidth: 4,
  });
  const droneText = droneRow.chunks.map((chunk) => chunk.text).join("");
  expect(droneText).toContain("D1");

  const targetRow = renderHeatmapRow({
    y: 0,
    state: baseState,
    flashTarget: false,
    focusedCell: { x: 1, y: 0 },
    focusedPanel: true,
    cellWidth: 4,
  });
  const targetText = targetRow.chunks.map((chunk) => chunk.text).join("");
  expect(targetText).toContain("◎");
});

test("monitor exits when its controlling parent is lost", () => {
  expect(hasLostControllingParent(4242, 1)).toBe(true);
  expect(hasLostControllingParent(4242, 4242)).toBe(false);
  expect(hasLostControllingParent(1, 1)).toBe(false);
});

test("monitor exits when its watched parent pid disappears", () => {
  expect(hasLostWatchedParent(4242, () => false)).toBe(true);
  expect(hasLostWatchedParent(4242, () => true)).toBe(false);
  expect(hasLostWatchedParent(null, () => false)).toBe(false);
});

test("monitor exits when its source has been gone too long", () => {
  expect(hasLostSource(1000, 17001, 15000)).toBe(true);
  expect(hasLostSource(1000, 15000, 15000)).toBe(false);
  expect(hasLostSource(0, 20000, 15000)).toBe(false);
});

test("snapshot type guard rejects malformed object", () => {
  expect(isSnapshot(null)).toBe(false);
  expect(isSnapshot(undefined)).toBe(false);
  expect(isSnapshot("string")).toBe(false);
  expect(isSnapshot(123)).toBe(false);
  expect(isSnapshot({ t: "not-a-number" })).toBe(false);
  expect(isSnapshot({ survivor_found: "not-a-boolean" })).toBe(false);
  expect(isSnapshot({ grid: "not-an-array" })).toBe(false);
  expect(isSnapshot({ drones: "not-an-array" })).toBe(false);
  expect(isSnapshot({ events: "not-an-array" })).toBe(false);
  expect(isSnapshot({ summary: "not-an-object" })).toBe(false);
  expect(isSnapshot({ stats: "not-an-object" })).toBe(false);
  expect(isSnapshot({ config: "not-an-object" })).toBe(false);
  expect(isSnapshot({ t: 1, survivor_found: true, grid: [], drones: [], events: [], stats: {} })).toBe(true);
  expect(isSnapshot({})).toBe(false);
});
