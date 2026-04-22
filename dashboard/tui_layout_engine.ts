import type { DisplayMode } from "./tui_monitor_model.ts";

export type TerminalBreakpoint = "compact" | "medium" | "wide" | "ultrawide";

export interface BentoLayout {
  breakpoint: TerminalBreakpoint;
  terminalWidth: number;
  terminalHeight: number;

  headerHeight: number;
  statsHeight: number;
  footerHeight: number;

  bodyWidth: number;
  bodyHeight: number;

  gap: number;
  panelPadding: number;

  heatmap: {
    width: number;
    height: number;
    cellWidth: number;
    rowRepeat: number;
    visible: boolean;
  };

  side: {
    width: number;
    height: number;
    direction: "row" | "column";
    visible: boolean;
  };

  roster: {
    width: number;
    height: number;
    maxVisible: number;
    visible: boolean;
  };

  events: {
    width: number;
    height: number;
    rowCount: number;
    maxVisible: number;
    visible: boolean;
  };

  detail: {
    width: number;
    height: number;
    visible: boolean;
  };

  modePanel: {
    width: number;
    height: number;
    visible: boolean;
  };

  stats: {
    compact: boolean;
    cardGap: number;
    cardPadding: number;
  };
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function breakpointFor(width: number, height: number): TerminalBreakpoint {
  if (width < 60 || height < 20) return "compact";
  if (width < 100 || height < 30) return "medium";
  if (width < 150) return "wide";
  return "ultrawide";
}

function computeCellWidth(availableWidth: number, gridSize: number, breakpoint: TerminalBreakpoint): number {
  const usable = Math.max(4, availableWidth - 3);
  const base = Math.floor(usable / Math.max(1, gridSize));
  const min = breakpoint === "compact" ? 2 : breakpoint === "medium" ? 3 : 4;
  const max = breakpoint === "ultrawide" ? 10 : breakpoint === "wide" ? 8 : 6;
  return clamp(base, min, max);
}

function computeRowRepeat(gridSize: number, availableRows: number, breakpoint: TerminalBreakpoint): number {
  const legendRows = breakpoint === "compact" ? 0 : 1;
  const axisRows = 1;
  const hintRows = 1;
  const dataRows = gridSize;
  const minHeatmapRows = legendRows + axisRows + dataRows + hintRows;
  if (availableRows <= minHeatmapRows) return 1;
  const spare = availableRows - minHeatmapRows;
  const maxRepeat = breakpoint === "ultrawide" ? 3 : breakpoint === "wide" ? 2 : 1;
  return clamp(Math.floor(spare / Math.max(1, gridSize)) + 1, 1, maxRepeat);
}

export function computeBentoLayout(args: {
  terminalWidth: number;
  terminalHeight: number;
  displayMode: DisplayMode;
  gridSize: number;
  droneCount: number;
  eventCount: number;
}): BentoLayout {
  const { terminalWidth, terminalHeight, displayMode, gridSize, droneCount, eventCount } = args;
  const bp = breakpointFor(terminalWidth, terminalHeight);

  const isAuxMode = displayMode === "config" || displayMode === "graphs" || displayMode === "detail";
  const isMapMode = displayMode === "map";

  const headerHeight = bp === "compact" ? 2 : 3;
  const statsHeight = 1;
  const footerHeight = 1;
  const gap = 0;
  const panelPadding = 0;

  const bodyWidth = terminalWidth;
  const bodyHeight = Math.max(1, terminalHeight - headerHeight - statsHeight - footerHeight - gap * 2);

  if (isAuxMode) {
    const modeHeight = Math.min(Math.max(16, bodyHeight - 2), bodyHeight);
    return {
      breakpoint: bp,
      terminalWidth,
      terminalHeight,
      headerHeight,
      statsHeight,
      footerHeight,
      bodyWidth,
      bodyHeight,
      gap,
      panelPadding,
      heatmap: { width: bodyWidth, height: 0, cellWidth: 2, rowRepeat: 1, visible: false },
      side: { width: bodyWidth, height: 0, direction: "column", visible: false },
      roster: { width: 0, height: 0, maxVisible: 0, visible: false },
      events: { width: 0, height: 0, rowCount: 0, maxVisible: 0, visible: false },
      detail: { width: 0, height: 0, visible: false },
      modePanel: {
        width: bp === "compact" ? bodyWidth : bodyWidth - 4,
        height: modeHeight,
        visible: true,
      },
      stats: { compact: bp === "compact", cardGap: 0, cardPadding: 0 },
    };
  }

  if (isMapMode) {
    const cellWidth = computeCellWidth(bodyWidth, gridSize, bp);
    const heatmapDataWidth = gridSize * cellWidth + 3;
    const rowRepeat = computeRowRepeat(gridSize, bodyHeight, bp);
    const heatmapHeight = gridSize * rowRepeat + 1;
    return {
      breakpoint: bp,
      terminalWidth,
      terminalHeight,
      headerHeight,
      statsHeight,
      footerHeight,
      bodyWidth,
      bodyHeight,
      gap: 0,
      panelPadding: 0,
      heatmap: {
        width: Math.max(heatmapDataWidth, bodyWidth),
        height: Math.min(heatmapHeight, bodyHeight),
        cellWidth,
        rowRepeat,
        visible: true,
      },
      side: { width: 0, height: 0, direction: "column", visible: false },
      roster: { width: 0, height: 0, maxVisible: 0, visible: false },
      events: { width: 0, height: 0, rowCount: 0, maxVisible: 0, visible: false },
      detail: { width: 0, height: 0, visible: false },
      modePanel: { width: 0, height: 0, visible: false },
      stats: { compact: true, cardGap: 0, cardPadding: 0 },
    };
  }

  const cellWidth = computeCellWidth(bodyWidth, gridSize, bp);
  const heatmapDataWidth = gridSize * cellWidth + 3;

  let heatmapWidth: number;
  let sideWidth: number;
  let sideDirection: "row" | "column" = "column";

  if (bp === "compact") {
    heatmapWidth = bodyWidth;
    sideWidth = bodyWidth;
    sideDirection = "column";
  } else if (bp === "medium") {
    heatmapWidth = Math.min(Math.max(heatmapDataWidth, Math.floor(bodyWidth * 0.58)), bodyWidth - 28);
    sideWidth = bodyWidth - heatmapWidth - gap;
    sideDirection = "column";
  } else if (bp === "wide") {
    heatmapWidth = Math.min(Math.max(heatmapDataWidth, Math.floor(bodyWidth * 0.55)), bodyWidth - 38);
    sideWidth = bodyWidth - heatmapWidth - gap;
    sideDirection = "column";
  } else {
    heatmapWidth = Math.min(Math.max(heatmapDataWidth, Math.floor(bodyWidth * 0.52)), bodyWidth - 52);
    sideWidth = bodyWidth - heatmapWidth - gap;
    sideDirection = "column";
  }

  const rowRepeat = computeRowRepeat(gridSize, bodyHeight, bp);
  const legendRows = bp === "compact" ? 0 : 1;
  const heatmapHeight = Math.min(
    bodyHeight,
    legendRows + 1 + gridSize * rowRepeat + 1
  );

  const sideHeight = bodyHeight;

  const rosterTitleHeight = 1;
  const rosterPadding = panelPadding * 2;
  const rosterItemHeight = 1;
  const maxRosterVisible = bp === "compact" ? 3 : bp === "medium" ? 5 : bp === "wide" ? 6 : 8;
  const rosterContentHeight = Math.min(droneCount, maxRosterVisible) * rosterItemHeight;
  const rosterHeight = Math.min(
    Math.max(rosterContentHeight + rosterTitleHeight + rosterPadding, bp === "compact" ? 3 : 4),
    Math.floor(sideHeight * 0.45)
  );

  const detailVisible = displayMode === "overview";
  const detailHeight = detailVisible ? 3 : 0;

  const eventsTitleHeight = 1;
  const eventsPadding = panelPadding * 2;
  const eventsAvailableHeight = Math.max(1, sideHeight - rosterHeight - detailHeight - gap * 2 - eventsTitleHeight - eventsPadding);
  const eventRowCount = Math.min(eventCount, Math.max(1, eventsAvailableHeight));
  const maxEventVisible = bp === "compact" ? 4 : bp === "medium" ? 8 : bp === "wide" ? 12 : 16;

  return {
    breakpoint: bp,
    terminalWidth,
    terminalHeight,
    headerHeight,
    statsHeight,
    footerHeight,
    bodyWidth,
    bodyHeight,
    gap,
    panelPadding,
    heatmap: {
      width: heatmapWidth,
      height: heatmapHeight,
      cellWidth,
      rowRepeat,
      visible: true,
    },
    side: {
      width: sideWidth,
      height: sideHeight,
      direction: sideDirection,
      visible: true,
    },
    roster: {
      width: sideDirection === "column" ? sideWidth : Math.floor(sideWidth * 0.45),
      height: rosterHeight,
      maxVisible: maxRosterVisible,
      visible: true,
    },
    events: {
      width: sideDirection === "column" ? sideWidth : sideWidth - Math.floor(sideWidth * 0.45) - gap,
      height: eventsAvailableHeight,
      rowCount: Math.min(eventRowCount, maxEventVisible),
      maxVisible: maxEventVisible,
      visible: true,
    },
    detail: {
      width: sideWidth,
      height: detailHeight,
      visible: detailVisible,
    },
    modePanel: { width: 0, height: 0, visible: false },
    stats: {
      compact: bp === "compact",
      cardGap: 0,
      cardPadding: 0,
    },
  };
}
