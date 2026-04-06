import type { BoxRenderable, TextRenderable } from "@opentui/core";

import type { DisplayMode } from "./tui_monitor_model.ts";

export function applyMonitorLayout(args: {
  compactLayout: boolean;
  displayMode: DisplayMode;
  terminalWidth: number;
  terminalHeight: number;
  headerHeight: number;
  statsHeight: number;
  footerHeight: number;
  preferredHeatmapHeight: number;
  eventRowCount: number;
  body: BoxRenderable;
  headerBox: BoxRenderable;
  statsRow: BoxRenderable;
  heatmapPanel: BoxRenderable;
  modePanel: BoxRenderable;
  gridFrame: BoxRenderable;
  heatmapLegend: TextRenderable;
  side: BoxRenderable;
  contextColumn: BoxRenderable;
  rosterBox: BoxRenderable;
  eventsBox: BoxRenderable;
  footerBox: BoxRenderable;
  compactStatsText: TextRenderable;
  statCards: BoxRenderable[];
  eventRows: TextRenderable[];
}) {
  const {
    compactLayout,
    displayMode,
    terminalWidth,
    terminalHeight,
    headerHeight,
    statsHeight,
    footerHeight,
    preferredHeatmapHeight,
    eventRowCount,
    body,
    headerBox,
    statsRow,
    heatmapPanel,
    modePanel,
    gridFrame,
    heatmapLegend,
    side,
    contextColumn,
    rosterBox,
    eventsBox,
    footerBox,
    compactStatsText,
    statCards,
    eventRows,
  } = args;

  body.flexDirection = "column";
  body.gap = 1;
  const centeredAuxMode = displayMode === "graphs" || displayMode === "config" || displayMode === "detail";
  body.justifyContent = centeredAuxMode ? "center" : "flex-start";
  body.alignItems = centeredAuxMode ? "center" : "stretch";
  headerBox.height = headerHeight;
  if (displayMode === "map") {
    headerBox.height = compactLayout ? 2 : 3;
  }
  headerBox.padding = compactLayout ? 0 : 1;
  statsRow.height = statsHeight;
  if (displayMode === "map") {
    statsRow.height = 1;
  }
  statsRow.paddingLeft = compactLayout ? 0 : 1;
  statsRow.paddingRight = compactLayout ? 0 : 1;
  statsRow.gap = compactLayout ? 0 : 1;
  statsRow.flexDirection = compactLayout ? "column" : "row";
  const fullPanelMode = displayMode === "config" || displayMode === "graphs" || displayMode === "detail";
  heatmapPanel.visible = !fullPanelMode;
  heatmapPanel.width = "100%";
  heatmapPanel.height = compactLayout
    ? Math.max(9, preferredHeatmapHeight)
    : Math.max(12, preferredHeatmapHeight);
  heatmapPanel.padding = 0;
  heatmapPanel.title = compactLayout ? " mission grid " : " mission grid · uncertainty ";
  modePanel.visible = fullPanelMode;
  const availableAuxHeight = terminalHeight - headerHeight - statsHeight - footerHeight - 3;
  modePanel.height = displayMode === "graphs"
    ? (compactLayout ? Math.min(Math.max(16, availableAuxHeight), 20) : Math.min(Math.max(18, availableAuxHeight), 22))
    : displayMode === "config"
      ? (compactLayout ? Math.min(Math.max(15, availableAuxHeight), 19) : Math.min(Math.max(16, availableAuxHeight), 19))
    : displayMode === "detail"
      ? (compactLayout ? Math.min(Math.max(16, availableAuxHeight), 20) : Math.min(Math.max(18, availableAuxHeight), 22))
    : compactLayout ? Math.max(9, availableAuxHeight) : Math.max(12, availableAuxHeight);
  modePanel.width = displayMode === "graphs" || displayMode === "config"
    ? (compactLayout ? "100%" : Math.min(terminalWidth - 6, 96))
    : displayMode === "detail"
      ? (compactLayout ? "100%" : Math.min(terminalWidth - 6, 96))
    : "100%";
  modePanel.flexGrow = centeredAuxMode ? 0 : 1;
  modePanel.padding = compactLayout ? 0 : 1;
  modePanel.title = displayMode === "config" ? " runtime config " : displayMode === "graphs" ? " speed & stats " : displayMode === "detail" ? " drone detail " : " mode ";
  gridFrame.padding = 0;
  gridFrame.flexGrow = 0;
  heatmapLegend.visible = !compactLayout;
  if (displayMode === "map") {
    heatmapLegend.visible = false;
  }
  side.visible = displayMode === "overview";
  side.height = compactLayout
    ? Math.max(8, terminalHeight - headerHeight - statsHeight - footerHeight - (typeof heatmapPanel.height === "number" ? heatmapPanel.height : 12) - 3)
    : "auto";
  side.width = "100%";
  side.gap = 1;
  side.flexDirection = compactLayout ? "column" : "row";
  contextColumn.width = compactLayout ? "100%" : Math.max(34, Math.floor(terminalWidth * 0.36));
  rosterBox.visible = !(compactLayout && displayMode === "detail");
  rosterBox.height = compactLayout && displayMode === "detail" ? 0 : compactLayout ? 4 : 5;
  rosterBox.padding = compactLayout ? 0 : 1;
  rosterBox.title = compactLayout ? " drones " : " active drones ";
  eventsBox.visible = !(compactLayout && displayMode === "detail");
  eventsBox.padding = compactLayout ? 0 : 1;
  eventsBox.title = compactLayout ? " alerts " : " attention & timeline ";
  eventsBox.flexGrow = 1;
  footerBox.padding = compactLayout ? 0 : 1;
  footerBox.height = displayMode === "map" ? 1 : footerHeight;
  compactStatsText.visible = compactLayout;
  for (const card of statCards) card.visible = !compactLayout;
  for (let index = 0; index < eventRows.length; index += 1) {
    eventRows[index]!.visible = index < eventRowCount;
  }
}
