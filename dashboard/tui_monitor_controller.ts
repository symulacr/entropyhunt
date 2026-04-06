import { createCliRenderer } from "@opentui/core";

import { FOCUS_THEME } from "./tui_theme.ts";
import {
  type DisplayMode,
  type FocusPanel,
  type ViewState,
  computeLayoutMetrics,
  normalizeSnapshot,
} from "./tui_monitor_model.ts";
import { handleMonitorKeyDown } from "./tui_monitor_input.ts";
import { hasLostControllingParent, hasLostSource, hasLostWatchedParent, showActiveShell, syncWaitingShell } from "./tui_monitor_runtime.ts";
import { bindMonitorMouseInteractions } from "./tui_monitor_interactions.ts";
import { createMonitorScene } from "./tui_monitor_scene.ts";
import { fetchMonitorSnapshot, postMonitorControl, type MonitorArgs } from "./tui_monitor_io.ts";
import { syncMonitorFrame } from "./tui_monitor_sync.ts";
import { type MonitorPanelBinding } from "./tui_monitor_focus.ts";
import type { MonitorHistory } from "./tui_monitor_aux.ts";

const SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

export async function runMonitorController(args: MonitorArgs) {
  const renderer = await createCliRenderer({
    targetFps: 18,
    screenMode: "alternate-screen",
    exitOnCtrlC: true,
    useMouse: true,
    autoFocus: true,
  });

  let { compactLayout, eventRowCount, heatmapWidth, rosterHeight, headerHeight, statsHeight, footerHeight, cellWidth } = computeLayoutMetrics(
    renderer.terminalWidth,
    renderer.terminalHeight,
  );

  const scene = createMonitorScene({ renderer, headerHeight, statsHeight, rosterHeight, footerHeight, heatmapWidth });
  const {
    shell,
    heatmapPanel,
    rosterBox,
    eventsBox,
    viewTabs,
    gridRows,
    gridRowMap,
    droneRows,
    eventRows,
    waitingShell,
    waitingBody,
  } = scene;

  let lastGood: ViewState | null = null;
  let spinnerIndex = 0;
  let survivorStartedAt = 0;
  let displayMode: DisplayMode = "overview";
  let focusedPanel: FocusPanel = "heatmap";
  let cursorX = 0;
  let cursorY = 0;
  let selectedDrone = 0;
  let selectedEvent = 0;
  let lastTickLatencyMs = 0;
  let lastSuccessfulSnapshotAt = 0;
  let controlStatus = "";
  let closed = false;
  let timer: ReturnType<typeof setInterval> | null = null;
  let orphanWatchTimer: ReturnType<typeof setInterval> | null = null;
  let controlStatusTimer: ReturnType<typeof setTimeout> | null = null;
  let controlRequestId = 0;
  let shutdown = () => {};
  const requestRender = () => renderer.requestRender();
  const setControlStatus = (next: string, clearAfterMs = 0) => {
    controlStatus = next;
    if (controlStatusTimer) {
      clearTimeout(controlStatusTimer);
      controlStatusTimer = null;
    }
    if (clearAfterMs > 0) {
      controlStatusTimer = setTimeout(() => {
        controlStatus = "";
        controlStatusTimer = null;
        renderLatest();
      }, clearAfterMs);
    }
    renderLatest();
  };
  const controlModeForPatch = (state: ViewState, patch: { tick_seconds?: number; tick_delay_seconds?: number; requested_drone_count?: number }) => {
    if (patch.tick_seconds != null) return state.controlCapabilities.tick_seconds;
    if (patch.tick_delay_seconds != null) return state.controlCapabilities.tick_delay_seconds;
    if (patch.requested_drone_count != null) return state.controlCapabilities.requested_drone_count;
    return "";
  };
  const applyControlPatch = (patch: { tick_seconds?: number; tick_delay_seconds?: number; requested_drone_count?: number }) => {
    if (!lastGood || !lastGood.sourceUrl.startsWith("http") || !lastGood.controlUrl) {
      setControlStatus("control unavailable", 1800);
      return;
    }
    const controlMode = controlModeForPatch(lastGood, patch);
    if (controlMode !== "live" && controlMode !== "next_run") {
      setControlStatus("read-only", 1800);
      return;
    }
    const previousState = lastGood;
    const requestId = ++controlRequestId;
    lastGood = {
      ...previousState,
      tickSeconds: patch.tick_seconds ?? lastGood.tickSeconds,
      tickDelaySeconds: patch.tick_delay_seconds ?? lastGood.tickDelaySeconds,
      requestedDroneCount: patch.requested_drone_count ?? lastGood.requestedDroneCount,
    };
    setControlStatus("sending…");
    void postMonitorControl(previousState.sourceUrl, patch)
      .then((payload) => {
        if (requestId !== controlRequestId) return;
        if (lastGood) {
          lastGood = {
            ...lastGood,
            tickSeconds: Number(payload.tick_seconds ?? lastGood.tickSeconds),
            tickDelaySeconds: Number(payload.tick_delay_seconds ?? lastGood.tickDelaySeconds),
            requestedDroneCount: Number(payload.requested_drone_count ?? lastGood.requestedDroneCount),
          };
        }
        setControlStatus("applied", 1500);
      })
      .catch(() => {
        if (requestId !== controlRequestId) return;
        lastGood = previousState;
        setControlStatus("send failed", 2200);
      });
  };
  const history: MonitorHistory = {
    coverage: [],
    uncertainty: [],
    auctions: [],
    dropouts: [],
    latency: [],
    drones: {},
  };

  const panelBindings: MonitorPanelBinding[] = [
    { panel: "heatmap", renderable: heatmapPanel, border: FOCUS_THEME.panels.heatmap.border },
    { panel: "roster", renderable: rosterBox, border: FOCUS_THEME.panels.roster.border },
    { panel: "events", renderable: eventsBox, border: FOCUS_THEME.panels.events.border },
  ];

  const renderLatest = () => {
    if (lastGood) {
      updateView(lastGood);
    } else {
      requestRender();
    }
  };

  const setFocusedPanel = (panel: FocusPanel) => {
    focusedPanel = panel;
    renderLatest();
  };

  const setDisplayMode = (mode: DisplayMode) => {
    displayMode = mode;
    renderLatest();
  };

  bindMonitorMouseInteractions({
    panelBindings,
    viewTabs,
    gridRows,
    gridRowMap,
    modeLines: scene.modeLines,
    droneRows,
    eventRows,
    getDisplayMode: () => displayMode,
    setFocusedPanel,
    setDisplayMode,
    setSelectedDrone: (index) => {
      selectedDrone = index;
    },
    setSelectedEvent: (index) => {
      selectedEvent = index;
    },
    setHeatmapCursor: (nextCursorX, nextCursorY) => {
      cursorX = nextCursorX;
      cursorY = nextCursorY;
    },
    getLastGood: () => lastGood,
    getCellWidth: () => cellWidth,
  });

  shell.onKeyDown = (key) => {
    if (!lastGood) return;
    const result = handleMonitorKeyDown({
      key,
      ui: { displayMode, focusedPanel, cursorX, cursorY, selectedDrone, selectedEvent },
      state: lastGood,
    });
    if (result.kind === "noop") return;
    key.preventDefault();
    if (result.kind === "shutdown") {
      shutdown();
      return;
    }
    if (result.kind === "display") {
      setDisplayMode(result.mode);
      return;
    }
    if (result.kind === "focus") {
      setFocusedPanel(result.panel);
      return;
    }
    if (result.kind === "ui") {
      ({ displayMode, focusedPanel, cursorX, cursorY, selectedDrone, selectedEvent } = result.ui);
      setFocusedPanel(focusedPanel);
      return;
    }
    if (result.kind === "control") {
      applyControlPatch(result.patch);
      return;
    }
    if (result.kind === "follow-roster") {
      selectedDrone = result.selectedDrone;
      setFocusedPanel("roster");
      return;
    }
    if (result.kind === "follow-heatmap") {
      cursorX = result.cursorX;
      cursorY = result.cursorY;
      setFocusedPanel("heatmap");
    }
  };

  const setWaiting = (visible: boolean, sourceUrl: string) => {
    if (closed) return;
    syncWaitingShell({
      visible,
      sourceUrl,
      spinnerFrame: SPINNER_FRAMES[spinnerIndex]!,
      shell,
      waitingShell,
      waitingBody,
      requestRender,
    });
  };

  const updateView = (state: ViewState) => {
    if (closed) return;
    const synced = syncMonitorFrame({
      state,
      rendererWidth: renderer.terminalWidth,
      rendererHeight: renderer.terminalHeight,
      compactLayout,
      eventRowCount,
      heatmapWidth,
      rosterHeight,
      headerHeight,
      statsHeight,
      footerHeight,
      cellWidth,
      ui: { displayMode, focusedPanel, cursorX, cursorY, selectedDrone, selectedEvent },
      lastTickLatencyMs,
      survivorStartedAt,
      history,
      controlStatus,
      panelBindings,
      scene,
      requestRender,
    });
    ({ compactLayout, eventRowCount, heatmapWidth, rosterHeight, headerHeight, statsHeight, footerHeight } = synced.layout);
    ({ displayMode, focusedPanel, cursorX, cursorY, selectedDrone, selectedEvent } = synced.ui);
    cellWidth = synced.cellWidth;
  };

  const tick = async () => {
    if (closed) return;
    const startedAt = performance.now();
    try {
      const snapshot = await fetchMonitorSnapshot(args.source);
      const state = normalizeSnapshot(snapshot, args.source, false);
      lastTickLatencyMs = performance.now() - startedAt;
      lastSuccessfulSnapshotAt = Date.now();
      if (state.survivorFound && survivorStartedAt === 0) survivorStartedAt = Date.now();
      history.coverage = [...history.coverage, state.coverage].slice(-24);
      history.uncertainty = [...history.uncertainty, state.avgEntropy].slice(-24);
      history.auctions = [...history.auctions, state.auctions].slice(-24);
      history.dropouts = [...history.dropouts, state.dropouts].slice(-24);
      history.latency = [...history.latency, Math.max(0, Math.round(lastTickLatencyMs))].slice(-24);
      for (const drone of state.drones) {
        const existing = history.drones[drone.id] ?? { entropy: [], searched: [] };
        history.drones[drone.id] = {
          entropy: [...existing.entropy, drone.entropy].slice(-24),
          searched: [...existing.searched, drone.searchedCells].slice(-24),
        };
      }
      lastGood = state;
      setWaiting(false, args.source);
      updateView(state);
    } catch {
      spinnerIndex = (spinnerIndex + 1) % SPINNER_FRAMES.length;
      if (lastGood) {
        updateView({ ...lastGood, staleData: true });
        showActiveShell({ shell, waitingShell, requestRender });
      } else {
        setWaiting(true, args.source);
      }
    }
  };

  renderer.start();
  shell.focus();
  const initialParentPid = process.ppid;
  const watchedParentPid = Number(process.env.ENTROPYHUNT_WATCH_PARENT_PID ?? "");
  const sourceLossExitMs = Number(process.env.ENTROPYHUNT_EXIT_ON_SOURCE_LOSS_MS ?? "0");
  const isPidAlive = (pid: number) => {
    try {
      process.kill(pid, 0);
      return true;
    } catch {
      return false;
    }
  };
  const handleResize = () => {
    if (closed) return;
    renderLatest();
  };
  renderer.on("resize", handleResize);
  setFocusedPanel("heatmap");
  await tick();

  timer = setInterval(() => {
    void tick();
  }, args.intervalMs);
  orphanWatchTimer = setInterval(() => {
    if (closed) return;
    if (hasLostWatchedParent(Number.isFinite(watchedParentPid) ? watchedParentPid : null, isPidAlive)
      || hasLostControllingParent(initialParentPid, process.ppid)
      || hasLostSource(lastSuccessfulSnapshotAt, Date.now(), sourceLossExitMs)) {
      shutdown();
    }
  }, 1000);

  shutdown = () => {
    if (closed) return;
    closed = true;
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
    if (orphanWatchTimer) {
      clearInterval(orphanWatchTimer);
      orphanWatchTimer = null;
    }
    if (controlStatusTimer) {
      clearTimeout(controlStatusTimer);
      controlStatusTimer = null;
    }
    renderer.off("resize", handleResize);
    process.off("SIGTERM", shutdown);
    process.off("SIGINT", shutdown);
    renderer.destroy();
  };

  process.on("SIGTERM", shutdown);
  process.on("SIGINT", shutdown);
}
