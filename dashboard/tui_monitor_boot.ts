import { createCliRenderer } from "@opentui/core";

import { FOCUS_THEME } from "./tui_theme.ts";
import {
  type DisplayMode,
  type FocusPanel,
  type ViewState,
  computeMonitorLayout,
} from "./tui_monitor_model.ts";
import { handleMonitorKeyDown } from "./tui_monitor_input.ts";
import { syncWaitingShell } from "./tui_monitor_runtime.ts";
import { bindMonitorMouseInteractions } from "./tui_monitor_interactions.ts";
import { createMonitorScene } from "./tui_monitor_scene.ts";
import { postMonitorControl, type MonitorArgs } from "./tui_monitor_io.ts";
import { syncMonitorFrame } from "./tui_monitor_sync.ts";
import { type MonitorPanelBinding } from "./tui_monitor_focus.ts";
import type { MonitorHistory } from "./tui_monitor_aux.ts";
import {
  attachAnimationEngine,
  createTargetPulseTimeline,
  createFooterHeartbeatTimeline,
} from "./tui_monitor_animations.ts";
import type { Timeline } from "@opentui/core";
import { createShutdown } from "./tui_monitor_shutdown.ts";

const SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

export interface MonitorContext {
  renderer: Awaited<ReturnType<typeof createCliRenderer>>;
  scene: ReturnType<typeof createMonitorScene>;
  layout: {
    compactLayout: boolean;
    eventRowCount: number;
    heatmapWidth: number;
    rosterHeight: number;
    headerHeight: number;
    statsHeight: number;
    footerHeight: number;
    cellWidth: number;
  };
  ui: {
    displayMode: DisplayMode;
    focusedPanel: FocusPanel;
    cursorX: number;
    cursorY: number;
    selectedDrone: number;
    selectedEvent: number;
  };
  history: MonitorHistory;
  timers: {
    timer: ReturnType<typeof setTimeout> | null;
    orphanWatchTimer: ReturnType<typeof setInterval> | null;
    controlStatusTimer: ReturnType<typeof setTimeout> | null;
  };
  lastGood: ViewState | null;
  lastTickLatencyMs: number;
  lastSuccessfulSnapshotAt: number;
  spinnerIndex: number;
  survivorStartedAt: number;
  controlStatus: string;
  controlRequestId: number;
  closed: boolean;
  args: MonitorArgs;
  timelines: Timeline[];
  initialParentPid: number;
  watchedParentPid: number;
  sourceLossExitMs: number;
  panelBindings: MonitorPanelBinding[];
  requestRender: () => void;
  setControlStatus: (next: string, clearAfterMs?: number) => void;
  renderLatest: () => void;
  updateView: (state: ViewState) => void;
  setWaiting: (visible: boolean, sourceUrl: string) => void;
  applyControlPatch: (patch: { tick_seconds?: number; tick_delay_seconds?: number; requested_drone_count?: number }) => void;
  shutdown: () => void;
  handleResize: () => void;
  isPidAlive: (pid: number) => boolean;
}

export async function bootMonitor(args: MonitorArgs): Promise<MonitorContext> {
  const renderer = await createCliRenderer({
    targetFps: 18,
    screenMode: "alternate-screen",
    exitOnCtrlC: true,
    useMouse: true,
    autoFocus: true,
  });

  const bento = computeMonitorLayout(
    renderer.terminalWidth,
    renderer.terminalHeight,
    "overview",
    10,
    5,
    10,
  );
  const layout = {
    compactLayout: bento.breakpoint === "compact",
    eventRowCount: bento.events.rowCount,
    heatmapWidth: bento.heatmap.width,
    rosterHeight: bento.roster.height,
    headerHeight: bento.headerHeight,
    statsHeight: bento.statsHeight,
    footerHeight: bento.footerHeight,
    cellWidth: bento.heatmap.cellWidth,
  };

  const scene = createMonitorScene({
    renderer,
    headerHeight: layout.headerHeight,
    statsHeight: layout.statsHeight,
    rosterHeight: layout.rosterHeight,
    footerHeight: layout.footerHeight,
    heatmapWidth: layout.heatmapWidth,
  });

  const ctx: MonitorContext = {
    renderer,
    scene,
    layout: { ...layout },
    ui: {
      displayMode: "overview",
      focusedPanel: "heatmap",
      cursorX: 0,
      cursorY: 0,
      selectedDrone: 0,
      selectedEvent: 0,
    },
    history: {
      coverage: [],
      uncertainty: [],
      auctions: [],
      dropouts: [],
      latency: [],
      drones: {},
    },
    timers: {
      timer: null,
      orphanWatchTimer: null,
      controlStatusTimer: null,
    },
    lastGood: null,
    lastTickLatencyMs: 0,
    lastSuccessfulSnapshotAt: 0,
    spinnerIndex: 0,
    survivorStartedAt: 0,
    controlStatus: "",
    controlRequestId: 0,
    closed: false,
    args,
    timelines: [],
    initialParentPid: process.ppid,
    watchedParentPid: Number(process.env.ENTROPYHUNT_WATCH_PARENT_PID ?? ""),
    sourceLossExitMs: Number(process.env.ENTROPYHUNT_EXIT_ON_SOURCE_LOSS_MS ?? "0"),
    panelBindings: [
      { panel: "heatmap", renderable: scene.heatmapPanel, border: FOCUS_THEME.panels.heatmap.border },
      { panel: "roster", renderable: scene.rosterBox, border: FOCUS_THEME.panels.roster.border },
      { panel: "events", renderable: scene.eventsBox, border: FOCUS_THEME.panels.events.border },
    ],
    requestRender: () => renderer.requestRender(),
    setControlStatus(next: string, clearAfterMs = 0) {
      ctx.controlStatus = next;
      if (ctx.timers.controlStatusTimer) {
        clearTimeout(ctx.timers.controlStatusTimer);
        ctx.timers.controlStatusTimer = null;
      }
      if (clearAfterMs > 0) {
        ctx.timers.controlStatusTimer = setTimeout(() => {
          ctx.controlStatus = "";
          ctx.timers.controlStatusTimer = null;
          ctx.renderLatest();
        }, clearAfterMs);
      }
      ctx.renderLatest();
    },
    renderLatest() {
      if (ctx.lastGood) {
        ctx.updateView(ctx.lastGood);
      } else {
        ctx.requestRender();
      }
    },
    updateView(state: ViewState) {
      if (ctx.closed) return;
      const synced = syncMonitorFrame({
        state,
        rendererWidth: ctx.renderer.terminalWidth,
        rendererHeight: ctx.renderer.terminalHeight,
        compactLayout: ctx.layout.compactLayout,
        eventRowCount: ctx.layout.eventRowCount,
        heatmapWidth: ctx.layout.heatmapWidth,
        rosterHeight: ctx.layout.rosterHeight,
        headerHeight: ctx.layout.headerHeight,
        statsHeight: ctx.layout.statsHeight,
        footerHeight: ctx.layout.footerHeight,
        cellWidth: ctx.layout.cellWidth,
        ui: ctx.ui,
        lastTickLatencyMs: ctx.lastTickLatencyMs,
        survivorStartedAt: ctx.survivorStartedAt,
        history: ctx.history,
        controlStatus: ctx.controlStatus,
        panelBindings: ctx.panelBindings,
        scene: ctx.scene,
        requestRender: ctx.requestRender,
      });
      Object.assign(ctx.layout, synced.layout);
      Object.assign(ctx.ui, synced.ui);
      ctx.layout.cellWidth = synced.cellWidth;
    },
    setWaiting(visible: boolean, sourceUrl: string) {
      if (ctx.closed) return;
      syncWaitingShell({
        visible,
        sourceUrl,
        spinnerFrame: SPINNER_FRAMES[ctx.spinnerIndex]!,
        shell: ctx.scene.shell,
        waitingShell: ctx.scene.waitingShell,
        waitingBody: ctx.scene.waitingBody,
        requestRender: ctx.requestRender,
      });
    },
    applyControlPatch(patch: { tick_seconds?: number; tick_delay_seconds?: number; requested_drone_count?: number }) {
      if (!ctx.lastGood || !ctx.lastGood.sourceUrl.startsWith("http") || !ctx.lastGood.controlUrl) {
        ctx.setControlStatus("control unavailable", 1800);
        return;
      }
      const controlMode = (() => {
        if (patch.tick_seconds != null) return ctx.lastGood.controlCapabilities.tick_seconds;
        if (patch.tick_delay_seconds != null) return ctx.lastGood.controlCapabilities.tick_delay_seconds;
        if (patch.requested_drone_count != null) return ctx.lastGood.controlCapabilities.requested_drone_count;
        return "";
      })();
      if (controlMode !== "live" && controlMode !== "next_run") {
        ctx.setControlStatus("read-only", 1800);
        return;
      }
      const previousState = ctx.lastGood;
      const requestId = ++ctx.controlRequestId;
      ctx.lastGood = {
        ...previousState,
        tickSeconds: patch.tick_seconds ?? ctx.lastGood.tickSeconds,
        tickDelaySeconds: patch.tick_delay_seconds ?? ctx.lastGood.tickDelaySeconds,
        requestedDroneCount: patch.requested_drone_count ?? ctx.lastGood.requestedDroneCount,
      };
      ctx.setControlStatus("sending…");
      (async () => {
        try {
          const payload = await postMonitorControl(previousState.sourceUrl, patch);
          if (requestId !== ctx.controlRequestId) return;
          if (ctx.lastGood) {
            ctx.lastGood = {
              ...ctx.lastGood,
              tickSeconds: Number(payload.tick_seconds ?? ctx.lastGood.tickSeconds),
              tickDelaySeconds: Number(payload.tick_delay_seconds ?? ctx.lastGood.tickDelaySeconds),
              requestedDroneCount: Number(payload.requested_drone_count ?? ctx.lastGood.requestedDroneCount),
            };
          }
          ctx.setControlStatus("applied", 1500);
        } catch (e) {
          process.stderr.write(`[tui-controller] ${e}\n`);
          if (requestId !== ctx.controlRequestId) return;
          ctx.lastGood = previousState;
          ctx.setControlStatus("send failed", 2200);
        }
      })();
    },
    shutdown: () => {},
    handleResize() {
      if (ctx.closed) return;
      ctx.renderLatest();
    },
    isPidAlive(pid: number) {
      try {
        process.kill(pid, 0);
        return true;
      } catch (e) {
        process.stderr.write(`[tui-controller] ${e}\n`);
        return false;
      }
    },
  };

  bindMonitorMouseInteractions({
    panelBindings: ctx.panelBindings,
    viewTabs: scene.viewTabs,
    gridRows: scene.gridRows,
    gridRowMap: scene.gridRowMap,
    modeLines: scene.modeLines,
    droneRows: scene.droneRows,
    eventRows: scene.eventRows,
    getDisplayMode: () => ctx.ui.displayMode,
    setFocusedPanel: (panel) => {
      ctx.ui.focusedPanel = panel;
      ctx.renderLatest();
    },
    setDisplayMode: (mode) => {
      ctx.ui.displayMode = mode;
      ctx.renderLatest();
    },
    setSelectedDrone: (index) => {
      ctx.ui.selectedDrone = index;
    },
    setSelectedEvent: (index) => {
      ctx.ui.selectedEvent = index;
    },
    setHeatmapCursor: (nextCursorX, nextCursorY) => {
      ctx.ui.cursorX = nextCursorX;
      ctx.ui.cursorY = nextCursorY;
    },
    getLastGood: () => ctx.lastGood,
    getCellWidth: () => ctx.layout.cellWidth,
  });

  scene.shell.onKeyDown = (key) => {
    if (!ctx.lastGood) return;
    const result = handleMonitorKeyDown({
      key,
      ui: ctx.ui,
      state: ctx.lastGood,
    });
    if (result.kind === "noop") return;
    key.preventDefault();
    if (result.kind === "shutdown") {
      ctx.shutdown();
      return;
    }
    if (result.kind === "display") {
      ctx.ui.displayMode = result.mode;
      ctx.renderLatest();
      return;
    }
    if (result.kind === "focus") {
      ctx.ui.focusedPanel = result.panel;
      ctx.renderLatest();
      return;
    }
    if (result.kind === "ui") {
      Object.assign(ctx.ui, result.ui);
      ctx.ui.focusedPanel = result.ui.focusedPanel;
      ctx.renderLatest();
      return;
    }
    if (result.kind === "control") {
      ctx.applyControlPatch(result.patch);
      return;
    }
    if (result.kind === "follow-roster") {
      ctx.ui.selectedDrone = result.selectedDrone;
      ctx.ui.focusedPanel = "roster";
      ctx.renderLatest();
      return;
    }
    if (result.kind === "follow-heatmap") {
      ctx.ui.cursorX = result.cursorX;
      ctx.ui.cursorY = result.cursorY;
      ctx.ui.focusedPanel = "heatmap";
      ctx.renderLatest();
    }
  };

  renderer.start();
  attachAnimationEngine(renderer);
  ctx.timelines.push(createTargetPulseTimeline(() => {}));
  ctx.timelines.push(createFooterHeartbeatTimeline(() => {}));
  scene.shell.focus();

  renderer.on("resize", ctx.handleResize);
  ctx.ui.focusedPanel = "heatmap";
  ctx.renderLatest();

  ctx.shutdown = createShutdown(ctx);
  return ctx;
}
