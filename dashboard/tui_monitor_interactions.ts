import type { BoxRenderable, TextRenderable } from "@opentui/core";

import type { FocusPanel } from "./tui_monitor_model.ts";
import { hitTestHeatmapCell } from "./tui_monitor_model.ts";
import type { MonitorPanelBinding } from "./tui_monitor_focus.ts";
import type { MonitorViewTab } from "./tui_monitor_renderables.ts";

function bindIndexedRows(rows: TextRenderable[], panel: FocusPanel, assign: (index: number) => void, setFocusedPanel: (panel: FocusPanel) => void) {
  for (const [index, row] of rows.entries()) {
    row.onMouseDown = () => {
      assign(index);
      setFocusedPanel(panel);
    };
  }
}

function bindGraphsDroneRows(args: {
  modeLines: TextRenderable[];
  getDisplayMode: () => MonitorViewTab["mode"];
  setDisplayMode: (mode: MonitorViewTab["mode"]) => void;
  setSelectedDrone: (index: number) => void;
}) {
  const { modeLines, getDisplayMode, setDisplayMode, setSelectedDrone } = args;
  const droneRows = [modeLines[11], modeLines[12], modeLines[13]];
  droneRows.forEach((row, index) => {
    if (!row) return;
    row.onMouseDown = () => {
      if (getDisplayMode() !== "graphs") return;
      setSelectedDrone(index);
      setDisplayMode("graphs");
    };
  });
}

export function bindMonitorMouseInteractions(args: {
  panelBindings: MonitorPanelBinding[];
  viewTabs: MonitorViewTab[];
  gridRows: TextRenderable[];
  gridRowMap: number[];
  modeLines: TextRenderable[];
  droneRows: TextRenderable[];
  eventRows: TextRenderable[];
  getDisplayMode: () => MonitorViewTab["mode"];
  setFocusedPanel: (panel: FocusPanel) => void;
  setDisplayMode: (mode: MonitorViewTab["mode"]) => void;
  setSelectedDrone: (index: number) => void;
  setSelectedEvent: (index: number) => void;
  setHeatmapCursor: (cursorX: number, cursorY: number) => void;
  getLastGood: () => { gridSize: number } | null;
  getCellWidth: () => number;
}) {
  const {
    panelBindings,
    viewTabs,
    gridRows,
    gridRowMap,
    modeLines,
    droneRows,
    eventRows,
    getDisplayMode,
    setFocusedPanel,
    setDisplayMode,
    setSelectedDrone,
    setSelectedEvent,
    setHeatmapCursor,
    getLastGood,
    getCellWidth,
  } = args;

  for (const binding of panelBindings) {
    binding.renderable.onMouseDown = () => setFocusedPanel(binding.panel);
  }
  for (const tab of viewTabs) {
    tab.renderable.onMouseDown = () => setDisplayMode(tab.mode);
  }
  for (const [index, row] of gridRows.entries()) {
    row.onMouseDown = (event) => {
      const lastGood = getLastGood();
      if (!lastGood) return;
      setHeatmapCursor(
        hitTestHeatmapCell(event.x, row.x, getCellWidth(), lastGood.gridSize),
        Math.max(0, Math.min(gridRowMap[index] ?? 0, lastGood.gridSize - 1)),
      );
      setFocusedPanel("heatmap");
    };
  }
  bindIndexedRows(droneRows, "roster", setSelectedDrone, setFocusedPanel);
  bindIndexedRows(eventRows, "events", setSelectedEvent, setFocusedPanel);
  bindGraphsDroneRows({ modeLines, getDisplayMode, setDisplayMode, setSelectedDrone });
}
