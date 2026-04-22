import {
  StyledText,
  bold as withBold,
  dim as withDim,
  fg as withFg,
  t,
  type TextChunk,
} from "@opentui/core";

import type { MonitorHistory } from "./tui_monitor_aux.ts";
import { COLORS, PANEL_THEME } from "./tui_theme.ts";

const SPARK_CHARS = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"];
const BAR_CHARS = ["▏", "▎", "▍", "▌", "▋", "▊", "▉", "█"];

function clampInt(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, Math.floor(value)));
}

function interpolateValue(data: number[], width: number, index: number): number {
  if (width <= 1 || data.length <= 1) return data.at(-1) ?? data[0] ?? 0;
  const position = (index * (data.length - 1)) / (width - 1);
  const left = Math.floor(position);
  const right = Math.min(data.length - 1, Math.ceil(position));
  const blend = position - left;
  const leftValue = data[left] ?? 0;
  const rightValue = data[right] ?? leftValue;
  return leftValue + (rightValue - leftValue) * blend;
}

function trendDirection(values: number[]): "up" | "down" | "flat" {
  if (values.length < 2) return "flat";
  const previous = values.at(-2) ?? values.at(-1) ?? 0;
  const current = values.at(-1) ?? 0;
  if (current > previous) return "up";
  if (current < previous) return "down";
  return "flat";
}

function trendColorForMetric(
  metric: "coverage" | "entropy" | "latency" | "auctions" | "dropouts",
  direction: "up" | "down" | "flat",
): string {
  if (direction === "flat") return COLORS.info;
  const goodUp = metric === "coverage" || metric === "auctions";
  const goodDown = metric === "entropy" || metric === "latency" || metric === "dropouts";
  if (direction === "up") {
    return goodUp ? COLORS.success : goodDown ? COLORS.danger : COLORS.info;
  }
  return goodDown ? COLORS.success : goodUp ? COLORS.danger : COLORS.info;
}

function formatNumber(value: number): string {
  if (Number.isInteger(value)) return String(value);
  return value.toFixed(2);
}

function sparklineChars(data: number[], width: number, min?: number, max?: number): string {
  if (!data.length) return "—";
  const safeMin = min ?? Math.min(...data);
  const safeMax = max ?? Math.max(...data);
  const range = Math.max(safeMax - safeMin, 1e-9);
  const points = Array.from({ length: Math.max(1, width) }, (_, index) =>
    interpolateValue(data, width, index),
  );
  return points
    .map((value) => {
      const normalized = (value - safeMin) / range;
      const idx = clampInt(normalized * (SPARK_CHARS.length - 1), 0, SPARK_CHARS.length - 1);
      return SPARK_CHARS[idx];
    })
    .join("");
}

function sparkbarChars(data: number[], width: number): string {
  if (!data.length) return "—";
  const safeMax = Math.max(...data, 1);
  const points = Array.from({ length: Math.max(1, width) }, (_, index) =>
    interpolateValue(data, width, index),
  );
  return points
    .map((value) => {
      const idx = clampInt((value / safeMax) * (BAR_CHARS.length - 1), 0, BAR_CHARS.length - 1);
      return BAR_CHARS[idx];
    })
    .join("");
}

export function sparkline(
  data: number[],
  width: number,
  options?: { min?: number; max?: number; color?: string },
): StyledText {
  const chars = sparklineChars(data, width, options?.min, options?.max);
  const color = options?.color ?? COLORS.info;
  return t`${withFg(color)(chars)}`;
}

export function sparkbar(
  data: number[],
  width: number,
  options?: { color?: string },
): StyledText {
  const chars = sparkbarChars(data, width);
  const color = options?.color ?? COLORS.info;
  return t`${withFg(color)(chars)}`;
}

function buildLabelWithSparkline(
  name: string,
  current: string,
  min: string,
  max: string,
  sparklineStyled: StyledText,
  trendGlyph: string,
  trendColor: string,
): StyledText {
  const label = `${name.padEnd(10)} ${current.padEnd(8)} min ${min.padEnd(6)} max ${max.padEnd(6)}`;
  const labelStyled = t`${withFg(PANEL_THEME.textMuted)(label)} ${withFg(PANEL_THEME.textMuted)(" ")}`;
  const trendStyled = t`${withFg(trendColor)(trendGlyph)}`;
  return new StyledText([
    ...labelStyled.chunks,
    ...sparklineStyled.chunks,
    withFg(PANEL_THEME.textMuted)(" "),
    ...trendStyled.chunks,
  ]);
}

export function renderCoverageSparkline(history: MonitorHistory, width: number): StyledText {
  const data = history.coverage;
  if (!data.length) {
    return t`${withFg(PANEL_THEME.textMuted)("coverage — no data")}`;
  }
  const current = data.at(-1) ?? 0;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const direction = trendDirection(data);
  const color = trendColorForMetric("coverage", direction);
  const label = `cov ${Math.round(current)}% min ${Math.round(min)} max ${Math.round(max)}`;
  const labelLen = label.length;
  const sparkWidth = Math.max(4, width - labelLen - 3);
  const spark = sparkline(data, sparkWidth, { min: 0, max: 100, color });
  const glyph = direction === "up" ? "↑" : direction === "down" ? "↓" : "→";
  const labelStyled = t`${withFg(PANEL_THEME.textMuted)(label)} `;
  const trendStyled = t`${withFg(color)(glyph)}`;
  return new StyledText([...labelStyled.chunks, ...spark.chunks, withFg(PANEL_THEME.textMuted)(" "), ...trendStyled.chunks]);
}

export function renderEntropySparkline(history: MonitorHistory, width: number): StyledText {
  const data = history.uncertainty;
  if (!data.length) {
    return t`${withFg(PANEL_THEME.textMuted)("entropy — no data")}`;
  }
  const current = data.at(-1) ?? 0;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const direction = trendDirection(data);
  const color = trendColorForMetric("entropy", direction);
  const label = `H ${formatNumber(current)} min ${formatNumber(min)} max ${formatNumber(max)}`;
  const labelLen = label.length;
  const sparkWidth = Math.max(4, width - labelLen - 3);
  const spark = sparkline(data, sparkWidth, { min: 0, max: 1, color });
  const glyph = direction === "up" ? "↑" : direction === "down" ? "↓" : "→";
  const labelStyled = t`${withFg(PANEL_THEME.textMuted)(label)} `;
  const trendStyled = t`${withFg(color)(glyph)}`;
  return new StyledText([...labelStyled.chunks, ...spark.chunks, withFg(PANEL_THEME.textMuted)(" "), ...trendStyled.chunks]);
}

export function renderLatencySparkline(history: MonitorHistory, width: number): StyledText {
  const data = history.latency;
  if (!data.length) {
    return t`${withFg(PANEL_THEME.textMuted)("latency — no data")}`;
  }
  const current = data.at(-1) ?? 0;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const direction = trendDirection(data);
  const color = trendColorForMetric("latency", direction);
  const label = `lat ${Math.round(current)}ms min ${Math.round(min)} max ${Math.round(max)}`;
  const labelLen = label.length;
  const sparkWidth = Math.max(4, width - labelLen - 3);
  const spark = sparkline(data, sparkWidth, { min: 0, max: Math.max(max, 1), color });
  const glyph = direction === "up" ? "↑" : direction === "down" ? "↓" : "→";
  const labelStyled = t`${withFg(PANEL_THEME.textMuted)(label)} `;
  const trendStyled = t`${withFg(color)(glyph)}`;
  return new StyledText([...labelStyled.chunks, ...spark.chunks, withFg(PANEL_THEME.textMuted)(" "), ...trendStyled.chunks]);
}

export function renderAuctionsSparkline(history: MonitorHistory, width: number): StyledText {
  const data = history.auctions;
  if (!data.length) {
    return t`${withFg(PANEL_THEME.textMuted)("auctions — no data")}`;
  }
  const current = data.at(-1) ?? 0;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const direction = trendDirection(data);
  const color = trendColorForMetric("auctions", direction);
  const label = `auc ${String(current)} min ${String(min)} max ${String(max)}`;
  const labelLen = label.length;
  const sparkWidth = Math.max(4, width - labelLen - 3);
  const spark = sparkline(data, sparkWidth, { min: 0, max: Math.max(max, 1), color });
  const glyph = direction === "up" ? "↑" : direction === "down" ? "↓" : "→";
  const labelStyled = t`${withFg(PANEL_THEME.textMuted)(label)} `;
  const trendStyled = t`${withFg(color)(glyph)}`;
  return new StyledText([...labelStyled.chunks, ...spark.chunks, withFg(PANEL_THEME.textMuted)(" "), ...trendStyled.chunks]);
}

export function renderDropoutsSparkline(history: MonitorHistory, width: number): StyledText {
  const data = history.dropouts;
  if (!data.length) {
    return t`${withFg(PANEL_THEME.textMuted)("dropouts — no data")}`;
  }
  const current = data.at(-1) ?? 0;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const direction = trendDirection(data);
  const color = trendColorForMetric("dropouts", direction);
  const label = `drop ${String(current)} min ${String(min)} max ${String(max)}`;
  const labelLen = label.length;
  const sparkWidth = Math.max(4, width - labelLen - 3);
  const spark = sparkline(data, sparkWidth, { min: 0, max: Math.max(max, 1), color });
  const glyph = direction === "up" ? "↑" : direction === "down" ? "↓" : "→";
  const labelStyled = t`${withFg(PANEL_THEME.textMuted)(label)} `;
  const trendStyled = t`${withFg(color)(glyph)}`;
  return new StyledText([...labelStyled.chunks, ...spark.chunks, withFg(PANEL_THEME.textMuted)(" "), ...trendStyled.chunks]);
}

export function renderDroneMiniCharts(
  history: MonitorHistory,
  droneIds: string[],
  width: number,
): StyledText {
  if (!droneIds.length) {
    return t`${withFg(PANEL_THEME.textMuted)("drones     — no data")}`;
  }
  const chunks: TextChunk[] = [];
  const prefix = t`${withFg(PANEL_THEME.textMuted)("drones     ")}`;
  chunks.push(...prefix.chunks);
  const perDroneWidth = Math.max(2, Math.min(4, Math.floor((width - 11) / droneIds.length) - 3));
  for (let i = 0; i < droneIds.length; i++) {
    const id = droneIds[i]!;
    const droneHistory = history.drones[id];
    const shortId = id.replace(/^drone_/, "d");
    if (i > 0) {
      chunks.push(withFg(PANEL_THEME.textMuted)("  "));
    }
    chunks.push(withFg(PANEL_THEME.textMuted)(`${shortId} `));
    if (droneHistory && droneHistory.entropy.length > 0) {
      const spark = sparklineChars(droneHistory.entropy, perDroneWidth, 0, 1);
      chunks.push(withFg(COLORS.info)(spark));
    } else {
      chunks.push(withFg(PANEL_THEME.textMuted)("—"));
    }
  }
  return new StyledText(chunks);
}

export function renderChartDashboard(
  history: MonitorHistory,
  width: number,
  height: number,
): StyledText {
  const droneIds = Object.keys(history.drones).sort();
  const lines: StyledText[] = [];
  lines.push(renderCoverageSparkline(history, width));
  lines.push(renderEntropySparkline(history, width));
  lines.push(renderLatencySparkline(history, width));
  lines.push(renderAuctionsSparkline(history, width));
  lines.push(renderDropoutsSparkline(history, width));
  lines.push(renderDroneMiniCharts(history, droneIds, width));

  const header = t`${withFg(PANEL_THEME.textMuted)(withDim("[ GRAPHS ]"))}`;
  const footer = t`${withFg(PANEL_THEME.textMuted)(withDim(`${history.coverage.length} samples · newest →`))}`;

  const allLines: StyledText[] = [header, ...lines, footer];

  const visible = allLines.slice(0, Math.max(1, height));

  const newlineChunks = t`
`.chunks;
  const combinedChunks: TextChunk[] = [];
  for (let i = 0; i < visible.length; i++) {
    if (i > 0) combinedChunks.push(...newlineChunks);
    combinedChunks.push(...visible[i].chunks);
  }
  return new StyledText(combinedChunks);
}
