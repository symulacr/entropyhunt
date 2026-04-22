import { StyledText, bg as withBg, bold as withBold, dim as withDim, fg as withFg, t, type TextChunk, type TextRenderable } from "@opentui/core";

import { speedControlCapability, type DisplayMode, type ViewState } from "./tui_monitor_model.ts";
import { COLORS, PANEL_THEME } from "./tui_theme.ts";
import {
  renderBatteryPanel,
  renderConsensusPanel,
  renderFailurePanel,
  renderMeshTopology,
} from "./tui_monitor_panels.ts";
import { renderChartDashboard } from "./tui_monitor_charts.ts";

export type MonitorHistory = {
  coverage: number[];
  uncertainty: number[];
  auctions: number[];
  dropouts: number[];
  latency: number[];
  drones: Record<string, { entropy: number[]; searched: number[] }>;
};

function controlModeLabel(mode: string | undefined): string {
  if (mode === "live") return "live";
  if (mode === "next_run") return "next run";
  return "read-only";
}

function speedWidgetValue(state: ViewState): string {
  if (state.controlCapabilities.tick_delay_seconds === "live") {
    return `tick ${state.tickSeconds}s · delay ${state.tickDelaySeconds.toFixed(2)}s`;
  }
  if (state.controlCapabilities.tick_seconds === "live") {
    return `tick ${state.tickSeconds.toFixed(2)}s per step`;
  }
  return "speed unavailable in this runtime";
}

const SPARK = "▁▂▃▄▅▆▇█";

function clampInt(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, Math.floor(value)));
}

function joinStyledTexts(texts: StyledText[]): StyledText {
  const chunks: TextChunk[] = [];
  const newlineChunks = t`
`.chunks;
  for (let i = 0; i < texts.length; i++) {
    if (i > 0) chunks.push(...newlineChunks);
    chunks.push(...texts[i].chunks);
  }
  return new StyledText(chunks);
}

function truncateText(value: string, maxWidth: number): string {
  if (maxWidth <= 1) return value.slice(0, Math.max(0, maxWidth));
  if (value.length <= maxWidth) return value;
  return `${value.slice(0, Math.max(0, maxWidth - 1))}…`;
}

function sparkline(values: number[], max = Math.max(1, ...values, 1), width = values.length): string {
  if (!values.length) return "—";
  const points = Array.from({ length: Math.max(1, width) }, (_, index) => {
    if (width <= 1 || values.length <= 1) return values.at(-1) ?? values[0] ?? 0;
    const position = (index * (values.length - 1)) / (width - 1);
    const left = Math.floor(position);
    const right = Math.min(values.length - 1, Math.ceil(position));
    const blend = position - left;
    const leftValue = values[left] ?? 0;
    const rightValue = values[right] ?? leftValue;
    return leftValue + (rightValue - leftValue) * blend;
  });
  return points
    .map((value) => {
      const index = Math.max(0, Math.min(SPARK.length - 1, Math.round((value / max) * (SPARK.length - 1))));
      return SPARK[index]!;
    })
    .join("");
}

function trendGlyph(values: number[]): string {
  if (values.length < 2) return "→";
  const previous = values.at(-2) ?? values.at(-1) ?? 0;
  const current = values.at(-1) ?? 0;
  if (current > previous) return "↑";
  if (current < previous) return "↓";
  return "→";
}

function plainLine(label: string, value: string, availableWidth: number) {
  const prefix = `${label.padEnd(10)} `;
  const bodyWidth = Math.max(8, availableWidth - prefix.length);
  return t`${withFg(PANEL_THEME.textMuted)(prefix)}${withFg(PANEL_THEME.textPrimary)(truncateText(value, bodyWidth))}`;
}

function hintLine(text: string) {
  return t`${withFg(PANEL_THEME.textMuted)(withDim(text))}`;
}

function sectionLine(title: string) {
  return t`${withFg(PANEL_THEME.textMuted)(withDim(`${title.toUpperCase()}`))}`;
}

function configFieldLine(label: string, value: string, selected: boolean, availableWidth: number) {
  const prefix = `${label.padEnd(10)} `;
  const bodyWidth = Math.max(8, availableWidth - prefix.length);
  const body = truncateText(value, bodyWidth);
  if (selected) {
    return t`${withFg(COLORS.accent)(withBold(prefix))}${withFg(PANEL_THEME.textPrimary)(withBold(body))}`;
  }
  return t`${withFg(PANEL_THEME.textMuted)(prefix)}${withFg(PANEL_THEME.textPrimary)(body)}`;
}

function graphTitleLine(label: string, suffix: string, color: string) {
  return t`${withFg(color)(withBold("●"))} ${withFg(PANEL_THEME.textMuted)(label.padEnd(11))} ${withFg(PANEL_THEME.textMuted)("[")} ${withFg(PANEL_THEME.textPrimary)(withBold(suffix))} ${withFg(PANEL_THEME.textMuted)("]")}`;
}

function graphSparkLine(values: number[], max: number, color: string, width: number) {
  return t`${withFg(PANEL_THEME.textMuted)("  trend")} ${withFg(color)(withBold(sparkline(values, max, width)))} ${withFg(PANEL_THEME.textSecondary)(trendGlyph(values))}`;
}

function graphHeaderText(label: string, suffix: string): string {
  return `● ${label.padEnd(11)} [ ${suffix} ]`;
}

function graphTrendText(values: number[], max: number, width: number): string {
  return `trend ${sparkline(values, max, width)} ${trendGlyph(values)}`;
}

function miniBar(value: number, max: number, width: number): string {
  const safeMax = Math.max(max, 1);
  const filled = clampInt((value / safeMax) * width, 0, width);
  return `${"█".repeat(filled)}${"·".repeat(Math.max(0, width - filled))}`;
}

function droneStatsLine(drone: ViewState["drones"][number], maxSearchedCells: number, availableWidth: number): string {
  const id = drone.id.replace(/^drone_/, "d");
  const scanWidth = clampInt((availableWidth - 36) / 2, 6, 14);
  const entropyWidth = clampInt((availableWidth - 36) / 2, 6, 14);
  const scanBar = miniBar(drone.searchedCells, maxSearchedCells, scanWidth);
  const entropyBar = miniBar(drone.entropy, 1, entropyWidth);
  return truncateText(
    `${id} scan ${scanBar} ${drone.searchedCells}  H ${entropyBar} ${drone.entropy.toFixed(2)}  ${drone.status}`,
    availableWidth,
  );
}

function droneHistoryLine(label: string, values: number[], max: number, availableWidth: number): string {
  const prefix = `${label.padEnd(8)} `;
  const sparkWidth = clampInt(availableWidth - prefix.length - 4, 10, 28);
  return `${prefix}${sparkline(values, max, sparkWidth)} ${trendGlyph(values)}`;
}

function droneSummary(drone: ViewState["drones"][number], selected: boolean, maxSearchedCells: number, availableWidth: number): string {
  const id = drone.id.replace(/^drone_/, "d");
  const scanWidth = clampInt((availableWidth - 18) / 2, 4, 10);
  const entropyWidth = clampInt((availableWidth - 18) / 2, 4, 10);
  const scanBar = miniBar(drone.searchedCells, maxSearchedCells, scanWidth);
  const entropyBar = miniBar(drone.entropy, 1, entropyWidth);
  return `${selected ? "▶" : "·"} ${id} S${scanBar} H${entropyBar} ${drone.status}`;
}

function droneHistorySummary(
  drone: ViewState["drones"][number],
  selected: boolean,
  history: { entropy: number[]; searched: number[] },
  maxSearchedCells: number,
  availableWidth: number,
): string {
  const id = drone.id.replace(/^drone_/, "d");
  const scanSpark = sparkline(history.searched, maxSearchedCells, 8);
  const entropySpark = sparkline(history.entropy, 1, 8);
  return truncateText(
    `${selected ? "▶" : "·"} ${id} scan ${scanSpark} ${drone.searchedCells} · H ${entropySpark} ${drone.entropy.toFixed(2)} · ${drone.status}`,
    availableWidth,
  );
}

function pairColumns(
  left: string,
  right: string,
  availableWidth: number,
  leftColor: string = PANEL_THEME.textPrimary,
  rightColor: string = PANEL_THEME.textPrimary,
) {
  const gap = "   ";
  const columnWidth = clampInt((availableWidth - gap.length) / 2, 18, 44);
  return t`${withFg(leftColor)(truncateText(left, columnWidth).padEnd(columnWidth, " "))}${withFg(PANEL_THEME.textMuted)(gap)}${withFg(rightColor)(truncateText(right, columnWidth).padEnd(columnWidth, " "))}`;
}

export function syncMonitorAuxPanel(args: {
  displayMode: DisplayMode;
  state: ViewState;
  history: MonitorHistory;
  modeLines: TextRenderable[];
  availableWidth: number;
  selectedDrone: number;
  selectedIndex?: number;
}) {
  const { displayMode, state, history, modeLines, availableWidth, selectedDrone, selectedIndex = 0 } = args;
  const speedMode = controlModeLabel(speedControlCapability(state.controlCapabilities));
  const countMode = controlModeLabel(state.controlCapabilities.requested_drone_count);
  const maxSearchedCells = Math.max(1, ...state.drones.map((drone) => drone.searchedCells));
  const focusedDrone = state.drones[Math.max(0, Math.min(selectedDrone, Math.max(0, state.drones.length - 1)))] ?? null;
  const focusedHistory = focusedDrone ? history.drones[focusedDrone.id] ?? { entropy: [], searched: [] } : { entropy: [], searched: [] };
  const lines = displayMode === "detail"
    ? [
        joinStyledTexts([
          renderMeshTopology(state.meshPeers ?? [], availableWidth),
          renderBatteryPanel(state.batteryLevels ?? {}, availableWidth),
          renderConsensusPanel(state.consensusRounds ?? 0, availableWidth),
          renderFailurePanel(state.failureEvents ?? [], availableWidth),
        ]),
      ]
    : displayMode === "config"
    ? [
        sectionLine("runtime"),
        plainLine("source", `${state.sourceLabel} · ${state.sourceUrl}`, availableWidth),
        plainLine("mesh", `${state.meshMode} · target [${state.target.x},${state.target.y}]`, availableWidth),
        plainLine("grid", `${state.gridSize}x${state.gridSize} · ${state.droneCount} drones`, availableWidth),
        plainLine("scope", `speed ${speedMode} · count ${countMode}`, availableWidth),
        "",
        sectionLine("settings"),
        configFieldLine("speed", speedWidgetValue(state), selectedIndex === 0, availableWidth),
        configFieldLine("next run", `drones ${state.requestedDroneCount} on next launch`, selectedIndex === 1, availableWidth),
        "",
        plainLine("apply", state.controlUrl ? `speed ${speedMode} + count ${countMode}` : "read-only (no backend control)", availableWidth),
        hintLine("↑ / ↓ choose field · ← / → adjust"),
        hintLine("[ / ] speed · - / + next-run count"),
        plainLine("note", "restart needed for drone-count change", availableWidth),
        plainLine("control", state.controlUrl || "no control endpoint", availableWidth),
      ]
    : [
        renderChartDashboard(history, availableWidth, modeLines.length),
      ];

  for (let index = 0; index < modeLines.length; index += 1) {
    modeLines[index]!.content = lines[index] ?? "";
  }
}
