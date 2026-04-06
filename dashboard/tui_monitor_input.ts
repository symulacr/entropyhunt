import {
  advanceDisplayMode,
  advanceUiState,
  type DisplayMode,
  type FocusPanel,
  type MonitorUiState,
  type ViewState,
} from "./tui_monitor_model.ts";

type KeyLike = {
  name?: string;
  sequence?: string;
  raw?: string;
  shift?: boolean;
};

export type MonitorKeyResult =
  | { kind: "noop" }
  | { kind: "shutdown" }
  | { kind: "display"; mode: DisplayMode }
  | { kind: "focus"; panel: FocusPanel }
  | { kind: "ui"; ui: MonitorUiState }
  | { kind: "control"; patch: { tick_seconds?: number; tick_delay_seconds?: number; requested_drone_count?: number } }
  | { kind: "follow-roster"; selectedDrone: number }
  | { kind: "follow-heatmap"; cursorX: number; cursorY: number };

const DISPLAY_MODE_SHORTCUTS = [
  [["m", "3"], "map"],
  [["c", "4"], "config"],
  [["g", "5"], "graphs"],
  [["d", "2"], "detail"],
  [["o", "1"], "overview"],
] as const;

const FOCUS_SHORTCUTS = [
  [["h"], "heatmap"],
  [["r"], "roster"],
  [["e"], "events"],
] as const;

export function matchesKey(key: KeyLike, ...values: string[]): boolean {
  return values.some((value) => key.name === value || key.sequence === value || key.raw === value);
}

export function handleMonitorKeyDown(args: {
  key: KeyLike;
  ui: MonitorUiState;
  state: Pick<ViewState, "gridSize" | "drones" | "events" | "tickSeconds" | "tickDelaySeconds" | "requestedDroneCount" | "droneCount" | "controlCapabilities">;
}): MonitorKeyResult {
  const { key, ui, state } = args;

  if (matchesKey(key, "q", "escape")) return { kind: "shutdown" };
  if (key.name === "tab") return { kind: "display", mode: advanceDisplayMode(ui.displayMode, Boolean(key.shift)) };

  const nextDisplayMode = DISPLAY_MODE_SHORTCUTS.find(([triggers]) => triggers.some((trigger) => matchesKey(key, trigger)))?.[1];
  if (nextDisplayMode) return { kind: "display", mode: nextDisplayMode };

  const nextFocusPanel = FOCUS_SHORTCUTS.find(([triggers]) => triggers.some((trigger) => matchesKey(key, trigger)))?.[1];
  if (nextFocusPanel) return { kind: "focus", panel: nextFocusPanel };

  if ((ui.displayMode === "graphs" || ui.displayMode === "detail") && (key.name === "up" || key.name === "down")) {
    return {
      kind: "ui",
      ui: {
        ...ui,
        selectedDrone: key.name === "up"
          ? Math.max(0, ui.selectedDrone - 1)
          : Math.min(Math.max(0, state.drones.length - 1), ui.selectedDrone + 1),
      },
    };
  }

  if (ui.displayMode === "config") {
    if (key.name === "up" || key.name === "down") {
      return {
        kind: "ui",
        ui: {
          ...ui,
          selectedEvent: key.name === "up" ? Math.max(0, ui.selectedEvent - 1) : Math.min(1, ui.selectedEvent + 1),
        },
      };
    }
    if (key.name === "left" || key.name === "right") {
      const focusSpeed = ui.selectedEvent === 0;
      const faster = key.name === "right";
      const speedPatch = state.controlCapabilities.tick_delay_seconds === "live"
        ? { tick_delay_seconds: Number(Math.max(0, state.tickDelaySeconds + (faster ? -0.05 : 0.05)).toFixed(2)) }
        : state.controlCapabilities.tick_seconds === "live"
          ? { tick_seconds: Number(Math.max(0.05, state.tickSeconds + (faster ? -0.25 : 0.25)).toFixed(2)) }
          : {};
      return {
        kind: "control",
        patch: focusSpeed
          ? speedPatch
          : { requested_drone_count: Math.max(1, state.requestedDroneCount + (faster ? 1 : -1)) },
      };
    }
  }

  if (key.name === "left" || key.name === "right" || key.name === "up" || key.name === "down") {
    return {
      kind: "ui",
      ui: advanceUiState(ui, state, key.name),
    };
  }

  if (ui.displayMode === "config") {
    if (matchesKey(key, "[")) {
      return {
        kind: "control",
        patch: state.controlCapabilities.tick_delay_seconds === "live"
          ? { tick_delay_seconds: Number((state.tickDelaySeconds + 0.05).toFixed(2)) }
          : state.controlCapabilities.tick_seconds === "live"
            ? { tick_seconds: Number((state.tickSeconds + 0.25).toFixed(2)) }
            : {},
      };
    }
    if (matchesKey(key, "]")) {
      return {
        kind: "control",
        patch: state.controlCapabilities.tick_delay_seconds === "live"
          ? { tick_delay_seconds: Number(Math.max(0, state.tickDelaySeconds - 0.05).toFixed(2)) }
          : state.controlCapabilities.tick_seconds === "live"
            ? { tick_seconds: Number(Math.max(0.05, state.tickSeconds - 0.25).toFixed(2)) }
            : {},
      };
    }
    if (matchesKey(key, "-", "_")) {
      return { kind: "control", patch: { requested_drone_count: Math.max(1, state.requestedDroneCount - 1) } };
    }
    if (matchesKey(key, "+", "=")) {
      return { kind: "control", patch: { requested_drone_count: Math.max(1, state.requestedDroneCount + 1) } };
    }
  }

  if (!matchesKey(key, "enter", "return")) return { kind: "noop" };

  if (ui.focusedPanel === "heatmap") {
    const selectedDrone = state.drones.findIndex((drone) => drone.x === ui.cursorX && drone.y === ui.cursorY);
    return selectedDrone >= 0 ? { kind: "follow-roster", selectedDrone } : { kind: "noop" };
  }

  if (ui.focusedPanel === "roster") {
    const drone = state.drones[ui.selectedDrone];
    return drone ? { kind: "follow-heatmap", cursorX: drone.x, cursorY: drone.y } : { kind: "noop" };
  }

  return { kind: "noop" };
}
