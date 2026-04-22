import {
  StyledText,
  Timeline,
  bg as withBg,
  bold as withBold,
  dim as withDim,
  engine,
  fg as withFg,
  t,
  type TextChunk,
} from "@opentui/core";

import type { CellSnapshot, MonitorState, NormalizedDrone } from "./tui_types.ts";
import { DRONE_ACCENT_COLORS, FOCUS_THEME, HEATMAP_THEME, PANEL_THEME } from "./tui_theme.ts";

const GRID_SIZE_FALLBACK = 10;
export const DRONE_TRAIL_FRAMES = 3;

// ── Dither tables ───────────────────────────────────────────────────────────

/** 16 Braille density levels × 16 variants each (maps to U+2800..U+28FF). */
const BRAILLE_DITHER: readonly string[][] = Array.from({ length: 16 }, (_, level) =>
  Array.from({ length: 16 }, (_, v) => String.fromCharCode(0x2800 + Math.min(255, level * 16 + v)))
);

/** 16 block-character density levels × 16 variants each. */
const BLOCK_LEVELS = [" ", "·", ":", ";", "░", "▒", "▓", "█", "▀", "▄", "▌", "▐", "▖", "▗", "▘", "▙"];
const BLOCK_DITHER: readonly string[][] = Array.from({ length: 16 }, (_, level) =>
  Array.from({ length: 16 }, (_, v) => {
    const offset = (v % 3) - 1; // -1, 0, +1 variation around the level
    const idx = (level + offset + 16) % 16;
    return BLOCK_LEVELS[idx]!;
  })
);

// ── Module-level animation state ────────────────────────────────────────────

const targetPulsePhase = { value: 0 };
const survivorCascade = { value: 0 };
let targetPulseTimeline: Timeline | null = null;
let survivorFlashTimeline: Timeline | null = null;
let survivorFlashActive = false;
let lastTimelineUpdate = 0;

// ── Drone trail state ───────────────────────────────────────────────────────

interface TrailPoint {
  x: number;
  y: number;
  droneId: string;
  age: number;
}

const droneTrailBuffer: TrailPoint[] = [];
const lastDronePositions = new Map<string, { x: number; y: number }>();

// ── Helpers ─────────────────────────────────────────────────────────────────

function lerpColor(hex1: string, hex2: string, t: number): string {
  const r1 = parseInt(hex1.slice(1, 3), 16);
  const g1 = parseInt(hex1.slice(3, 5), 16);
  const b1 = parseInt(hex1.slice(5, 7), 16);
  const r2 = parseInt(hex2.slice(1, 3), 16);
  const g2 = parseInt(hex2.slice(3, 5), 16);
  const b2 = parseInt(hex2.slice(5, 7), 16);
  const r = Math.round(r1 + (r2 - r1) * t);
  const g = Math.round(g1 + (g2 - g1) * t);
  const b = Math.round(b1 + (b2 - b1) * t);
  return `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${b.toString(16).padStart(2, "0")}`;
}

function dimColor(hex: string, factor: number): string {
  const r = Math.min(255, Math.floor(parseInt(hex.slice(1, 3), 16) * factor));
  const g = Math.min(255, Math.floor(parseInt(hex.slice(3, 5), 16) * factor));
  const b = Math.min(255, Math.floor(parseInt(hex.slice(5, 7), 16) * factor));
  return `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${b.toString(16).padStart(2, "0")}`;
}

function getTrailIntensity(x: number, y: number): number {
  for (const trail of droneTrailBuffer) {
    if (trail.x === x && trail.y === y) {
      if (trail.age === 1) return 1.0;
      if (trail.age === 2) return 0.66;
      if (trail.age === 3) return 0.33;
    }
  }
  return 0;
}

function initTargetPulseTimeline(): void {
  if (targetPulseTimeline) return;
  targetPulseTimeline = new Timeline({
    duration: 2000,
    loop: true,
    autoplay: true,
  });
  targetPulseTimeline.add(
    targetPulsePhase,
    {
      value: 1,
      duration: 2000,
      ease: "inOutSine",
      onUpdate: (anim) => {
        targetPulsePhase.value = anim.targets[0]!.value;
      },
    }
  );
  engine.register(targetPulseTimeline);
}

function initSurvivorFlashTimeline(): void {
  if (survivorFlashTimeline) return;
  survivorFlashTimeline = new Timeline({
    duration: 3000,
    loop: false,
    autoplay: false,
  });
  survivorFlashTimeline.add(
    survivorCascade,
    {
      value: 1,
      duration: 3000,
      ease: "outElastic",
      onUpdate: (anim) => {
        survivorCascade.value = anim.targets[0]!.value;
      },
    }
  );
  engine.register(survivorFlashTimeline);
}

// ── Public API ──────────────────────────────────────────────────────────────

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

export function buildDroneIndex(state: MonitorState): Map<string, NormalizedDrone> {
  return new Map<string, NormalizedDrone>(state.drones.map((drone) => [`${drone.x},${drone.y}`, drone]));
}

function gridSize(state: MonitorState): number {
  const explicit = typeof state.gridSize === "number" ? state.gridSize : 0;
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

/** Returns a unique glyph based on entropy decimals, certainty decimals, and a cell seed. */
export function ditherGlyph(entropy: number, certainty: number, seed: number): string {
  const level = Math.min(15, Math.floor(entropy * 16));
  const variant = Math.abs(Math.floor((seed * 31 + certainty * 1000) % 16));
  return BRAILLE_DITHER[level]![variant]!;
}

function blockDitherGlyph(entropy: number, certainty: number, seed: number): string {
  const level = Math.min(15, Math.floor(entropy * 16));
  const variant = Math.abs(Math.floor((seed * 31 + certainty * 1000) % 16));
  return BLOCK_DITHER[level]![variant]!;
}

export function updateDroneTrails(state: MonitorState): void {
  for (const trail of droneTrailBuffer) {
    trail.age += 1;
  }
  const valid = droneTrailBuffer.filter((t) => t.age <= DRONE_TRAIL_FRAMES);
  droneTrailBuffer.length = 0;
  droneTrailBuffer.push(...valid);

  for (const drone of state.drones) {
    const prev = lastDronePositions.get(drone.id);
    if (prev && (prev.x !== drone.x || prev.y !== drone.y)) {
      droneTrailBuffer.push({ x: prev.x, y: prev.y, droneId: drone.id, age: 1 });
    }
    lastDronePositions.set(drone.id, { x: drone.x, y: drone.y });
  }
}

export function updateAnimationTimelines(nowMs: number): void {
  initTargetPulseTimeline();
  initSurvivorFlashTimeline();

  const delta = lastTimelineUpdate > 0 ? nowMs - lastTimelineUpdate : 16;
  lastTimelineUpdate = nowMs;

  if (delta > 0 && delta < 1000) {
    targetPulseTimeline?.update(delta);
    survivorFlashTimeline?.update(delta);
  }
}

export function checkSurvivorFlash(survivorFound: boolean): void {
  initSurvivorFlashTimeline();
  if (survivorFound && !survivorFlashActive) {
    survivorFlashActive = true;
    survivorFlashTimeline?.restart();
    survivorFlashTimeline?.play();
  } else if (!survivorFound) {
    survivorFlashActive = false;
  }
}

export function buildAxisRow(size: number = GRID_SIZE_FALLBACK, cellWidth: number = 2): StyledText {
  const labels = Array.from({ length: size }, (_, x) => String(x).padStart(2, "0").padEnd(cellWidth, " "));
  return t`${withFg(PANEL_THEME.textMuted)(withDim(`   ${labels.join("")}`))}`;
}

export function buildLegend(compact = false): StyledText {
  const high = ditherGlyph(0.9, 0.5, 0);
  const medium = ditherGlyph(0.6, 0.5, 1);
  const low = ditherGlyph(0.3, 0.5, 2);
  if (compact) {
    return t`${withFg(PANEL_THEME.textMuted)(withDim("risk"))} ${withFg(HEATMAP_THEME.bandColors.high)(withBold(`${high}${high}`))} ${withFg(HEATMAP_THEME.bandColors.medium)(withBold(`${medium}${medium}`))} ${withFg(HEATMAP_THEME.bandColors.low)(withBold(`${low}${low}`))} ${withFg(PANEL_THEME.textMuted)(withDim("clear"))} ${withFg(PANEL_THEME.textSecondary)("◎ tgt · D")}`;
  }
  return t`${withFg(PANEL_THEME.textMuted)(withDim("risk"))} ${withFg(HEATMAP_THEME.bandColors.high)(withBold(`${high}${high}`))} ${withFg(HEATMAP_THEME.bandColors.medium)(withBold(`${medium}${medium}`))} ${withFg(HEATMAP_THEME.bandColors.low)(withBold(`${low}${low}`))} ${withFg(PANEL_THEME.textMuted)(withDim("clear"))} ${withFg(PANEL_THEME.textSecondary)("◎ target")} ${withFg(PANEL_THEME.textMuted)("·")} ${withFg(PANEL_THEME.textSecondary)("· reserved")} ${withFg(PANEL_THEME.textMuted)("·")} ${withFg(PANEL_THEME.textSecondary)("D drone")} ${withFg(PANEL_THEME.textMuted)("·")} ${withFg(PANEL_THEME.textSecondary)("◇ focus")}`;
}

export function renderHeatmapRow(args: {
  y: number;
  state: MonitorState;
  flashTarget: boolean;
  focusedCell?: { x: number; y: number } | null;
  cellWidth?: number;
  focusedPanel?: boolean;
  droneIndex?: Map<string, NormalizedDrone>;
}): StyledText {
  const { y, state, flashTarget, focusedCell = null, focusedPanel = false } = args;
  const cellWidth = args.cellWidth ?? 2;
  const drones = args.droneIndex ?? buildDroneIndex(state);
  const size = gridSize(state);
  const chunks: TextChunk[] = [withFg(PANEL_THEME.textMuted)(withDim(`${String(y).padStart(2, "0")} `))];

  checkSurvivorFlash(state.survivorFound);

  for (let x = 0; x < size; x += 1) {
    const drone = drones.get(`${x},${y}`);
    const cell = state.grid[y]?.[x];
    const entropyValue = gridCellEntropy(cell);
    const owner = Number(cell?.owner ?? -1);
    const isTarget = state.target.x === x && state.target.y === y;
    const seed = x * y + x + y;
    const certaintyVal = Number(cell?.certainty ?? 0.5);
    const fillGlyph = cellWidth >= 2
      ? ditherGlyph(entropyValue, certaintyVal, seed)
      : blockDitherGlyph(entropyValue, certaintyVal, seed);

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
      const pulsePhase = targetPulsePhase.value;
      fg = lerpColor(HEATMAP_THEME.targetBorder, "#ffffff", pulsePhase);
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

    const trailIntensity = getTrailIntensity(x, y);
    if (trailIntensity > 0 && !drone) {
      const trailDrone = droneTrailBuffer.find((t) => t.x === x && t.y === y);
      if (trailDrone) {
        const token = droneToken(trailDrone.droneId);
        bg = dimColor(token.color, trailIntensity);
      }
    }

    const cascade = survivorCascade.value;
    if (cascade > 0 && state.survivorFound && !isTarget && !drone) {
      const maxDist = size;
      const dist = Math.max(Math.abs(x - state.target.x), Math.abs(y - state.target.y));
      const threshold = cascade * maxDist;
      if (dist <= threshold) {
        const glowIntensity = 1 - dist / Math.max(1, threshold);
        bg = lerpColor(bg, HEATMAP_THEME.survivorFlashBackground, glowIntensity * 0.5);
      }
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
