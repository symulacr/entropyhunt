import type { BoxRenderable, TextRenderable } from "@opentui/core";

import type { DisplayMode } from "./tui_monitor_model.ts";
import type { BentoLayout } from "./tui_layout_engine.ts";

export function applyMonitorLayout(args: {
  layout: BentoLayout;
  displayMode: DisplayMode;
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
    layout,
    displayMode,
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

  const isMap = displayMode === "map";
  const isAux = displayMode === "config" || displayMode === "graphs" || displayMode === "detail";
  const compact = layout.breakpoint === "compact";

  body.flexDirection = "column";
  body.gap = layout.gap;
  body.justifyContent = isAux ? "center" : "flex-start";
  body.alignItems = isAux ? "center" : "stretch";
  body.paddingLeft = 0;
  body.paddingRight = 0;

  headerBox.height = layout.headerHeight;
  headerBox.padding = 0;
  headerBox.gap = 0;

  statsRow.height = layout.statsHeight;
  statsRow.paddingLeft = 0;
  statsRow.paddingRight = 0;
  statsRow.gap = 0;
  statsRow.flexDirection = "row";

  heatmapPanel.visible = layout.heatmap.visible;
  heatmapPanel.width = layout.heatmap.width;
  heatmapPanel.height = layout.heatmap.height;
  heatmapPanel.padding = layout.panelPadding;
  heatmapPanel.gap = 0;
  heatmapPanel.border = false;

  modePanel.visible = layout.modePanel.visible;
  modePanel.width = layout.modePanel.width;
  modePanel.height = layout.modePanel.height;
  modePanel.flexGrow = isAux ? 0 : 1;
  modePanel.padding = 0;
  modePanel.border = false;

  gridFrame.padding = 0;
  gridFrame.gap = 0;
  gridFrame.flexGrow = 0;
  gridFrame.border = false;

  heatmapLegend.visible = layout.heatmap.visible && !compact && !isMap;

  side.visible = layout.side.visible;
  side.height = layout.side.height;
  side.width = layout.side.width;
  side.gap = 0;
  side.flexDirection = layout.side.direction;

  contextColumn.width = layout.side.direction === "column" ? layout.side.width : layout.roster.width;
  contextColumn.gap = 0;

  rosterBox.visible = layout.roster.visible;
  rosterBox.height = layout.roster.height;
  rosterBox.width = layout.roster.width;
  rosterBox.padding = 0;
  rosterBox.border = false;

  eventsBox.visible = layout.events.visible;
  eventsBox.width = layout.events.width;
  eventsBox.padding = 0;
  eventsBox.flexGrow = 1;
  eventsBox.border = false;

  footerBox.height = layout.footerHeight;
  footerBox.padding = 0;

  compactStatsText.visible = layout.stats.compact;
  for (const card of statCards) {
    card.visible = !layout.stats.compact;
    card.border = false;
    card.paddingLeft = 0;
    card.paddingRight = 0;
  }
  for (let index = 0; index < eventRows.length; index += 1) {
    eventRows[index]!.visible = index < layout.events.rowCount;
  }
}
