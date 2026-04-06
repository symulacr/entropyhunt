import { bg as withBg, bold as withBold, dim as withDim, fg as withFg, t, type TextRenderable } from "@opentui/core";

import { speedControlCapability, type DisplayMode, type ViewState } from "./tui_monitor_model.ts";
import { COLORS, PANEL_THEME } from "./tui_theme.ts";

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

function widgetInnerWidth(availableWidth: number): number {
  return clampInt(availableWidth - 28, 44, 64);
}

function graphSparkWidth(availableWidth: number): number {
  return clampInt(availableWidth - 42, 20, 40);
}

function graphColumnWidth(availableWidth: number): number {
  return clampInt((availableWidth - 24) / 2, 24, 48);
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
  const prefix = `${label.padEnd(8)} `;
  const bodyWidth = Math.max(8, availableWidth - prefix.length);
  return t`${withFg(PANEL_THEME.textMuted)(prefix)}${withFg(PANEL_THEME.textPrimary)(truncateText(value, bodyWidth))}`;
}

function hintLine(text: string) {
  return t`${withFg(PANEL_THEME.textMuted)(withDim(text))}`;
}

function sectionLine(title: string) {
  return t`${withFg(PANEL_THEME.textMuted)(withDim(`[ ${title.toUpperCase()} ]`))}`;
}

function widgetTop(label: string, selected: boolean, innerWidth: number) {
  const prefix = selected ? "┌▶ " : "┌─ ";
  const title = `${label.toUpperCase()} `;
  const ruleWidth = Math.max(0, innerWidth - title.length);
  return t`${withFg(selected ? COLORS.info : PANEL_THEME.textMuted)(`${prefix}${title}${"─".repeat(ruleWidth)}┐`)}`;
}

function widgetBody(value: string, selected: boolean, innerWidth: number) {
  const content = `${selected ? "> " : "  "}${value}`.slice(0, innerWidth).padEnd(innerWidth, " ");
  return selected
    ? t`${withFg(COLORS.info)(withBold("│"))}${withFg("#f8fafc")(withBold(content))}${withFg(COLORS.info)(withBold("│"))}`
    : t`${withFg(PANEL_THEME.textMuted)("│")}${withFg(PANEL_THEME.textPrimary)(content)}${withFg(PANEL_THEME.textMuted)("│")}`;
}

function widgetBottom(selected: boolean, innerWidth: number) {
  return t`${withFg(selected ? COLORS.info : PANEL_THEME.textMuted)(`└${"─".repeat(innerWidth)}┘`)}`;
}

function graphTitleLine(label: string, suffix: string, color: string) {
  return t`${withFg(color)(withBold("●"))} ${withFg(PANEL_THEME.textMuted)(label.padEnd(11))} ${withFg(PANEL_THEME.textMuted)("[")} ${withFg("#f8fafc")(withBold(suffix))} ${withFg(PANEL_THEME.textMuted)("]")}`;
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

function tileTop(label: string, suffix: string, width: number): string {
  const title = ` ${label} [${suffix}] `;
  return `┌${title}${"─".repeat(Math.max(0, width - title.length - 2))}┐`;
}

function tileBody(text: string, width: number): string {
  return `│${truncateText(text, Math.max(0, width - 2)).padEnd(Math.max(0, width - 2), " ")}│`;
}

function tileBottom(width: number): string {
  return `└${"─".repeat(Math.max(0, width - 2))}┘`;
}

function pairTiles(
  leftTitle: string,
  leftValue: string,
  leftTrend: string,
  rightTitle: string,
  rightValue: string,
  rightTrend: string,
  availableWidth: number,
  leftColor: string,
  rightColor: string,
) {
  const width = graphColumnWidth(availableWidth);
  return [
    pairColumns(tileTop(leftTitle, leftValue, width), tileTop(rightTitle, rightValue, width), availableWidth, leftColor, rightColor),
    pairColumns(tileBody(leftTrend, width), tileBody(rightTrend, width), availableWidth, leftColor, rightColor),
    pairColumns(tileBottom(width), tileBottom(width), availableWidth, leftColor, rightColor),
  ];
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
  const innerWidth = widgetInnerWidth(availableWidth);
  const sparkWidth = graphSparkWidth(availableWidth);
  const maxSearchedCells = Math.max(1, ...state.drones.map((drone) => drone.searchedCells));
  const focusedDrone = state.drones[Math.max(0, Math.min(selectedDrone, Math.max(0, state.drones.length - 1)))] ?? null;
  const focusedHistory = focusedDrone ? history.drones[focusedDrone.id] ?? { entropy: [], searched: [] } : { entropy: [], searched: [] };
  const lines = displayMode === "detail"
    ? [
        sectionLine("drone detail"),
        plainLine(
          "focus",
          focusedDrone
            ? `${focusedDrone.id} · ${focusedDrone.status} · ${focusedDrone.offline ? "offline" : "online"}`
            : "no active drone",
          availableWidth,
        ),
        plainLine(
          "route",
          focusedDrone
            ? `[${focusedDrone.x},${focusedDrone.y}] → ${focusedDrone.tx == null || focusedDrone.ty == null ? "--" : `[${focusedDrone.tx},${focusedDrone.ty}]`}`
            : "--",
          availableWidth,
        ),
        ...pairTiles(
          "scan",
          `${focusedDrone?.searchedCells ?? 0}`,
          graphTrendText(focusedHistory.searched, maxSearchedCells, Math.max(10, Math.floor(sparkWidth / 2))),
          "entropy",
          focusedDrone ? focusedDrone.entropy.toFixed(2) : "0.00",
          graphTrendText(focusedHistory.entropy, 1, Math.max(10, Math.floor(sparkWidth / 2))),
          availableWidth,
          COLORS.info,
          COLORS.warning,
        ),
        ...pairTiles(
          "position",
          focusedDrone ? `[${focusedDrone.x},${focusedDrone.y}]` : "--",
          focusedDrone ? `target ${focusedDrone.tx == null || focusedDrone.ty == null ? "--" : `[${focusedDrone.tx},${focusedDrone.ty}]`}` : "--",
          "status",
          focusedDrone?.status ?? "--",
          focusedDrone?.offline ? "link lost" : "tracking live updates",
          availableWidth,
          PANEL_THEME.textPrimary,
          PANEL_THEME.textPrimary,
        ),
        sectionLine("swarm"),
        ...state.drones.slice(0, 3).map((drone, index) =>
          plainLine(
            "agent",
            droneHistorySummary(drone, selectedDrone === index, history.drones[drone.id] ?? { entropy: [], searched: [] }, maxSearchedCells, availableWidth - 10),
            availableWidth,
          )),
        pairColumns(
          `target   [${state.target.x},${state.target.y}]`,
          `request  ${state.requestedDroneCount} next launch`,
          availableWidth,
        ),
      ]
    : displayMode === "config"
    ? [
        ...pairTiles(
          "source",
          state.sourceLabel,
          state.sourceUrl,
          "mesh",
          state.meshMode,
          `target [${state.target.x},${state.target.y}]`,
          availableWidth,
          COLORS.info,
          PANEL_THEME.textPrimary,
        ),
        ...pairTiles(
          "grid",
          `${state.gridSize}x${state.gridSize}`,
          `drones ${state.droneCount} live`,
          "scope",
          `${speedMode}/${countMode}`,
          `speed ${speedMode} · count ${countMode}`,
          availableWidth,
          COLORS.success,
          COLORS.warning,
        ),
        widgetTop("speed", selectedIndex === 0, innerWidth),
        widgetBody(speedWidgetValue(state), selectedIndex === 0, innerWidth),
        widgetBottom(selectedIndex === 0, innerWidth),
        widgetTop("next run", selectedIndex === 1, innerWidth),
        widgetBody(`drones ${state.requestedDroneCount} on next launch`, selectedIndex === 1, innerWidth),
        widgetBottom(selectedIndex === 1, innerWidth),
        plainLine("apply", state.controlUrl ? `speed ${speedMode} + count ${countMode}` : "read-only (no backend control)", availableWidth),
        hintLine("↑ / ↓ choose field · ← / → adjust"),
        hintLine("[ / ] speed · - / + next-run count"),
        plainLine("note", "restart needed for drone-count change", availableWidth),
        plainLine("control", state.controlUrl || "no control endpoint", availableWidth),
      ]
    : [
        plainLine("state", state.survivorFound ? "survivor confirmed" : "search in progress", availableWidth),
        hintLine("y↑ coverage/entropy/latency · x→ oldest to newest (24 samples)"),
        ...pairTiles(
          "coverage",
          `${Math.round(state.coverage)}%`,
          graphTrendText(history.coverage, 100, Math.max(10, Math.floor(sparkWidth / 2))),
          "uncertainty",
          state.avgEntropy.toFixed(2),
          graphTrendText(history.uncertainty, 1, Math.max(10, Math.floor(sparkWidth / 2))),
          availableWidth,
          COLORS.success,
          COLORS.warning,
        ),
        ...pairTiles(
          "latency",
          `${Math.round(history.latency.at(-1) ?? 0)}ms`,
          graphTrendText(history.latency, Math.max(1, ...history.latency, 1), Math.max(10, Math.floor(sparkWidth / 2))),
          "speed",
          `${state.tickSeconds.toFixed(2)}s`,
          `tick ${state.tickSeconds.toFixed(2)}s · drones ${state.droneCount}`,
          availableWidth,
          "#a78bfa",
          PANEL_THEME.textPrimary,
        ),
        sectionLine("drone focus"),
        plainLine(
          "focus",
          focusedDrone
            ? `${focusedDrone.id} [${focusedDrone.x},${focusedDrone.y}] → ${focusedDrone.tx == null || focusedDrone.ty == null ? "--" : `[${focusedDrone.tx},${focusedDrone.ty}]`} · ${focusedDrone.status}`
            : "no active drone",
          availableWidth,
        ),
        pairColumns(
          droneHistoryLine("scan", focusedHistory.searched, maxSearchedCells, Math.max(20, Math.floor(availableWidth / 2))),
          droneHistoryLine("entropy", focusedHistory.entropy, 1, Math.max(20, Math.floor(availableWidth / 2))),
          availableWidth,
          PANEL_THEME.textPrimary,
          PANEL_THEME.textPrimary,
        ),
        ...state.drones.slice(0, 3).map((drone, index) =>
          plainLine(
            "agent",
            droneHistorySummary(drone, selectedDrone === index, history.drones[drone.id] ?? { entropy: [], searched: [] }, maxSearchedCells, availableWidth - 10),
            availableWidth,
          )),
        pairColumns(
          `claims   ${state.auctions} settled · bft ${state.bftRounds}`,
          `health   ${state.dropouts > 0 ? `${state.dropouts} lost link` : "stable"}`,
          availableWidth,
        ),
        pairColumns(
          `target   [${state.target.x},${state.target.y}]`,
          `request  ${state.requestedDroneCount} next launch`,
          availableWidth,
        ),
      ];

  for (let index = 0; index < modeLines.length; index += 1) {
    modeLines[index]!.content = lines[index] ?? "";
  }
}
