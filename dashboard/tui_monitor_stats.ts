import { BoxRenderable, TextRenderable, bold as withBold, fg as withFg, t } from "@opentui/core";

import type { ViewState } from "./tui_monitor_model.ts";
import { formatDuration } from "./tui_monitor_model.ts";
import { COLORS, PANEL_THEME, STAT_THRESHOLDS, coverageColorFor } from "./tui_theme.ts";

export const STAT_SPECS = [
  { key: "coverage", label: "grid scanned", grow: 2 },
  { key: "entropy", label: "uncertainty", grow: 1 },
  { key: "auctions", label: "claim rounds", grow: 1 },
  { key: "dropouts", label: "drone health", grow: 2 },
  { key: "elapsed", label: "mission time", grow: 1 },
] as const;

export type StatKey = typeof STAT_SPECS[number]["key"];

export function buildStatValues(state: ViewState): string[] {
  const coverageStatus = state.coverage >= STAT_THRESHOLDS.coverage.good ? "on track" : state.coverage >= STAT_THRESHOLDS.coverage.warn ? "watch" : "slow";
  const entropyStatus = state.avgEntropy >= STAT_THRESHOLDS.entropy.high ? "high" : state.avgEntropy >= STAT_THRESHOLDS.entropy.warn ? "watch" : "low";
  const claimStatus = state.auctions >= STAT_THRESHOLDS.auctions.active ? "settled" : "idle";
  return [
    `${coverageStatus} · ${Math.round(state.coverage)}%`,
    `${entropyStatus} · ${state.avgEntropy.toFixed(2)}`,
    `${state.auctions} ${claimStatus}`,
    state.dropouts > 0 ? `risk · ${state.dropouts} lost` : "stable · all linked",
    `${formatDuration(state.elapsed)} active`,
  ];
}

export function buildCompactStatsContent(state: ViewState, tickLatencyMs: number) {
  return t`${withFg(coverageColorFor(Math.round(state.coverage)))(withBold(`scan ${Math.round(state.coverage)}%`))} ${withFg(PANEL_THEME.textMuted)("·")} ${withFg(COLORS.warning)(withBold(`unc ${state.avgEntropy.toFixed(2)}`))} ${withFg(PANEL_THEME.textMuted)("·")} ${withFg(PANEL_THEME.textPrimary)(`${state.auctions} claims`)} ${withFg(PANEL_THEME.textMuted)("·")} ${withFg(state.dropouts > 0 ? COLORS.danger : COLORS.success)(state.dropouts > 0 ? `${state.dropouts} lost` : "stable")} ${withFg(PANEL_THEME.textMuted)("·")} ${withFg(PANEL_THEME.textSecondary)(formatDuration(state.elapsed))} ${withFg(PANEL_THEME.textMuted)("·")} ${withFg(COLORS.info)(`rt ${Math.max(0, Math.round(tickLatencyMs))}ms`)}`;
}

export function statVisualsFor(key: StatKey, state: ViewState) {
  const coverageC = coverageColorFor(Math.round(state.coverage));
  switch (key) {
    case "coverage":
      return { color: coverageC, backgroundColor: COLORS.bgSuccessDim, borderColor: coverageC };
    case "entropy":
      return { color: COLORS.warning, backgroundColor: COLORS.bgWarningDim, borderColor: COLORS.warning };
    case "dropouts":
      return state.dropouts > 0
        ? { color: COLORS.danger, backgroundColor: COLORS.bgDangerDim, borderColor: COLORS.danger }
        : { color: PANEL_THEME.textPrimary, backgroundColor: COLORS.bgSuccessDim, borderColor: COLORS.success };
    case "auctions":
      return { color: PANEL_THEME.textPrimary, backgroundColor: COLORS.bgMutedBlue, borderColor: COLORS.border };
    case "elapsed":
      return { color: PANEL_THEME.textPrimary, backgroundColor: COLORS.bgNeutral, borderColor: COLORS.border };
  }
}

export function syncMonitorStats(args: {
  compactLayout: boolean;
  state: ViewState;
  tickLatencyMs: number;
  compactStatsText: TextRenderable;
  statCards: BoxRenderable[];
  statLabels: TextRenderable[];
  statValues: TextRenderable[];
}) {
  const { compactLayout, state, tickLatencyMs, compactStatsText, statCards, statLabels, statValues } = args;
  const values = buildStatValues(state);
  if (compactLayout) {
    compactStatsText.content = buildCompactStatsContent(state, tickLatencyMs);
    return;
  }
  for (const [index, spec] of STAT_SPECS.entries()) {
    const { color, backgroundColor, borderColor } = statVisualsFor(spec.key, state);
    statCards[index]!.borderColor = borderColor;
    statCards[index]!.backgroundColor = backgroundColor;
    statLabels[index]!.bg = backgroundColor;
    statValues[index]!.bg = backgroundColor;
    statLabels[index]!.content = t`${withFg(PANEL_THEME.textMuted)(spec.label)}`;
    statValues[index]!.content = t`${withFg(color)(withBold(values[index]!))}`;
  }
}
