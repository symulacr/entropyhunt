import type { TextRenderable } from "@opentui/core";

import { speedControlCapability, type DisplayMode, type FocusPanel, type ViewState } from "./tui_monitor_model.ts";
import {
  buildCompactSubheaderLine,
  buildCompactHeaderLine,
  buildDisplayModeChip,
  buildFocusStatusLine,
  buildHeaderLine,
  buildSubheaderLine,
} from "./tui_monitor_presenters.ts";
import type { MonitorViewTab } from "./tui_monitor_renderables.ts";

export function syncMonitorHeader(args: {
  state: ViewState;
  compactLayout: boolean;
  displayMode: DisplayMode;
  headerLine: TextRenderable;
  subheaderLine: TextRenderable;
  viewTabs: MonitorViewTab[];
}) {
  const { state, compactLayout, displayMode, headerLine, subheaderLine, viewTabs } = args;
  headerLine.content = compactLayout ? buildCompactHeaderLine(state) : buildHeaderLine(state);
  subheaderLine.content = compactLayout ? buildCompactSubheaderLine(state) : buildSubheaderLine(state);
  if (displayMode === "map") {
    subheaderLine.content = compactLayout
      ? buildCompactSubheaderLine(state)
      : buildCompactSubheaderLine(state);
  }
  for (const tab of viewTabs) {
    tab.renderable.content = displayMode === "map" && tab.mode !== "map"
      ? ""
      : buildDisplayModeChip(tab.mode, displayMode === tab.mode, compactLayout);
  }
}

export function buildMonitorFooterMessage(args: {
  state: ViewState;
  compactLayout: boolean;
  displayMode: DisplayMode;
  controlStatus?: string;
  focusedPanel: FocusPanel;
  cursorX: number;
  cursorY: number;
  selectedDrone: number;
  selectedEvent: number;
  tickLatencyMs: number;
}) {
  const { state, compactLayout, displayMode, controlStatus = "", focusedPanel, cursorX, cursorY, selectedDrone, selectedEvent, tickLatencyMs } = args;
  if (displayMode === "config") {
    const configFocus = selectedEvent === 0 ? "speed" : "next-run drone count";
    const capability = selectedEvent === 0
      ? speedControlCapability(state.controlCapabilities)
      : state.controlCapabilities.requested_drone_count;
    const modeLabel = capability === "live" ? "config live" : capability === "next_run" ? "config next run" : "config read-only";
    return `${modeLabel} · editing ${configFocus} · ${controlStatus || "ready"} · ←/→ adjust`;
  }
  if (displayMode === "graphs") {
    const focusedDrone = state.drones[Math.max(0, Math.min(selectedDrone, Math.max(0, state.drones.length - 1)))];
    return `graphs live history · ${focusedDrone ? focusedDrone.id : "no drone"} selected · ↑/↓ agents · rt=${Math.max(0, Math.round(tickLatencyMs))}ms`;
  }
  if (displayMode === "detail") {
    const focusedDrone = state.drones[Math.max(0, Math.min(selectedDrone, Math.max(0, state.drones.length - 1)))];
    return `drone detail · ${focusedDrone ? focusedDrone.id : "no drone"} selected · ↑/↓ agents · rt=${Math.max(0, Math.round(tickLatencyMs))}ms`;
  }
  const statusMessage = compactLayout
    ? state.survivorFound
      ? "survivor confirmed"
      : state.staleData
        ? "stale snapshot"
        : `mesh ${state.meshMode} healthy`
    : state.survivorFound
      ? "survivor confirmed — hold the grid and coordinate response"
      : state.staleData
        ? "stale snapshot — showing last good state"
        : state.meshMode === "real"
            ? "vertex p2p mesh active — watch the alert timeline for changes"
            : "local mesh active — watch the alert timeline for changes";

  const focusMessage = buildFocusStatusLine(state, focusedPanel, cursorX, cursorY, selectedDrone, selectedEvent, tickLatencyMs, compactLayout)
    .chunks
    .map((chunk) => chunk.text)
    .join("");

  return `${statusMessage} · ${focusMessage}`;
}
