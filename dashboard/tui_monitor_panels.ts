import {
  StyledText,
  bg as withBg,
  bold as withBold,
  dim as withDim,
  fg as withFg,
  t,
  type TextChunk,
} from "@opentui/core";

import { COLORS, EVENT_TONE_MAP, EVENT_TONE_THEME, PANEL_THEME } from "./tui_theme.ts";
import { isEventToneKey } from "./tui_theme.ts";

function padCell(value: string, width: number): string {
  if (value.length >= width) return value.slice(0, width);
  return value.padEnd(width, " ");
}

function clip(value: string, max: number): string {
  if (value.length <= max) return value;
  if (max <= 1) return value.slice(0, max);
  return `${value.slice(0, max - 1)}…`;
}

function droneShortId(droneId: string): string {
  const match = droneId.match(/(\d+)$/);
  return match ? `d${match[1]}` : droneId.slice(0, 3);
}

export function renderMeshTopology(peers: string[], width: number): StyledText {
  const chunks: TextChunk[] = [];
  const count = peers.length;
  const label = withFg(PANEL_THEME.textSecondary)(withBold(`mesh peers ${count}`));
  chunks.push(...t`${label}`.chunks);

  if (count === 0) {
    chunks.push(...t`\n${withFg(PANEL_THEME.textMuted)(withDim("  no peers"))}`.chunks);
    return new StyledText(chunks);
  }

  const shortPeers = peers.map((p) => droneShortId(p));
  const statusColor = count > 0 ? COLORS.success : COLORS.dim;
  const statusText = withFg(statusColor)(withBold("●"));

  if (count <= 4) {
    const ring = shortPeers.map((p, i) => {
      const next = shortPeers[(i + 1) % count]!;
      return `${p}─${next}`;
    });
    const ringLine = ring.slice(0, 1).join("  ");
    const ringText = `  ${statusText} ${ringLine}`;
    chunks.push(...t`\n${withFg(PANEL_THEME.textSecondary)(ringText)}`.chunks);
    const connector = shortPeers.map((_, i) => {
      const prev = shortPeers[(i - 1 + count) % count]!;
      return `${prev}↔${shortPeers[i]!}`;
    }).slice(0, 1).join("  ");
    const connText = `     ${connector}`;
    chunks.push(...t`\n${withFg(PANEL_THEME.textMuted)(withDim(connText))}`.chunks);
  } else {
    const hub = withFg(COLORS.info)(withBold("◎"));
    const hubLine = `  ${statusText} ${hub} hub`;
    chunks.push(...t`\n${withFg(PANEL_THEME.textSecondary)(hubLine)}`.chunks);
    const spokes = shortPeers.slice(0, Math.min(6, shortPeers.length));
    const spokeLine = `     ${spokes.map((p) => `${p}`).join(" ")}`;
    chunks.push(...t`\n${withFg(PANEL_THEME.textMuted)(withDim(spokeLine))}`.chunks);
  }

  return new StyledText(chunks);
}

function batteryBar(percent: number, barWidth: number): string {
  const clamped = Math.max(0, Math.min(100, percent));
  const filled = Math.round((clamped / 100) * barWidth);
  const blocks = ["▏", "▎", "▍", "▌", "▋", "▊", "▉", "█"];
  if (filled <= 0) return "░".repeat(barWidth);
  if (filled >= barWidth) return "█".repeat(barWidth);
  const full = Math.floor(filled);
  const frac = filled - full;
  const fracIndex = Math.round(frac * (blocks.length - 1));
  const fracChar = frac > 0 ? blocks[fracIndex]! : "";
  return `${"█".repeat(full)}${fracChar}${"░".repeat(Math.max(0, barWidth - full - (fracChar ? 1 : 0)))}`;
}

function batteryColor(percent: number): string {
  if (percent > 60) return COLORS.success;
  if (percent > 30) return COLORS.warning;
  return COLORS.danger;
}

export function renderBatteryPanel(batteryLevels: Record<string, number>, width: number): StyledText {
  const chunks: TextChunk[] = [];
  const entries = Object.entries(batteryLevels);
  const header = withFg(PANEL_THEME.textSecondary)(withBold(`battery ${entries.length}`));
  chunks.push(...t`${header}`.chunks);

  if (entries.length === 0) {
    chunks.push(...t`\n${withFg(PANEL_THEME.textMuted)(withDim("  no data"))}`.chunks);
    return new StyledText(chunks);
  }

  const maxLabel = 4;
  const barWidth = Math.max(4, width - maxLabel - 6);

  for (const [id, level] of entries) {
    const short = droneShortId(id);
    const label = padCell(short, maxLabel);
    const bar = batteryBar(level, barWidth);
    const color = batteryColor(level);
    const percent = `${Math.round(level)}%`;
    const line = `\n${withFg(PANEL_THEME.textMuted)(label)} ${withFg(color)(bar)} ${withFg(color)(percent)}`;
    chunks.push(...t`${line}`.chunks);
  }

  return new StyledText(chunks);
}

export function renderConsensusPanel(rounds: number, width: number): StyledText {
  const chunks: TextChunk[] = [];
  const header = withFg(PANEL_THEME.textSecondary)(withBold("consensus"));
  chunks.push(...t`${header}`.chunks);

  const big = withFg(COLORS.info)(withBold(String(rounds)));
  chunks.push(...t`\n  ${big} ${withFg(PANEL_THEME.textMuted)("rounds")}`.chunks);

  const barWidth = Math.max(4, width - 4);
  const progress = Math.min(1, rounds / 100);
  const filled = Math.round(progress * barWidth);
  const bar = `${"█".repeat(filled)}${"░".repeat(Math.max(0, barWidth - filled))}`;
  const barColor = rounds > 60 ? COLORS.success : rounds > 30 ? COLORS.warning : COLORS.info;
  chunks.push(...t`\n  ${withFg(barColor)(bar)}`.chunks);

  return new StyledText(chunks);
}

export function renderFailurePanel(events: Array<{ type: string; t: number }>, width: number): StyledText {
  const chunks: TextChunk[] = [];
  const header = withFg(PANEL_THEME.textSecondary)(withBold(`failures ${events.length}`));
  chunks.push(...t`${header}`.chunks);

  if (events.length === 0) {
    chunks.push(...t`\n${withFg(PANEL_THEME.textMuted)(withDim("  none"))}`.chunks);
    return new StyledText(chunks);
  }

  const lastFive = events.slice(-5);
  for (const event of lastFive) {
    const tone = isEventToneKey(event.type) ? EVENT_TONE_MAP[event.type] : "stale";
    const chip = EVENT_TONE_THEME[tone];
    const badge = withBg(chip.bg)(withFg(chip.fg)(withBold(` ${padCell(chip.label, 4)} `)));
    const time = withFg(PANEL_THEME.textMuted)(withDim(`${String(event.t).padStart(3, "0")}`));
    const line = `\n${time} ${badge}`;
    chunks.push(...t`${line}`.chunks);
  }

  return new StyledText(chunks);
}
