import {
  StyledText,
  bg as withBg,
  bold as withBold,
  dim as withDim,
  fg as withFg,
  strikethrough as withStrikethrough,
  t,
  type TextChunk,
} from "@opentui/core";

import type { NormalizedDrone, NormalizedEvent } from "./tui_types.ts";
import { EVENT_TONE_MAP, EVENT_TONE_THEME, FOCUS_THEME, PANEL_THEME, STATUS_CHIP_THEME, STATUS_DISPLAY_MAP } from "./tui_theme.ts";

function padCell(value: string, width: number): string {
  if (value.length >= width) return value.slice(0, width);
  return value.padEnd(width, " ");
}

function clip(value: string, max: number): string {
  if (value.length <= max) return value;
  if (max <= 1) return value.slice(0, max);
  return `${value.slice(0, max - 1)}…`;
}

function coordLabel(x: number | null | undefined, y: number | null | undefined): string {
  if (x == null || y == null) return "--";
  return `[${x},${y}]`;
}

function accentFor(droneId: string): string {
  const match = droneId.match(/(\d+)$/);
  const index = match ? Math.max(0, Number(match[1]) - 1) : 0;
  const colors = ["#378ADD", "#1D9E75", "#BA7517", "#D85A30", "#D4537E"];
  return colors[index % colors.length] ?? PANEL_THEME.textPrimary;
}

function droneShortId(droneId: string): string {
  const match = droneId.match(/(\d+)$/);
  return match ? `d${match[1]}` : droneId.slice(0, 3);
}

function focusWrap(content: StyledText, _selected: boolean, _focusedPanel: boolean): StyledText {
  if (!_selected) return content;
  const token = _focusedPanel ? FOCUS_THEME.cells.active : FOCUS_THEME.cells.focused;
  const rowChunks: TextChunk[] = [
    withBg(token.bg)(withFg(token.fg)("▶ ")),
    ...content.chunks.map((chunk) => withBg(token.bg)(chunk)),
  ];
  return new StyledText(rowChunks);
}

export function mapStatus(raw: string | undefined, offline: boolean): string {
  if (offline) return "offline";
  return STATUS_DISPLAY_MAP[raw as keyof typeof STATUS_DISPLAY_MAP] ?? raw ?? "idle";
}

export function renderDroneRow({
  drone,
  selected = false,
  focusedPanel = false,
}: {
  drone: NormalizedDrone;
  selected?: boolean;
  focusedPanel?: boolean;
}): StyledText {
  const accent = accentFor(drone.id);
  const shortId = droneShortId(drone.id);
  const name = drone.offline
    ? withFg(PANEL_THEME.textMuted)(withStrikethrough(padCell(shortId, 3)))
    : withFg(PANEL_THEME.textPrimary)(withBold(padCell(shortId, 3)));
  const statusKey = (drone.status in STATUS_CHIP_THEME ? drone.status : "idle") as keyof typeof STATUS_CHIP_THEME;
  const chip = STATUS_CHIP_THEME[statusKey];
  const chipText = withBg(chip.bg)(withFg(chip.fg)(` ${chip.label.toUpperCase()} `));
  const current = withFg(PANEL_THEME.textMuted)(padCell(coordLabel(drone.x, drone.y), 5));
  const target = withFg(PANEL_THEME.textSecondary)(padCell(coordLabel(drone.tx, drone.ty), 5));
  const entropy = withFg(PANEL_THEME.textSecondary)(padCell(`H${drone.entropy.toFixed(2)}`, 5));
  const row = t`${withFg(accent)(withBold("●"))} ${name} ${current}${withFg(PANEL_THEME.textMuted)("→")}${target} ${entropy} ${chipText}`;
  return focusWrap(row, selected, focusedPanel);
}

function compressEventMessage(message: string): string {
  return message
    .replace(/^survivor confirmed at /i, "survivor @ ")
    .replace(/^drone_(\d+) heartbeat timeout$/i, "d$1 lost link")
    .replace(/^auction drone_(\d+) vs drone_(\d+) -> drone_(\d+) wins$/i, "claim win d$3")
    .replace(/^auction d(\d+) vs d(\d+) -> d(\d+) wins$/i, "claim win d$3");
}

export function renderEventRow({
  event,
  selected = false,
  focusedPanel = false,
}: {
  event: NormalizedEvent;
  selected?: boolean;
  focusedPanel?: boolean;
}): StyledText {
  const tone = EVENT_TONE_MAP[event.type as keyof typeof EVENT_TONE_MAP] ?? "info";
  const chip = EVENT_TONE_THEME[tone];
  const badge = withBg(chip.bg)(withFg(chip.fg)(withBold(` ${padCell(chip.label, 4)} `)));
  const time = withFg(PANEL_THEME.textMuted)(withDim(`${String(event.t).padStart(3, "0")}`));
  const bodyColor = tone === "stale" ? chip.accent : tone === "found" ? chip.accent : PANEL_THEME.textSecondary;
  const body = withFg(bodyColor)(padCell(clip(compressEventMessage(event.msg), 26), 26));
  const row = t`${time} ${badge} ${body}`;
  return focusWrap(row, selected, focusedPanel);
}

export function buildFooterLine(message: string) {
  return t`${withFg("#22c55e")("●")} ${withFg(PANEL_THEME.textMuted)(message)}`;
}

export function buildHeaderLine(title: string, subtitle: string, chips: ReadonlyArray<StyledText> = []): StyledText {
  const chunks: TextChunk[] = [
    ...t`${withFg(PANEL_THEME.textPrimary)(withBold(title))} ${withFg(PANEL_THEME.textMuted)(subtitle)}`.chunks,
  ];
  for (const chip of chips) {
    chunks.push(withFg(PANEL_THEME.textMuted)(" "));
    chunks.push(...chip.chunks);
  }
  return new StyledText(chunks);
}
