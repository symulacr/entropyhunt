import { BoxRenderable, TextRenderable, bold as withBold, fg as withFg, t } from "@opentui/core";

import { buildAxisRow, buildLegend } from "./tui_heatmap.ts";
import { MAX_DRONE_LINES, MAX_EVENT_LINES, MAX_GRID_DIMENSION, MAX_GRID_RENDER_ROWS } from "./tui_monitor_model.ts";
import { createMonitorStatsRow, createMonitorViewTabs, createTextRows, type MonitorViewTab } from "./tui_monitor_renderables.ts";
import { COLORS, PANEL_THEME } from "./tui_theme.ts";

type RenderContext = ConstructorParameters<typeof BoxRenderable>[0] & {
  root: { add: (node: BoxRenderable) => unknown };
};

export type MonitorScene = {
  shell: BoxRenderable;
  headerBox: BoxRenderable;
  headerLine: TextRenderable;
  subheaderLine: TextRenderable;
  viewTabs: MonitorViewTab[];
  statsRow: BoxRenderable;
  statLabels: TextRenderable[];
  statValues: TextRenderable[];
  statCards: BoxRenderable[];
  compactStatsText: TextRenderable;
  body: BoxRenderable;
  heatmapPanel: BoxRenderable;
  heatmapLegend: TextRenderable;
  gridFrame: BoxRenderable;
  axisTop: TextRenderable;
  gridRowMap: number[];
  gridRows: TextRenderable[];
  heatmapHint: TextRenderable;
  modePanel: BoxRenderable;
  modeLines: TextRenderable[];
  side: BoxRenderable;
  contextColumn: BoxRenderable;
  rosterBox: BoxRenderable;
  droneRows: TextRenderable[];
  detailBox: BoxRenderable;
  detailTitle: TextRenderable;
  detailLine1: TextRenderable;
  detailLine2: TextRenderable;
  eventsBox: BoxRenderable;
  eventRows: TextRenderable[];
  footerBox: BoxRenderable;
  footerLine: TextRenderable;
  waitingShell: BoxRenderable;
  waitingBody: TextRenderable;
};

export function createMonitorScene(args: {
  renderer: RenderContext;
  headerHeight: number;
  statsHeight: number;
  rosterHeight: number;
  footerHeight: number;
  heatmapWidth: number;
}): MonitorScene {
  const { renderer, headerHeight, statsHeight, rosterHeight, footerHeight, heatmapWidth } = args;

  const root = new BoxRenderable(renderer, {
    id: "root",
    width: "100%",
    height: "100%",
    flexDirection: "column",
    backgroundColor: COLORS.bg,
    padding: 0,
  });
  renderer.root.add(root);

  const shell = new BoxRenderable(renderer, {
    id: "shell",
    width: "100%",
    height: "100%",
    flexDirection: "column",
    backgroundColor: COLORS.headerBg,
    border: true,
    borderColor: COLORS.border,
    focusable: true,
    gap: 0,
    padding: 0,
  });
  root.add(shell);

  const headerBox = new BoxRenderable(renderer, {
    id: "header-box",
    flexDirection: "column",
    backgroundColor: COLORS.headerBg,
    padding: 1,
    gap: 0,
    height: headerHeight,
  });
  shell.add(headerBox);

  const headerLine = new TextRenderable(renderer, { id: "header-line", content: "", fg: PANEL_THEME.textPrimary, bg: COLORS.headerBg, wrapMode: "none", truncate: true, height: 1 });
  const subheaderLine = new TextRenderable(renderer, { id: "subheader-line", content: "", fg: PANEL_THEME.textMuted, bg: COLORS.headerBg, wrapMode: "none", truncate: true, height: 1 });
  const { box: viewTabsBox, tabs: viewTabs } = createMonitorViewTabs(renderer);
  headerBox.add(headerLine);
  headerBox.add(subheaderLine);
  headerBox.add(viewTabsBox);

  const { row: statsRow, labels: statLabels, values: statValues, cards: statCards, compactText: compactStatsText } = createMonitorStatsRow(renderer);
  statsRow.height = statsHeight;
  shell.add(statsRow);

  const body = new BoxRenderable(renderer, {
    id: "body",
    flexDirection: "row",
    flexGrow: 1,
    gap: 1,
    backgroundColor: COLORS.headerBg,
    paddingLeft: 1,
    paddingRight: 1,
  });
  shell.add(body);

  const heatmapPanel = new BoxRenderable(renderer, {
    id: "heatmap-panel",
    width: heatmapWidth,
    flexDirection: "column",
    border: true,
    borderColor: COLORS.border,
    backgroundColor: COLORS.headerBg,
    padding: 1,
    gap: 1,
    title: " mission grid · uncertainty ",
    titleAlignment: "left",
  });
  body.add(heatmapPanel);

  const heatmapLegend = new TextRenderable(renderer, { id: "heatmap-legend", content: buildLegend(), fg: PANEL_THEME.textMuted, bg: COLORS.headerBg, wrapMode: "none", truncate: true });
  heatmapPanel.add(heatmapLegend);

  const gridFrame = new BoxRenderable(renderer, {
    id: "grid-frame",
    flexDirection: "column",
    border: true,
    borderColor: COLORS.border,
    backgroundColor: COLORS.panelBg,
    padding: 1,
    gap: 0,
    flexGrow: 0,
  });
  heatmapPanel.add(gridFrame);

  const axisTop = new TextRenderable(renderer, { id: "axis-top", content: buildAxisRow(MAX_GRID_DIMENSION), fg: PANEL_THEME.textMuted, bg: COLORS.panelBg, wrapMode: "none", truncate: true });
  gridFrame.add(axisTop);

  const gridRowMap: number[] = Array.from({ length: MAX_GRID_RENDER_ROWS }, () => 0);
  const gridRows = createTextRows({ renderer, parent: gridFrame, count: MAX_GRID_RENDER_ROWS, prefix: "grid-row", fg: PANEL_THEME.textPrimary, bg: COLORS.panelBg });

  const heatmapHint = new TextRenderable(renderer, { id: "heatmap-hint", content: "", fg: PANEL_THEME.textPrimary, bg: COLORS.headerBg, wrapMode: "none", truncate: true });
  heatmapPanel.add(heatmapHint);

  const modePanel = new BoxRenderable(renderer, {
    id: "mode-panel",
    width: "100%",
    flexDirection: "column",
    border: true,
    borderColor: COLORS.border,
    backgroundColor: COLORS.headerBg,
    paddingTop: 0,
    paddingBottom: 0,
    paddingLeft: 1,
    paddingRight: 1,
    gap: 0,
    title: " mode ",
    titleAlignment: "left",
    visible: false,
    flexGrow: 1,
  });
  const modeLines = createTextRows({ renderer, parent: modePanel, count: 16, prefix: "mode-line", fg: PANEL_THEME.textPrimary, bg: COLORS.headerBg });
  body.add(modePanel);

  const side = new BoxRenderable(renderer, { id: "side", flexDirection: "column", flexGrow: 1, gap: 1, backgroundColor: COLORS.headerBg });
  body.add(side);
  const contextColumn = new BoxRenderable(renderer, {
    id: "context-column",
    flexDirection: "column",
    gap: 1,
    backgroundColor: COLORS.headerBg,
  });
  side.add(contextColumn);

  const rosterBox = new BoxRenderable(renderer, {
    id: "roster-box",
    flexDirection: "column",
    border: true,
    borderColor: COLORS.border,
    backgroundColor: COLORS.headerBg,
    padding: 1,
    gap: 0,
    height: rosterHeight,
    title: " active drones ",
    titleAlignment: "left",
  });
  contextColumn.add(rosterBox);
  const droneRows = createTextRows({ renderer, parent: rosterBox, count: MAX_DRONE_LINES, prefix: "drone-row", fg: PANEL_THEME.textPrimary, bg: COLORS.headerBg });

  const detailBox = new BoxRenderable(renderer, {
    id: "detail-box",
    flexDirection: "column",
    border: true,
    borderColor: COLORS.border,
    backgroundColor: COLORS.headerBg,
    padding: 1,
    gap: 0,
    title: " focus detail ",
    titleAlignment: "left",
    visible: false,
  });
  const detailTitle = new TextRenderable(renderer, { id: "detail-title", content: "", fg: PANEL_THEME.textPrimary, bg: COLORS.headerBg, wrapMode: "none", truncate: true });
  const detailLine1 = new TextRenderable(renderer, { id: "detail-line1", content: "", fg: PANEL_THEME.textSecondary, bg: COLORS.headerBg, wrapMode: "none", truncate: true });
  const detailLine2 = new TextRenderable(renderer, { id: "detail-line2", content: "", fg: PANEL_THEME.textMuted, bg: COLORS.headerBg, wrapMode: "none", truncate: true });
  detailBox.add(detailTitle);
  detailBox.add(detailLine1);
  detailBox.add(detailLine2);
  contextColumn.add(detailBox);

  const eventsBox = new BoxRenderable(renderer, {
    id: "events-box",
    flexDirection: "column",
    flexGrow: 1,
    border: true,
    borderColor: COLORS.border,
    backgroundColor: COLORS.headerBg,
    padding: 1,
    gap: 0,
    title: " attention & timeline ",
    titleAlignment: "left",
  });
  side.add(eventsBox);
  const eventRows = createTextRows({ renderer, parent: eventsBox, count: MAX_EVENT_LINES, prefix: "event-row", fg: PANEL_THEME.textPrimary, bg: COLORS.headerBg });

  const footerBox = new BoxRenderable(renderer, { id: "footer-box", backgroundColor: COLORS.headerBg, padding: 1, height: footerHeight });
  footerBox.width = "100%";
  shell.add(footerBox);
  const footerLine = new TextRenderable(renderer, { id: "footer-line", content: "", fg: PANEL_THEME.textMuted, bg: COLORS.headerBg, wrapMode: "none", truncate: true });
  footerBox.add(footerLine);

  const waitingShell = new BoxRenderable(renderer, {
    id: "waiting-shell",
    width: "100%",
    height: "100%",
    flexDirection: "column",
    backgroundColor: COLORS.headerBg,
    border: true,
    borderColor: COLORS.border,
    padding: 2,
    gap: 1,
  });
  root.add(waitingShell);
  waitingShell.visible = false;
  const waitingTitle = new TextRenderable(renderer, { id: "waiting-title", content: t`${withFg(COLORS.warning)(withBold("WAITING FOR SWARM"))}`, fg: COLORS.warning, bg: COLORS.headerBg, wrapMode: "none", truncate: true });
  const waitingBody = new TextRenderable(renderer, { id: "waiting-body", content: "", fg: PANEL_THEME.textMuted, bg: COLORS.headerBg, wrapMode: "none", truncate: true });
  waitingShell.add(waitingTitle);
  waitingShell.add(waitingBody);

  return {
    shell,
    headerBox,
    headerLine,
    subheaderLine,
    viewTabs,
    statsRow,
    statLabels,
    statValues,
    statCards,
    compactStatsText,
    body,
    heatmapPanel,
    heatmapLegend,
    gridFrame,
    axisTop,
    gridRowMap,
    gridRows,
    heatmapHint,
    modePanel,
    modeLines,
    side,
    contextColumn,
    rosterBox,
    droneRows,
    detailBox,
    detailTitle,
    detailLine1,
    detailLine2,
    eventsBox,
    eventRows,
    footerBox,
    footerLine,
    waitingShell,
    waitingBody,
  };
}
