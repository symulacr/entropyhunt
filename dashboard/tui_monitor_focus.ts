import type { BoxRenderable } from "@opentui/core";

import type { FocusPanel, MonitorUiState, ViewState } from "./tui_monitor_model.ts";
import { COLORS } from "./tui_theme.ts";
import { clamp } from "./tui_monitor_util.ts";

export type MonitorPanelBinding = {
  panel: FocusPanel;
  renderable: BoxRenderable;
  border: string;
};

export function clampMonitorFocus(ui: MonitorUiState, state: ViewState): MonitorUiState {
  return {
    ...ui,
    cursorX: clamp(ui.cursorX, 0, Math.max(0, state.gridSize - 1)),
    cursorY: clamp(ui.cursorY, 0, Math.max(0, state.gridSize - 1)),
    selectedDrone: clamp(ui.selectedDrone, 0, Math.max(0, state.drones.length - 1)),
    selectedEvent: clamp(ui.selectedEvent, 0, Math.max(0, state.events.length - 1)),
  };
}

export function syncFocusedPanel(args: {
  focusedPanel: FocusPanel;
  panelBindings: MonitorPanelBinding[];
  requestRender?: () => void;
}) {
  const { focusedPanel, panelBindings, requestRender } = args;
  for (const binding of panelBindings) {
    binding.renderable.borderColor = focusedPanel === binding.panel ? binding.border : COLORS.border;
  }
  requestRender?.();
}
