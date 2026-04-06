import { bg as withBg, bold as withBold, fg as withFg, t } from "@opentui/core";

import type { DisplayMode, FocusPanel, ViewState } from "./tui_monitor_model.ts";
import { entropy as cellEntropy } from "./tui_heatmap.ts";
import { buildHeaderLine as buildHeaderLineShared } from "./tui_sidebar.ts";
import { COLORS, HEADER_THEME, INTERACTION_THEME, MESH_MODE_THEME, MODE_CHIP_THEME, PANEL_THEME } from "./tui_theme.ts";

export function buildHeaderLine(state: ViewState): ReturnType<typeof t> {
  const modeToken = MODE_CHIP_THEME[state.sourceLabel as keyof typeof MODE_CHIP_THEME] ?? HEADER_THEME.tags.mode;
  const meshToken = MESH_MODE_THEME[state.meshMode];
  const bftToken = { fg: COLORS.warning, bg: "#451a03", label: `bft ${state.bftRounds}` };
  return buildHeaderLineShared("entropy hunt", "track 2 · search & rescue", [
    t`${withBg(modeToken.bg)(withFg(modeToken.fg)(withBold(` ${modeToken.label.toUpperCase()} `)))}`,
    t`${withBg(meshToken.bg)(withFg(meshToken.fg)(withBold(` ${meshToken.label.toUpperCase()} `)))}`,
    t`${withBg(bftToken.bg)(withFg(bftToken.fg)(withBold(` ${bftToken.label.toUpperCase()} `)))}`,
  ]);
}

export function buildCompactHeaderLine(state: ViewState): ReturnType<typeof t> {
  const modeToken = MODE_CHIP_THEME[state.sourceLabel as keyof typeof MODE_CHIP_THEME] ?? HEADER_THEME.tags.mode;
  const meshToken = MESH_MODE_THEME[state.meshMode];
  const compactModeLabel = state.sourceLabel === "live" ? "LIVE" : state.sourceLabel === "replay" ? "RPLY" : "SYN";
  return buildHeaderLineShared("ehunt", "track 2", [
    t`${withBg(modeToken.bg)(withFg(modeToken.fg)(withBold(` ${compactModeLabel} `)))}`,
    t`${withBg(meshToken.bg)(withFg(meshToken.fg)(withBold(` ${state.meshMode.toUpperCase()} `)))}`,
    t`${withBg("#451a03")(withFg(COLORS.warning)(withBold(` B${state.bftRounds} `)))}`,
  ]);
}

export function buildSubheaderLine(state: ViewState): ReturnType<typeof t> {
  const warnings = [
    state.gridTruncated ? `grid capped to ${state.gridSize}x${state.gridSize}` : "",
    state.hiddenDroneCount > 0 ? `+${state.hiddenDroneCount} hidden drones` : "",
    state.hiddenEventCount > 0 ? `+${state.hiddenEventCount} hidden events` : "",
  ].filter(Boolean).join(" · ");
  return t`${withFg(PANEL_THEME.textMuted)("source")} ${withFg(PANEL_THEME.textSecondary)(state.sourceUrl)}${warnings ? withFg(PANEL_THEME.textMuted)(` · ${warnings}`) : ""}`;
}

export function buildCompactSubheaderLine(state: ViewState): ReturnType<typeof t> {
  return t`${withFg(PANEL_THEME.textMuted)(`target [${state.target.x},${state.target.y}]`)} ${withBg(INTERACTION_THEME.navigate.bg)(withFg(INTERACTION_THEME.navigate.fg)(" move "))} ${withBg(INTERACTION_THEME.switch.bg)(withFg(INTERACTION_THEME.switch.fg)(" views "))} ${withBg(INTERACTION_THEME.select.bg)(withFg(INTERACTION_THEME.select.fg)(" h/r/e focus "))} ${withBg(INTERACTION_THEME.quit.bg)(withFg(INTERACTION_THEME.quit.fg)(" quit "))}`;
}

export function buildInspectorLine(state: ViewState, cursorX: number, cursorY: number, compact = false): ReturnType<typeof t> {
  const cell = state.grid[cursorY]?.[cursorX];
  const certainty = Number(cell?.certainty ?? 0.5);
  const entropy = Number(cell?.entropy ?? cellEntropy(certainty));
  const owner = Number(cell?.owner ?? -1);
  const ownerLabel = owner >= 0 ? `reserved by d${owner + 1}` : "unclaimed";
  if (compact) {
    return t`${withFg(PANEL_THEME.textSecondary)(`cell [${cursorX},${cursorY}]`)} ${withFg(PANEL_THEME.textMuted)(`unc ${entropy.toFixed(2)} · conf ${certainty.toFixed(2)} · ${ownerLabel}`)}`;
  }
  return t`${withFg(PANEL_THEME.textSecondary)(`cell [${cursorX},${cursorY}]`)} ${withFg(PANEL_THEME.textMuted)(`uncertainty ${entropy.toFixed(2)} · confidence ${certainty.toFixed(2)} · ${ownerLabel} · target [${state.target.x},${state.target.y}]`)}`;
}

export function buildFocusStatusLine(
  state: ViewState,
  focusedPanel: FocusPanel,
  cursorX: number,
  cursorY: number,
  selectedDrone: number,
  selectedEvent: number,
  tickLatencyMs: number,
  compact = false,
): ReturnType<typeof t> {
  let focusLabel = `heatmap [${cursorX},${cursorY}]`;
  if (focusedPanel === "roster") {
    const drone = state.drones[selectedDrone];
    focusLabel = drone ? `drone ${drone.id} [${drone.x},${drone.y}]` : "active drones";
  } else if (focusedPanel === "events") {
    const event = state.events[selectedEvent];
    focusLabel = event ? `event ${event.type} at ${event.t}s` : "attention timeline";
  }
  const latency = `rt=${Math.max(0, Math.round(tickLatencyMs))}ms`;
  if (compact) {
    return t`${withFg(PANEL_THEME.textMuted)(focusLabel)} ${withFg(PANEL_THEME.textMuted)("·")} ${withFg(COLORS.info)(latency)}`;
  }
  return t`${withFg(PANEL_THEME.textMuted)(`selected ${focusLabel}`)} ${withFg(PANEL_THEME.textMuted)("·")} ${withFg(COLORS.info)(latency)}`;
}

export function buildDisplayModeChip(mode: DisplayMode, active: boolean, compact = false): ReturnType<typeof t> {
  const palette = active
    ? { fg: "#f8fafc", bg: "#1d4ed8" }
    : { fg: PANEL_THEME.textSecondary, bg: "#0f1b33" };
  const label = compact
    ? mode === "overview"
      ? " 1 ovw "
      : mode === "detail"
        ? " 2 det "
        : mode === "map"
          ? " 3 map "
          : mode === "config"
            ? " 4 cfg "
            : " 5 gph "
    : mode === "overview"
      ? " 1 overview "
      : mode === "detail"
        ? " 2 detail "
        : mode === "map"
          ? " 3 map "
          : mode === "config"
            ? " 4 config "
            : " 5 graphs ";
  return t`${withBg(palette.bg)(withFg(palette.fg)(withBold(label)))}`;
}

export function buildDetailSummary(
  state: ViewState,
  focusedPanel: FocusPanel,
  cursorX: number,
  cursorY: number,
  selectedDrone: number,
  selectedEvent: number,
): [string, string, string] {
  if (focusedPanel === "roster") {
    const drone = state.drones[selectedDrone];
    if (!drone) return ["active drones", "no drone selected", "click a drone row or use arrows"];
    return [
      `${drone.id} · ${drone.status}`,
      `now [${drone.x},${drone.y}] → ${drone.tx == null || drone.ty == null ? "awaiting task" : `[${drone.tx},${drone.ty}]`} · uncertainty ${drone.entropy.toFixed(2)}`,
      drone.offline ? "link lost — inspect the alert timeline" : "enter follows this drone · h/r/e switches focus",
    ];
  }
  if (focusedPanel === "events") {
    const event = state.events[selectedEvent];
    if (!event) return ["attention timeline", "no event selected", "timeline is empty"];
    return [
      `${event.type.toUpperCase()} · ${event.t}s`,
      event.msg.slice(0, 120),
      "use the timeline to spot changes, risk, and next actions",
    ];
  }
  const cell = state.grid[cursorY]?.[cursorX];
  const certainty = Number(cell?.certainty ?? 0.5);
  const entropy = Number(cell?.entropy ?? cellEntropy(certainty));
  const owner = Number(cell?.owner ?? -1);
  return [
    `cell [${cursorX},${cursorY}]`,
    `uncertainty ${entropy.toFixed(2)} · confidence ${certainty.toFixed(2)} · ${owner >= 0 ? `reserved by d${owner + 1}` : "unclaimed"}`,
    "arrows inspect cells · enter follows a drone · m opens the full map",
  ];
}
