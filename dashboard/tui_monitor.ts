import {
  type DisplayMode,
  type FocusPanel,
  type MonitorUiState,
  type ViewState,
  advanceDisplayMode,
  advanceUiState,
  hitTestHeatmapCell,
  logicalHeatmapRowForRenderIndex,
  normalizeSnapshot,
} from "./tui_monitor_model.ts";
import { runMonitorController } from "./tui_monitor_controller.ts";
import { parseMonitorArgs } from "./tui_monitor_io.ts";

export {
  advanceDisplayMode,
  advanceUiState,
  hitTestHeatmapCell,
  logicalHeatmapRowForRenderIndex,
  normalizeSnapshot,
};
export type {
  DisplayMode,
  FocusPanel,
  MonitorUiState,
  ViewState,
};

export async function main() {
  await runMonitorController(parseMonitorArgs(process.argv.slice(2)));
}

if (import.meta.main) {
  await main();
}
