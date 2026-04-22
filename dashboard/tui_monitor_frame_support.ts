import { BoxRenderable, TextRenderable } from "@opentui/core";
import { createTestRenderer } from "@opentui/core/testing";

import { buildAxisRow, buildDroneIndex, buildLegend, renderHeatmapRow } from "./tui_heatmap.ts";
import {
  type MonitorUiState,
  type ViewState,
  computeActiveCellWidth,
  computeLayoutMetrics,
  computeHeatmapRowRepeat,
  formatDuration,
} from "./tui_monitor_model.ts";
import { syncMonitorAuxPanel, type MonitorHistory } from "./tui_monitor_aux.ts";
import {
  buildCompactSubheaderLine,
  buildCompactHeaderLine,
  buildDetailSummary,
  buildDisplayModeChip,
  buildFocusStatusLine,
  buildHeaderLine,
  buildInspectorLine,
  buildSubheaderLine,
} from "./tui_monitor_presenters.ts";
import { buildFooterLine, renderDroneRow, renderEventRow } from "./tui_sidebar.ts";
import { COLORS, PANEL_THEME, coverageColorFor } from "./tui_theme.ts";

export function sampleViewState(): ViewState {
  return {
    elapsed: 92,
    coverage: 73,
    avgEntropy: 0.61,
    auctions: 7,
    dropouts: 1,
    bftRounds: 31,
    meshMode: "real",
    sourceLabel: "live",
    sourceUrl: "http://127.0.0.1:8765/snapshot.json",
    target: { x: 3, y: 2 },
    droneCount: 3,
    tickSeconds: 1,
    tickDelaySeconds: 0.1,
    requestedDroneCount: 4,
    controlUrl: "http://127.0.0.1:8765/control",
    controlCapabilities: {
      tick_seconds: "live",
      tick_delay_seconds: "live",
      requested_drone_count: "next_run",
    },
    gridSize: 5,
    grid: [
      [{ certainty: 0.51, owner: -1 }, { certainty: 0.62, owner: -1 }, { certainty: 0.78, owner: -1 }, { certainty: 0.45, owner: -1 }, { certainty: 0.32, owner: -1 }],
      [{ certainty: 0.95, owner: -1 }, { certainty: 0.31, owner: -1 }, { certainty: 0.44, owner: -1 }, { certainty: 0.57, owner: 0 }, { certainty: 0.49, owner: -1 }],
      [{ certainty: 0.87, owner: -1 }, { certainty: 0.53, owner: -1 }, { certainty: 0.28, owner: -1 }, { certainty: 0.51, owner: -1 }, { certainty: 0.67, owner: -1 }],
      [{ certainty: 0.41, owner: -1 }, { certainty: 0.22, owner: -1 }, { certainty: 0.18, owner: 1 }, { certainty: 0.36, owner: -1 }, { certainty: 0.59, owner: -1 }],
      [{ certainty: 0.14, owner: -1 }, { certainty: 0.26, owner: -1 }, { certainty: 0.33, owner: -1 }, { certainty: 0.48, owner: -1 }, { certainty: 0.66, owner: -1 }],
    ],
    drones: [
      { id: "drone_1", x: 1, y: 0, tx: 3, ty: 2, claimedCell: null, status: "searching", offline: false, entropy: 0.96, searchedCells: 19 },
      { id: "drone_2", x: 2, y: 3, tx: 4, ty: 4, claimedCell: null, status: "transit", offline: false, entropy: 0.68, searchedCells: 13 },
      { id: "drone_3", x: 4, y: 1, tx: null, ty: null, claimedCell: null, status: "offline", offline: true, entropy: 0.43, searchedCells: 7 },
    ],
    events: [
      { t: 92, type: "found", msg: "survivor confirmed at [3,2]" },
      { t: 60, type: "stale", msg: "drone_2 heartbeat timeout" },
      { t: 18, type: "bft", msg: "claim d1>d3 -> d1 holds" },
    ],
    survivorFound: true,
    staleData: false,
    hiddenDroneCount: 0,
    hiddenEventCount: 0,
    gridTruncated: false,
  };
}

function sampleHistory(): MonitorHistory {
  return {
    coverage: [12, 18, 27, 41, 55, 66, 73],
    uncertainty: [0.92, 0.88, 0.82, 0.75, 0.69, 0.64, 0.61],
    auctions: [1, 2, 3, 4, 5, 6, 7],
    dropouts: [0, 0, 1, 1, 1, 1, 1],
    latency: [21, 18, 17, 14, 12, 10, 9],
    drones: {
      drone_1: { entropy: [0.98, 0.97, 0.96], searched: [7, 13, 19] },
      drone_2: { entropy: [0.74, 0.71, 0.68], searched: [5, 9, 13] },
      drone_3: { entropy: [0.51, 0.47, 0.43], searched: [3, 5, 7] },
    },
  };
}

export async function renderMonitorTestFrame({
  width,
  height,
  ui,
  latencyMs = 12,
}: {
  width: number;
  height: number;
  ui: MonitorUiState;
  latencyMs?: number;
}): Promise<string> {
  const state = sampleViewState();
  const history = sampleHistory();
  const metrics = computeLayoutMetrics(width, height);
  const { compactLayout } = metrics;
  const isMapDisplay = ui.displayMode === "map";
  const isAuxDisplay = ui.displayMode === "config" || ui.displayMode === "graphs" || ui.displayMode === "detail";
  const testSetup = await createTestRenderer({ width, height, useMouse: true, autoFocus: true, screenMode: "main-screen" });
  const { renderer, renderOnce, captureCharFrame } = testSetup;

  const root = new BoxRenderable(renderer, {
    width: "100%",
    height: "100%",
    flexDirection: "column",
    backgroundColor: COLORS.bg,
    padding: 0,
  });
  renderer.root.add(root);
  const shell = new BoxRenderable(renderer, {
    width: "100%",
    height: "100%",
    flexDirection: "column",
    backgroundColor: COLORS.headerBg,
    border: true,
    borderColor: COLORS.border,
    padding: 0,
  });
  root.add(shell);

  const header = new BoxRenderable(renderer, { flexDirection: "column", backgroundColor: COLORS.headerBg, padding: 1, height: isMapDisplay ? (compactLayout ? 2 : 3) : metrics.headerHeight });
  shell.add(header);
  header.add(new TextRenderable(renderer, { content: compactLayout ? buildCompactHeaderLine(state) : buildHeaderLine(state), fg: PANEL_THEME.textPrimary, bg: COLORS.headerBg, wrapMode: "none", truncate: true, height: 1 }));
  header.add(new TextRenderable(renderer, { content: isMapDisplay ? buildCompactSubheaderLine(state) : compactLayout ? buildCompactSubheaderLine(state) : buildSubheaderLine(state), fg: PANEL_THEME.textMuted, bg: COLORS.headerBg, wrapMode: "none", truncate: true, height: 1 }));
  const tabs = new TextRenderable(
    renderer,
    {
      content: isMapDisplay
        ? buildDisplayModeChip("map", true, compactLayout).chunks.map((c) => c.text).join("")
        : `${buildDisplayModeChip("overview", ui.displayMode === "overview", compactLayout).chunks.map((c) => c.text).join("")} ${buildDisplayModeChip("detail", ui.displayMode === "detail", compactLayout).chunks.map((c) => c.text).join("")} ${buildDisplayModeChip("map", ui.displayMode === "map", compactLayout).chunks.map((c) => c.text).join("")} ${buildDisplayModeChip("config", ui.displayMode === "config", compactLayout).chunks.map((c) => c.text).join("")} ${buildDisplayModeChip("graphs", ui.displayMode === "graphs", compactLayout).chunks.map((c) => c.text).join("")}`,
      fg: PANEL_THEME.textPrimary,
      bg: COLORS.headerBg,
      wrapMode: "none",
      truncate: true,
    },
  );
  header.add(tabs);

  const stats = new TextRenderable(
    renderer,
    {
      content: compactLayout
        ? `scan ${Math.round(state.coverage)}% · unc ${state.avgEntropy.toFixed(2)} · ${state.auctions} claims · ${state.dropouts > 0 ? `${state.dropouts} lost` : "stable"} · ${formatDuration(state.elapsed)} · rt ${latencyMs}ms`
        : `coverage: ${Math.round(state.coverage)}% scanned · uncertainty: ${state.avgEntropy.toFixed(2)} · claims: ${state.auctions} settled · health: ${state.dropouts > 0 ? `${state.dropouts} lost link` : "stable"} · ${formatDuration(state.elapsed)} · rt ${latencyMs}ms`,
      fg: coverageColorFor(Math.round(state.coverage)),
      bg: COLORS.headerBg,
      wrapMode: "none",
      truncate: true,
      height: isMapDisplay ? 1 : metrics.statsHeight,
    },
  );
  shell.add(stats);

  const centeredAuxMode = ui.displayMode === "graphs" || ui.displayMode === "config" || ui.displayMode === "detail";
  const body = new BoxRenderable(renderer, {
    flexDirection: "column",
    flexGrow: 1,
    gap: 1,
    backgroundColor: COLORS.headerBg,
    paddingLeft: 1,
    paddingRight: 1,
    justifyContent: centeredAuxMode ? "center" : "flex-start",
    alignItems: centeredAuxMode ? "center" : "stretch",
  });
  shell.add(body);

  const availableMapRows = isMapDisplay
    ? Math.max(state.gridSize, height - metrics.headerHeight - metrics.statsHeight - 4)
    : undefined;
  const rowRepeat = computeHeatmapRowRepeat(state.gridSize, ui.displayMode, compactLayout, availableMapRows);
  const preferredHeatmapHeight = isMapDisplay
    ? Math.max(state.gridSize * rowRepeat + 1, availableMapRows ?? 0)
    : state.gridSize * rowRepeat + (compactLayout ? 5 : 4);
  const cellWidth = computeActiveCellWidth(width - 12, state.gridSize, metrics.cellWidth);
  if (isAuxDisplay) {
    const modePanel = new BoxRenderable(renderer, {
      flexDirection: "column",
      width: centeredAuxMode ? Math.min(width - 6, 96) : "100%",
      flexGrow: centeredAuxMode ? 0 : 1,
      border: true,
      borderColor: COLORS.border,
      backgroundColor: COLORS.headerBg,
      paddingTop: 0,
      paddingBottom: 0,
      paddingLeft: 1,
      paddingRight: 1,
      height: ui.displayMode === "graphs"
        ? Math.min(Math.max(18, height - metrics.headerHeight - metrics.statsHeight - metrics.footerHeight - 3), 22)
        : ui.displayMode === "config"
          ? Math.min(Math.max(16, height - metrics.headerHeight - metrics.statsHeight - metrics.footerHeight - 3), 19)
        : ui.displayMode === "detail"
          ? Math.min(Math.max(18, height - metrics.headerHeight - metrics.statsHeight - metrics.footerHeight - 3), 22)
        : Math.max(12, height - metrics.headerHeight - metrics.statsHeight - metrics.footerHeight - 3),
      title: ui.displayMode === "config" ? " runtime config " : ui.displayMode === "graphs" ? " speed & stats " : " drone detail ",
      titleAlignment: "left",
    });
    const modeLines: TextRenderable[] = [];
    for (let index = 0; index < 16; index += 1) {
      const line = new TextRenderable(renderer, {
        content: "",
        fg: PANEL_THEME.textPrimary,
        bg: COLORS.headerBg,
        wrapMode: "none",
        truncate: true,
      });
      modePanel.add(line);
      modeLines.push(line);
    }
    syncMonitorAuxPanel({ displayMode: ui.displayMode, state, history, modeLines, availableWidth: width, selectedDrone: ui.selectedDrone, selectedIndex: ui.selectedEvent });
    body.add(modePanel);
  } else {
    const heatmap = new BoxRenderable(renderer, { flexDirection: "column", width: "100%", height: isMapDisplay ? "auto" : compactLayout ? Math.max(9, preferredHeatmapHeight) : Math.max(12, preferredHeatmapHeight), flexGrow: 0, border: true, borderColor: COLORS.border, backgroundColor: COLORS.headerBg, padding: 0, title: compactLayout ? " mission grid " : " mission grid · uncertainty ", titleAlignment: "left" });
    if (!compactLayout) {
      heatmap.add(new TextRenderable(renderer, { content: buildLegend(compactLayout), fg: PANEL_THEME.textMuted, bg: COLORS.headerBg, wrapMode: "none", truncate: true }));
    }
    heatmap.add(new TextRenderable(renderer, { content: buildAxisRow(state.gridSize, cellWidth), fg: PANEL_THEME.textMuted, bg: COLORS.headerBg, wrapMode: "none", truncate: true }));
    const drones = buildDroneIndex(state);
    for (let y = 0; y < state.gridSize; y += 1) {
      for (let repeat = 0; repeat < rowRepeat; repeat += 1) {
        heatmap.add(new TextRenderable(renderer, {
          content: renderHeatmapRow({ y, state, flashTarget: state.survivorFound, focusedCell: { x: ui.cursorX, y: ui.cursorY }, focusedPanel: ui.focusedPanel === "heatmap", cellWidth, droneIndex: drones }),
          fg: PANEL_THEME.textPrimary,
          bg: COLORS.headerBg,
          wrapMode: "none",
          truncate: true,
        }));
      }
    }
    heatmap.add(new TextRenderable(renderer, { content: buildInspectorLine(state, ui.cursorX, ui.cursorY, compactLayout), fg: PANEL_THEME.textPrimary, bg: COLORS.headerBg, wrapMode: "none", truncate: true }));
    body.add(heatmap);
  }

  if (!isMapDisplay && !isAuxDisplay) {
    const side = new BoxRenderable(renderer, { flexDirection: compactLayout ? "column" : "row", width: "100%", gap: 1, backgroundColor: COLORS.headerBg, flexGrow: 1 });
    const contextColumn = new BoxRenderable(renderer, { flexDirection: "column", width: compactLayout ? "100%" : Math.max(34, Math.floor(width * 0.36)), gap: 1, backgroundColor: COLORS.headerBg });
    side.add(contextColumn);
    if (!(compactLayout && ui.displayMode === "detail")) {
      const roster = new BoxRenderable(renderer, { flexDirection: "column", border: true, borderColor: COLORS.border, backgroundColor: COLORS.headerBg, padding: 1, title: compactLayout ? " drones " : " active drones ", titleAlignment: "left", height: compactLayout ? 4 : 5 });
      for (let i = 0; i < state.drones.length; i += 1) {
        roster.add(new TextRenderable(renderer, {
          content: renderDroneRow({ drone: state.drones[i]!, selected: ui.focusedPanel === "roster" && ui.selectedDrone === i, focusedPanel: ui.focusedPanel === "roster" }),
          fg: PANEL_THEME.textPrimary,
          bg: COLORS.headerBg,
          wrapMode: "none",
          truncate: true,
        }));
      }
      contextColumn.add(roster);
    }
    if (ui.displayMode !== "overview") {
      const [a, b, c] = buildDetailSummary(state, ui.focusedPanel, ui.cursorX, ui.cursorY, ui.selectedDrone, ui.selectedEvent);
      const detail = new BoxRenderable(renderer, { flexDirection: "column", border: true, borderColor: COLORS.border, backgroundColor: COLORS.headerBg, padding: 1, title: " detail ", titleAlignment: "left", height: compactLayout ? Math.max(6, Math.floor(height * 0.22)) : 6, flexGrow: compactLayout ? 1 : 0 });
      detail.title = compactLayout ? " focus " : " focus detail ";
      detail.add(new TextRenderable(renderer, { content: a, fg: PANEL_THEME.textPrimary, bg: COLORS.headerBg, wrapMode: "none", truncate: true }));
      detail.add(new TextRenderable(renderer, { content: b, fg: PANEL_THEME.textSecondary, bg: COLORS.headerBg, wrapMode: "none", truncate: true }));
      detail.add(new TextRenderable(renderer, { content: c, fg: PANEL_THEME.textMuted, bg: COLORS.headerBg, wrapMode: "none", truncate: true }));
      contextColumn.add(detail);
    }
    if (!(compactLayout && ui.displayMode === "detail")) {
      const events = new BoxRenderable(renderer, { flexDirection: "column", flexGrow: 1, border: true, borderColor: COLORS.border, backgroundColor: COLORS.headerBg, padding: 1, title: compactLayout ? " alerts " : " attention & timeline ", titleAlignment: "left" });
      for (let i = 0; i < state.events.length; i += 1) {
        events.add(new TextRenderable(renderer, {
          content: renderEventRow({ event: state.events[i]!, selected: ui.focusedPanel === "events" && ui.selectedEvent === i, focusedPanel: ui.focusedPanel === "events" }),
          fg: PANEL_THEME.textPrimary,
          bg: COLORS.headerBg,
          wrapMode: "none",
          truncate: true,
        }));
      }
      side.add(events);
    }
    body.add(side);
  }

  const footer = new BoxRenderable(renderer, {
    flexDirection: "column",
    width: "100%",
    backgroundColor: COLORS.headerBg,
    height: isMapDisplay ? 1 : metrics.footerHeight,
    padding: 0,
  });
  footer.add(new TextRenderable(renderer, {
    content: buildFooterLine(
      ui.displayMode === "config"
        ? `${state.controlUrl ? "config live" : "config read-only"} · editing ${ui.selectedEvent === 0 ? "speed" : "next-run drone count"} · ←/→ adjust`
        : ui.displayMode === "graphs"
          ? `graphs live history · coverage / uncertainty / auctions / dropouts / latency · rt=${latencyMs}ms`
          : `${state.survivorFound ? "survivor confirmed — hold the grid" : `mesh ${state.meshMode} healthy`} · ${buildFocusStatusLine(state, ui.focusedPanel, ui.cursorX, ui.cursorY, ui.selectedDrone, ui.selectedEvent, latencyMs, compactLayout).chunks.map((c) => c.text).join("")}`,
    ),
    fg: PANEL_THEME.textMuted,
    bg: COLORS.headerBg,
    wrapMode: "none",
    truncate: true,
  }));
  shell.add(footer);

  await renderOnce();
  const frame = captureCharFrame();
  renderer.destroy();
  return frame;
}
