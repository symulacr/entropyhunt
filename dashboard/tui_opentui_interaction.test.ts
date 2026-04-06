import { test, expect } from "bun:test";
import { BoxRenderable, TextRenderable } from "@opentui/core";
import { createTestRenderer } from "@opentui/core/testing";

import { advanceUiState, type MonitorUiState } from "./tui_monitor_v2.ts";
import { bindMonitorMouseInteractions } from "./tui_monitor_interactions.ts";

test("OpenTUI mouse and key events drive monitor interaction helpers", async () => {
  const { renderer, mockInput, mockMouse, renderOnce } = await createTestRenderer({
    width: 80,
    height: 24,
    useMouse: true,
    autoFocus: true,
    screenMode: "main-screen",
  });

  let ui: MonitorUiState = {
    displayMode: "overview",
    focusedPanel: "heatmap",
    cursorX: 0,
    cursorY: 0,
    selectedDrone: 0,
    selectedEvent: 0,
  };

  const state = {
    gridSize: 5,
    drones: [{ id: "drone_1" }, { id: "drone_2" }],
    events: [{ t: 1 }, { t: 2 }, { t: 3 }],
  };

  const shell = new BoxRenderable(renderer, {
    id: "shell",
    width: 70,
    height: 8,
    flexDirection: "row",
    focusable: true,
  });
  shell.onKeyDown = (key) => {
    ui = advanceUiState(ui, state as any, key.name);
  };

  const heatmap = new BoxRenderable(renderer, { id: "heatmap", width: 30, height: 8 });
  heatmap.onMouseDown = () => {
    ui = { ...ui, focusedPanel: "heatmap" };
  };

  const roster = new BoxRenderable(renderer, { id: "roster", width: 40, height: 8 });
  roster.onMouseDown = () => {
    ui = { ...ui, focusedPanel: "roster" };
  };

  shell.add(heatmap);
  shell.add(roster);
  renderer.root.add(shell);
  shell.focus();

  await renderOnce();
  await mockMouse.click(35, 1);
  await renderOnce();
  expect(ui.focusedPanel).toBe("roster");

  mockInput.pressArrow("down");
  await renderOnce();
  expect(ui.selectedDrone).toBe(1);

  mockInput.pressArrow("left");
  await renderOnce();
  expect(ui.focusedPanel).toBe("heatmap");

  renderer.destroy();
});

test("graphs drilldown rows can select drones by mouse", async () => {
  const { renderer, renderOnce, mockMouse } = await createTestRenderer({
    width: 100,
    height: 24,
    useMouse: true,
    autoFocus: true,
    screenMode: "main-screen",
  });

  let selectedDrone = 0;
  let displayMode: "overview" | "detail" | "map" | "config" | "graphs" = "graphs";

  const shell = new BoxRenderable(renderer, {
    id: "shell",
    width: 100,
    height: 24,
    flexDirection: "column",
    focusable: true,
  });
  renderer.root.add(shell);

  const modeLines = Array.from({ length: 16 }, (_, index) => {
    const row = new TextRenderable(renderer, {
      id: `mode-${index}`,
      content: "x".repeat(80),
      wrapMode: "none",
      truncate: true,
    });
    shell.add(row);
    return row;
  });

  bindMonitorMouseInteractions({
    panelBindings: [],
    viewTabs: [],
    gridRows: [],
    gridRowMap: [],
    modeLines,
    droneRows: [],
    eventRows: [],
    getDisplayMode: () => displayMode,
    setFocusedPanel: () => {},
    setDisplayMode: (mode) => {
      displayMode = mode;
    },
    setSelectedDrone: (index) => {
      selectedDrone = index;
    },
    setSelectedEvent: () => {},
    setHeatmapCursor: () => {},
    getLastGood: () => ({ gridSize: 5 }),
    getCellWidth: () => 4,
  });

  await renderOnce();

  await mockMouse.click((modeLines[12]!.x ?? 0) + 5, modeLines[12]!.y ?? 0);
  await renderOnce();
  expect(selectedDrone).toBe(1);

  await mockMouse.click((modeLines[13]!.x ?? 0) + 5, modeLines[13]!.y ?? 0);
  await renderOnce();
  expect(selectedDrone).toBe(2);

  renderer.destroy();
});
