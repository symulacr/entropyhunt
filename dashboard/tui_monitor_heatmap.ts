import type { TextRenderable } from "@opentui/core";

import { buildAxisRow, buildDroneIndex, buildLegend, renderHeatmapRow, updateAnimationTimelines, updateDroneTrails, checkSurvivorFlash } from "./tui_heatmap.ts";
import {
  type DisplayMode,
  type FocusPanel,
  type ViewState,
  computeActiveCellWidth,
  computeHeatmapRowRepeat,
  logicalHeatmapRowForRenderIndex,
} from "./tui_monitor_model.ts";
import { buildInspectorLine } from "./tui_monitor_presenters.ts";

export function syncMonitorHeatmap(args: {
  state: ViewState;
  compactLayout: boolean;
  displayMode: DisplayMode;
  gridFrameWidth: number;
  terminalWidth: number;
  fallbackCellWidth: number;
  axisTop: TextRenderable;
  heatmapLegend: TextRenderable;
  heatmapHint: TextRenderable;
  gridRows: TextRenderable[];
  gridRowMap: number[];
  cursorX: number;
  cursorY: number;
  focusedPanel: FocusPanel;
  survivorStartedAt: number;
  nowMs?: number;
}): number {
  const {
    state,
    compactLayout,
    displayMode,
    gridFrameWidth,
    terminalWidth,
    fallbackCellWidth,
    axisTop,
    heatmapLegend,
    heatmapHint,
    gridRows,
    gridRowMap,
    cursorX,
    cursorY,
    focusedPanel,
    survivorStartedAt,
    nowMs = Date.now(),
  } = args;

  const liveCellWidth = computeActiveCellWidth(gridFrameWidth || terminalWidth - 8, state.gridSize, fallbackCellWidth);
  const rowRepeat = computeHeatmapRowRepeat(state.gridSize, displayMode, compactLayout, gridRows.length);
  const renderedRows = Math.min(gridRows.length, state.gridSize * rowRepeat);
  const flashTarget = state.survivorFound && Math.floor((nowMs - survivorStartedAt) / 250) % 2 === 0;

  updateDroneTrails(state);
  updateAnimationTimelines(nowMs);
  checkSurvivorFlash(state.survivorFound);

  const drones = buildDroneIndex(state);

  axisTop.content = buildAxisRow(state.gridSize, liveCellWidth);
  heatmapLegend.content = buildLegend(compactLayout);
  heatmapHint.content = buildInspectorLine(state, cursorX, cursorY, compactLayout);

  for (let renderIndex = 0; renderIndex < gridRows.length; renderIndex += 1) {
    const logicalY = logicalHeatmapRowForRenderIndex(renderIndex, rowRepeat, state.gridSize);
    gridRowMap[renderIndex] = logicalY;
    gridRows[renderIndex]!.visible = renderIndex < renderedRows;
    gridRows[renderIndex]!.content = renderIndex < renderedRows
      ? renderHeatmapRow({
          y: logicalY,
          state,
          flashTarget,
          focusedCell: { x: cursorX, y: cursorY },
          focusedPanel: focusedPanel === "heatmap",
          cellWidth: liveCellWidth,
          droneIndex: drones,
        })
      : "";
  }

  return liveCellWidth;
}
