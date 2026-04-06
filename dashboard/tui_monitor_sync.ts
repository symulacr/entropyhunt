import { buildFooterLine as buildFooterLineShared } from "./tui_sidebar.ts";
import {
  type DisplayMode,
  type FocusPanel,
  type MonitorUiState,
  type ViewState,
  MAX_GRID_DIMENSION,
  computeHeatmapRowRepeat,
  computeLayoutMetrics,
} from "./tui_monitor_model.ts";
import { syncMonitorStats } from "./tui_monitor_stats.ts";
import { syncMonitorHeatmap } from "./tui_monitor_heatmap.ts";
import { syncMonitorSidebar } from "./tui_monitor_sidebar.ts";
import { buildMonitorFooterMessage, syncMonitorHeader } from "./tui_monitor_chrome.ts";
import { syncMonitorAuxPanel, type MonitorHistory } from "./tui_monitor_aux.ts";
import { applyMonitorLayout } from "./tui_monitor_layout.ts";
import { clampMonitorFocus, syncFocusedPanel, type MonitorPanelBinding } from "./tui_monitor_focus.ts";
import type { MonitorScene } from "./tui_monitor_scene.ts";

export function syncMonitorFrame(args: {
  state: ViewState;
  rendererWidth: number;
  rendererHeight: number;
  compactLayout: boolean;
  eventRowCount: number;
  heatmapWidth: number;
  rosterHeight: number;
  headerHeight: number;
  statsHeight: number;
  footerHeight: number;
  cellWidth: number;
  ui: MonitorUiState;
  lastTickLatencyMs: number;
  survivorStartedAt: number;
  history: MonitorHistory;
  controlStatus: string;
  panelBindings: MonitorPanelBinding[];
  scene: MonitorScene;
  requestRender: () => void;
}) {
  const {
    state,
    rendererWidth,
    rendererHeight,
    compactLayout,
    eventRowCount,
    heatmapWidth,
    rosterHeight,
    headerHeight,
    statsHeight,
    footerHeight,
    cellWidth,
    ui,
    lastTickLatencyMs,
    survivorStartedAt,
    history,
    controlStatus,
    panelBindings,
    scene,
    requestRender,
  } = args;

  const layout = computeLayoutMetrics(rendererWidth, rendererHeight);
  const activeGridSize = Math.max(1, Math.min(state.gridSize ?? MAX_GRID_DIMENSION, MAX_GRID_DIMENSION));
  const legendRows = layout.compactLayout ? 0 : 1;
  const availableMapRows = ui.displayMode === "map"
    ? Math.max(activeGridSize, rendererHeight - layout.headerHeight - layout.statsHeight - 4)
    : undefined;
  const rowRepeat = computeHeatmapRowRepeat(activeGridSize, ui.displayMode, layout.compactLayout, availableMapRows);
  const preferredHeatmapHeight = ui.displayMode === "map"
    ? Math.max(activeGridSize * rowRepeat + legendRows + 1, availableMapRows ?? 0)
    : activeGridSize * rowRepeat + legendRows + (layout.compactLayout ? 5 : 3);

  applyMonitorLayout({
    compactLayout: layout.compactLayout,
    displayMode: ui.displayMode,
    terminalWidth: rendererWidth,
    terminalHeight: rendererHeight,
    headerHeight: layout.headerHeight,
    statsHeight: layout.statsHeight,
    footerHeight: layout.footerHeight,
    preferredHeatmapHeight,
    eventRowCount: layout.eventRowCount,
    body: scene.body,
    headerBox: scene.headerBox,
    statsRow: scene.statsRow,
    heatmapPanel: scene.heatmapPanel,
    modePanel: scene.modePanel,
    gridFrame: scene.gridFrame,
    heatmapLegend: scene.heatmapLegend,
    side: scene.side,
    contextColumn: scene.contextColumn,
    rosterBox: scene.rosterBox,
    eventsBox: scene.eventsBox,
    detailBox: scene.detailBox,
    footerBox: scene.footerBox,
    compactStatsText: scene.compactStatsText,
    statCards: scene.statCards,
    eventRows: scene.eventRows,
  });

  const clampedUi = clampMonitorFocus(ui, state);
  syncMonitorHeader({
    state,
    compactLayout: layout.compactLayout,
    displayMode: clampedUi.displayMode,
    headerLine: scene.headerLine,
    subheaderLine: scene.subheaderLine,
    viewTabs: scene.viewTabs,
  });
  syncMonitorStats({
    compactLayout: layout.compactLayout,
    state,
    tickLatencyMs: lastTickLatencyMs,
    compactStatsText: scene.compactStatsText,
    statCards: scene.statCards,
    statLabels: scene.statLabels,
    statValues: scene.statValues,
  });
  const nextCellWidth = syncMonitorHeatmap({
    state,
    compactLayout: layout.compactLayout,
    displayMode: clampedUi.displayMode,
    gridFrameWidth: scene.gridFrame.width,
    terminalWidth: rendererWidth,
    fallbackCellWidth: cellWidth,
    axisTop: scene.axisTop,
    heatmapLegend: scene.heatmapLegend,
    heatmapHint: scene.heatmapHint,
    gridRows: scene.gridRows,
    gridRowMap: scene.gridRowMap,
    cursorX: clampedUi.cursorX,
    cursorY: clampedUi.cursorY,
    focusedPanel: clampedUi.focusedPanel,
    survivorStartedAt,
  });
  syncMonitorSidebar({
    state,
    focusedPanel: clampedUi.focusedPanel,
    cursorX: clampedUi.cursorX,
    cursorY: clampedUi.cursorY,
    selectedDrone: clampedUi.selectedDrone,
    selectedEvent: clampedUi.selectedEvent,
    eventRowCount: layout.eventRowCount,
    detailTitle: scene.detailTitle,
    detailLine1: scene.detailLine1,
    detailLine2: scene.detailLine2,
    droneRows: scene.droneRows,
    eventRows: scene.eventRows,
  });
  if (ui.displayMode === "config" || ui.displayMode === "graphs" || ui.displayMode === "detail") {
    syncMonitorAuxPanel({
      displayMode: ui.displayMode,
      state,
      history,
      modeLines: scene.modeLines,
      availableWidth: rendererWidth,
      selectedDrone: clampedUi.selectedDrone,
      selectedIndex: ui.selectedEvent,
    });
  }
  scene.footerLine.content = buildFooterLineShared(buildMonitorFooterMessage({
    state,
    compactLayout: layout.compactLayout,
    displayMode: ui.displayMode,
    controlStatus,
    focusedPanel: clampedUi.focusedPanel,
    cursorX: clampedUi.cursorX,
    cursorY: clampedUi.cursorY,
    selectedDrone: clampedUi.selectedDrone,
    selectedEvent: clampedUi.selectedEvent,
    tickLatencyMs: lastTickLatencyMs,
  }));
  syncFocusedPanel({ focusedPanel: clampedUi.focusedPanel, panelBindings, requestRender });

  return {
    layout,
    ui: clampedUi,
    cellWidth: nextCellWidth,
  };
}
