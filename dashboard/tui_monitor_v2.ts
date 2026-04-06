import {
  type DisplayMode,
  type FocusPanel,
  type LayoutMetrics,
  type MonitorUiState,
  type ViewState,
  advanceDisplayMode,
  advanceUiState,
  computeLayoutMetrics,
  hitTestHeatmapCell,
  logicalHeatmapRowForRenderIndex,
} from "./tui_monitor_model.ts";
import { parseMonitorArgs } from "./tui_monitor_io.ts";
import { runMonitorController } from "./tui_monitor_controller.ts";

export {
  advanceDisplayMode,
  advanceUiState,
  computeLayoutMetrics,
  hitTestHeatmapCell,
  logicalHeatmapRowForRenderIndex,
};
export type {
  DisplayMode,
  FocusPanel,
  LayoutMetrics,
  MonitorUiState,
  ViewState,
};

export async function main() {
  await runMonitorController(parseMonitorArgs(process.argv.slice(2)));
}

if (import.meta.main) {
  await main();
}
