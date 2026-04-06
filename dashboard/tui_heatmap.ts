import {
  StyledText,
  bg as withBg,
  bold as withBold,
  dim as withDim,
  fg as withFg,
  t,
  type TextChunk,
} from "@opentui/core";

import type { CellSnapshot, MonitorState, NormalizedDrone } from "./tui_types.ts";
import { DRONE_ACCENT_COLORS, FOCUS_THEME, HEATMAP_THEME, PANEL_THEME } from "./tui_theme.ts";

const GRID_SIZE_FALLBACK = 10;

export function entropy(certainty: number): number {
  if (certainty <= 0 || certainty >= 1) return 0;
  return -(certainty * Math.log2(certainty) + (1 - certainty) * Math.log2(1 - certainty));
}

export function gridCellEntropy(cell: CellSnapshot | undefined): number {
  if (!cell) return 1;
  if (typeof cell.entropy === "number") return cell.entropy;
  return entropy(Number(cell.certainty ?? 0.5));
}

export function droneToken(droneId: string): { label: string; color: string } {
  const suffix = String(droneId).split("_").pop() ?? "1";
  const index = Math.max(0, (Number.parseInt(suffix, 10) || 1) - 1) % DRONE_ACCENT_COLORS.length;
  return {
    label: `D${suffix}`.slice(0, 2),
    color: DRONE_ACCENT_COLORS[index] ?? PANEL_THEME.textPrimary,
  };
}

function droneIndex(state: MonitorState): Map<string, NormalizedDrone> {
  return new Map<string, NormalizedDrone>(state.drones.map((drone) => [`${drone.x},${drone.y}`, drone]));
}

function gridSize(state: MonitorState): number {
  const explicit = typeof (state as { gridSize?: unknown }).gridSize === "number" ? Number((state as { gridSize?: unknown }).gridSize) : 0;
  return Math.max(1, explicit, state.grid.length, state.grid[0]?.length ?? 0);
}

function ownerAccent(owner: number): string {
  const index = ((owner % DRONE_ACCENT_COLORS.length) + DRONE_ACCENT_COLORS.length) % DRONE_ACCENT_COLORS.length;
  return DRONE_ACCENT_COLORS[index] ?? PANEL_THEME.textPrimary;
}

function selectionColors(isFocusedPanel: boolean): { bg: string; fg: string } {
  const token = isFocusedPanel ? FOCUS_THEME.cells.active : FOCUS_THEME.cells.focused;
  return { bg: token.bg, fg: token.fg };
}

function cellFillGlyph(entropyValue: number): string {
  if (entropyValue > HEATMAP_THEME.thresholds.high) return "█";
  if (entropyValue >= HEATMAP_THEME.thresholds.medium) return "▓";
  return "░";
}

function fillCell(label: string, cellWidth: number, fillGlyph: string): string {
  const trimmed = label.slice(0, cellWidth);
  if (!trimmed) return fillGlyph.repeat(cellWidth);
  if (trimmed.length >= cellWidth) return trimmed;
  const left = Math.floor((cellWidth - trimmed.length) / 2);
  const right = cellWidth - trimmed.length - left;
  return `${fillGlyph.repeat(left)}${trimmed}${fillGlyph.repeat(right)}`;
}

function focusOverlayLabel(label: string, cellWidth: number, fillGlyph: string): string {
  const trimmed = label.trim();
  if (!trimmed) return fillCell(cellWidth >= 4 ? "◇" : "◆", cellWidth, fillGlyph);
  if (cellWidth >= trimmed.length + 2) {
    return fillCell(`▕${trimmed}▏`, cellWidth, fillGlyph);
  }
  return fillCell(trimmed, cellWidth, fillGlyph);
}

export function buildAxisRow(size: number = GRID_SIZE_FALLBACK, cellWidth: number = 2): StyledText {
  const labels = Array.from({ length: size }, (_, x) => String(x).padStart(2, "0").padEnd(cellWidth, " "));
  return t`${withFg(PANEL_THEME.textMuted)(withDim(`   ${labels.join("")}`))}`;
}

export function buildLegend(compact = false): StyledText {
  if (compact) {
    return t`${withFg(PANEL_THEME.textMuted)(withDim("risk"))} ${withFg(HEATMAP_THEME.bandColors.high)(withBold("██"))} ${withFg(HEATMAP_THEME.bandColors.medium)(withBold("▓▓"))} ${withFg(HEATMAP_THEME.bandColors.low)(withBold("░░"))} ${withFg(PANEL_THEME.textMuted)(withDim("clear"))} ${withFg(PANEL_THEME.textSecondary)("◎ tgt · D")}`;
  }
  return t`${withFg(PANEL_THEME.textMuted)(withDim("risk"))} ${withFg(HEATMAP_THEME.bandColors.high)(withBold("██"))} ${withFg(HEATMAP_THEME.bandColors.medium)(withBold("▓▓"))} ${withFg(HEATMAP_THEME.bandColors.low)(withBold("░░"))} ${withFg(PANEL_THEME.textMuted)(withDim("clear"))} ${withFg(PANEL_THEME.textSecondary)("◎ target")} ${withFg(PANEL_THEME.textMuted)("·")} ${withFg(PANEL_THEME.textSecondary)("· reserved")} ${withFg(PANEL_THEME.textMuted)("·")} ${withFg(PANEL_THEME.textSecondary)("D drone")} ${withFg(PANEL_THEME.textMuted)("·")} ${withFg(PANEL_THEME.textSecondary)("◇ focus")}`;
}

export function renderHeatmapRow(args: {
  y: number;
  state: MonitorState;
  flashTarget: boolean;
  focusedCell?: { x: number; y: number } | null;
  cellWidth?: number;
  focusedPanel?: boolean;
}): StyledText {
  const { y, state, flashTarget, focusedCell = null, focusedPanel = false } = args;
  const cellWidth = args.cellWidth ?? 2;
  const drones = droneIndex(state);
  const size = gridSize(state);
  const chunks: TextChunk[] = [withFg(PANEL_THEME.textMuted)(withDim(`${String(y).padStart(2, "0")} `))];

  for (let x = 0; x < size; x += 1) {
    const drone = drones.get(`${x},${y}`);
    const cell = state.grid[y]?.[x];
    const entropyValue = gridCellEntropy(cell);
    const owner = Number(cell?.owner ?? -1);
    const isTarget = state.target.x === x && state.target.y === y;
    const fillGlyph = cellFillGlyph(entropyValue);

    let bg: string = HEATMAP_THEME.bandColors[
      entropyValue > HEATMAP_THEME.thresholds.high
        ? "high"
        : entropyValue >= HEATMAP_THEME.thresholds.medium
          ? "medium"
          : "low"
    ];
    let fg: string = entropyValue < HEATMAP_THEME.thresholds.medium ? PANEL_THEME.textPrimary : PANEL_THEME.shellText;
    let label = "";

    if (owner >= 0) {
      fg = ownerAccent(owner);
      label = "·";
    }

    if (isTarget) {
      fg = HEATMAP_THEME.targetBorder;
      label = HEATMAP_THEME.legend.target.glyph;
      if (flashTarget) {
        bg = HEATMAP_THEME.survivorFlashBackground;
        fg = PANEL_THEME.textPrimary;
      }
    }

    if (drone) {
      const token = droneToken(drone.id);
      bg = PANEL_THEME.panelBackground;
      fg = token.color;
      label = token.label;
    }

    if (focusedCell && focusedCell.x === x && focusedCell.y === y) {
      const selection = selectionColors(focusedPanel);
      fg = selection.fg;
      label = focusOverlayLabel(label, cellWidth, fillGlyph);
      if (!drone && !isTarget && owner < 0) {
        bg = selection.bg;
      }
    }

    const cellText = label ? fillCell(label, cellWidth, fillGlyph) : fillGlyph.repeat(cellWidth);
    chunks.push(withBg(bg)(withFg(fg)(label ? withBold(cellText) : cellText)));
  }

  return new StyledText(chunks);
}
