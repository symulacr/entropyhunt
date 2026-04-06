import type { CellSnapshot, Snapshot } from "./tui_types.ts";
import { TUI_LAYOUT } from "./tui_theme.ts";
import { entropy as cellEntropy } from "./tui_heatmap.ts";
import { mapStatus } from "./tui_sidebar.ts";

export type DroneView = {
  id: string;
  x: number;
  y: number;
  tx: number | null;
  ty: number | null;
  claimedCell: { x: number; y: number } | null;
  status: string;
  offline: boolean;
  entropy: number;
  searchedCells: number;
};

export type EventView = { t: number; type: string; msg: string };
export type FocusPanel = "heatmap" | "roster" | "events";
export type DisplayMode = "overview" | "detail" | "map" | "config" | "graphs";

export type MonitorUiState = {
  displayMode: DisplayMode;
  focusedPanel: FocusPanel;
  cursorX: number;
  cursorY: number;
  selectedDrone: number;
  selectedEvent: number;
};

export type ViewState = {
  elapsed: number;
  coverage: number;
  avgEntropy: number;
  auctions: number;
  dropouts: number;
  bftRounds: number;
  meshMode: "real" | "stub";
  sourceLabel: string;
  sourceUrl: string;
  target: { x: number; y: number };
  droneCount: number;
  tickSeconds: number;
  tickDelaySeconds: number;
  requestedDroneCount: number;
  controlUrl: string;
  controlCapabilities: Record<string, string>;
  grid: CellSnapshot[][];
  gridSize: number;
  drones: DroneView[];
  events: EventView[];
  survivorFound: boolean;
  staleData: boolean;
  hiddenDroneCount: number;
  hiddenEventCount: number;
  gridTruncated: boolean;
};

export type LayoutMetrics = {
  compactLayout: boolean;
  eventRowCount: number;
  heatmapWidth: number;
  rosterHeight: number;
  headerHeight: number;
  statsHeight: number;
  footerHeight: number;
  cellWidth: number;
};

export function speedControlCapability(controlCapabilities: Record<string, string>): string {
  if (controlCapabilities.tick_delay_seconds === "live") return "live";
  if (controlCapabilities.tick_seconds === "live") return "live";
  return controlCapabilities.tick_delay_seconds ?? controlCapabilities.tick_seconds ?? "unavailable";
}

export const MAX_GRID_DIMENSION = TUI_LAYOUT.gridSize;
export const MAX_GRID_RENDER_ROWS = MAX_GRID_DIMENSION * 12;
export const MAX_EVENT_LINES = TUI_LAYOUT.maxEvents;
export const MAX_DRONE_LINES = TUI_LAYOUT.maxDronesVisible;

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

export function formatDuration(totalSeconds: number): string {
  const seconds = Math.max(0, Math.round(totalSeconds));
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  if (minutes <= 0) return `${seconds}s`;
  return `${minutes}m ${String(remainder).padStart(2, "0")}s`;
}

export function computeActiveCellWidth(availableWidth: number, gridSize: number, fallback: number): number {
  const usableWidth = Math.max(4, availableWidth - 3);
  return clamp(Math.floor(usableWidth / Math.max(1, gridSize)), Math.max(2, fallback), 20);
}

export function computeHeatmapRowRepeat(
  gridSize: number,
  displayMode: DisplayMode,
  compactLayout: boolean,
  availableRows?: number,
): number {
  if (displayMode === "map") {
    if (availableRows && availableRows > 0) {
      return Math.max(1, Math.floor(availableRows / Math.max(1, gridSize)));
    }
    return gridSize <= 6 ? 3 : gridSize <= 8 ? 2 : 1;
  }
  return compactLayout ? 1 : (gridSize <= 8 ? 2 : 1);
}

function normalizeTarget(value: unknown): { x: number; y: number } {
  if (Array.isArray(value)) return { x: Number(value[0] ?? 7), y: Number(value[1] ?? 3) };
  if (value && typeof value === "object") {
    const maybe = value as { x?: unknown; y?: unknown };
    return { x: Number(maybe.x ?? 7), y: Number(maybe.y ?? 3) };
  }
  return { x: 7, y: 3 };
}

function normalizeClaimedCell(value: unknown): { x: number; y: number } | null {
  if (!Array.isArray(value)) return null;
  const x = Number(value[0]);
  const y = Number(value[1]);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return { x, y };
}

function sourceLabelFor(url: string, snapshot: Snapshot): string {
  const mode = snapshot.config?.source_mode;
  if (mode === "synthetic" || mode === "live" || mode === "replay") return mode;
  if (snapshot.summary?.mesh === "local" || snapshot.summary?.mesh === "foxmq") return "live";
  if (!url.startsWith("http")) return "replay";
  return "live";
}

function toGrid(snapshot: Snapshot): CellSnapshot[][] {
  const raw = Array.isArray(snapshot.grid) ? snapshot.grid : [];
  return raw.map((row) => Array.isArray(row) ? [...row] : []);
}

export function computeLayoutMetrics(terminalWidth: number, terminalHeight: number): LayoutMetrics {
  const compactLayout = terminalWidth <= 110 || terminalHeight <= 30;
  return {
    compactLayout,
    eventRowCount: compactLayout ? 2 : 10,
    heatmapWidth: compactLayout ? Math.max(terminalWidth - 4, 32) : Math.max(78, Math.floor(terminalWidth * 0.6)),
    rosterHeight: compactLayout ? 5 : 11,
    headerHeight: compactLayout ? 3 : 4,
    statsHeight: compactLayout ? 1 : 4,
    footerHeight: compactLayout ? 1 : 2,
    cellWidth: terminalWidth >= 150 ? 6 : terminalWidth >= 120 ? 4 : terminalWidth >= 76 ? 3 : 2,
  };
}

export function normalizeSnapshot(snapshot: Snapshot, sourceUrl: string, staleData: boolean): ViewState {
  const summary = (snapshot.summary ?? {}) as Record<string, unknown>;
  const stats = (snapshot.stats ?? summary) as Record<string, unknown>;
  const config = (snapshot.config ?? {}) as Record<string, unknown>;
  const rawGrid = toGrid(snapshot);
  const target = normalizeTarget(config.target ?? summary.target);
  const sourceLabel = sourceLabelFor(sourceUrl, snapshot);
  const rawMesh = String(config.mesh_mode ?? summary.mesh ?? config.transport ?? "real").toLowerCase();
  const meshMode = rawMesh === "stub" || rawMesh === "local" ? "stub" : "real";
  const rawGridSize = config.grid_size ?? config.grid ?? rawGrid.length ?? MAX_GRID_DIMENSION;
  const gridSize = clamp(Number(rawGridSize), 1, MAX_GRID_DIMENSION);
  const gridTruncated =
    Number(rawGridSize) > MAX_GRID_DIMENSION ||
    rawGrid.length > MAX_GRID_DIMENSION ||
    rawGrid.some((row) => row.length > MAX_GRID_DIMENSION);
  const grid = rawGrid
    .slice(0, MAX_GRID_DIMENSION)
    .map((row) => row.slice(0, MAX_GRID_DIMENSION));
  const dronesRaw = (summary.drones as Array<Record<string, unknown>> | undefined) ?? (snapshot.drones ?? []);
  const hiddenDroneCount = Math.max(0, dronesRaw.length - MAX_DRONE_LINES);

  const drones = dronesRaw.slice(0, MAX_DRONE_LINES).map((drone) => {
    const position = Array.isArray(drone.position) ? drone.position : [drone.x ?? 0, drone.y ?? 0];
    const targetPos = Array.isArray(drone.target) ? drone.target : [drone.tx ?? null, drone.ty ?? null];
    const claimedCell = normalizeClaimedCell(drone.claimed_cell);
    const x = Number(position[0] ?? 0);
    const y = Number(position[1] ?? 0);
    const certainty = Number(grid[y]?.[x]?.certainty ?? 0.5);
    const entropy = Number(grid[y]?.[x]?.entropy ?? cellEntropy(certainty));
    const offline = Boolean(drone.stale || drone.reachable === false || drone.alive === false);
    return {
      id: String(drone.id ?? "drone"),
      x,
      y,
      tx: targetPos[0] == null ? null : Number(targetPos[0]),
      ty: targetPos[1] == null ? null : Number(targetPos[1]),
      claimedCell,
      status: mapStatus(typeof drone.status === "string" ? drone.status : undefined, offline),
      offline,
      entropy,
      searchedCells: Number(drone.searched_cells ?? 0),
    } satisfies DroneView;
  });

  const rawEvents = Array.isArray(snapshot.events) ? snapshot.events : [];
  const hiddenEventCount = Math.max(0, rawEvents.length - MAX_EVENT_LINES);
  const events = rawEvents
    .slice(-MAX_EVENT_LINES)
    .reverse()
    .map((event) => ({
      t: Number(event?.t ?? 0),
      type: String(event?.type ?? "info"),
      msg: String(event?.msg ?? event?.message ?? ""),
    }));

  drones.forEach((drone, index) => {
    const claimedCell = drone.claimedCell;
    if (!claimedCell) return;
    if (claimedCell.y < 0 || claimedCell.y >= grid.length) return;
    if (claimedCell.x < 0 || claimedCell.x >= (grid[claimedCell.y]?.length ?? 0)) return;
    const cell = grid[claimedCell.y]?.[claimedCell.x];
    if (!cell) return;
    if (typeof cell.owner !== "number" || cell.owner < 0) {
      grid[claimedCell.y]![claimedCell.x] = { ...cell, owner: index };
    }
  });

  return {
    elapsed: Number(stats.duration_elapsed ?? summary.duration_elapsed ?? stats.elapsed ?? snapshot.t ?? 0),
    coverage: clamp(Number(stats.coverage ?? summary.coverage ?? 0) * 100, 0, 100),
    avgEntropy: Number(stats.average_entropy ?? summary.average_entropy ?? stats.avg_entropy ?? summary.avg_entropy ?? 0),
    auctions: Number(stats.auctions ?? summary.auctions ?? 0),
    dropouts: Number(stats.dropouts ?? summary.dropouts ?? 0),
    bftRounds: Number(stats.bft_rounds ?? summary.bft_rounds ?? 0),
    meshMode,
    sourceLabel,
    sourceUrl,
    target,
    droneCount: Number(config.drone_count ?? summary.peer_count ?? drones.length),
    tickSeconds: Number(config.tick_seconds ?? summary.tick_seconds ?? 1),
    tickDelaySeconds: Number(config.tick_delay_seconds ?? 0.1),
    requestedDroneCount: Number(config.requested_drone_count ?? config.drone_count ?? summary.peer_count ?? drones.length),
    controlUrl: typeof config.control_url === "string" ? config.control_url : "",
    controlCapabilities:
      config.control_capabilities && typeof config.control_capabilities === "object"
        ? Object.fromEntries(
            Object.entries(config.control_capabilities).flatMap(([key, value]) =>
              typeof value === "string" ? [[key, value]] : [],
            ),
          )
        : {},
    grid,
    gridSize,
    drones,
    events,
    survivorFound: Boolean(summary.survivor_found ?? snapshot.survivor_found),
    staleData,
    hiddenDroneCount,
    hiddenEventCount,
    gridTruncated,
  };
}

export function hitTestHeatmapCell(mouseX: number, rowX: number, cellWidth: number, gridSize: number): number {
  const localX = Math.max(0, mouseX - rowX - 3);
  return clamp(Math.floor(localX / Math.max(1, cellWidth)), 0, Math.max(0, gridSize - 1));
}

export function logicalHeatmapRowForRenderIndex(renderIndex: number, rowRepeat: number, gridSize: number): number {
  return clamp(Math.floor(renderIndex / Math.max(1, rowRepeat)), 0, Math.max(0, gridSize - 1));
}

export function advanceDisplayMode(mode: DisplayMode, reverse = false): DisplayMode {
  const order: DisplayMode[] = ["overview", "detail", "map", "config", "graphs"];
  const current = order.indexOf(mode);
  return order[(current + (reverse ? -1 : 1) + order.length) % order.length]!;
}

export function advanceUiState(
  ui: MonitorUiState,
  state: Pick<ViewState, "gridSize" | "drones" | "events">,
  keyName: string,
): MonitorUiState {
  const next = { ...ui };
  const clampDrone = (value: number) => clamp(value, 0, Math.max(0, state.drones.length - 1));
  const clampEvent = (value: number) => clamp(value, 0, Math.max(0, state.events.length - 1));
  if (next.focusedPanel === "heatmap") {
    if (keyName === "left") next.cursorX = clamp(next.cursorX - 1, 0, state.gridSize - 1);
    else if (keyName === "right") next.cursorX = clamp(next.cursorX + 1, 0, state.gridSize - 1);
    else if (keyName === "up") next.cursorY = clamp(next.cursorY - 1, 0, state.gridSize - 1);
    else if (keyName === "down") next.cursorY = clamp(next.cursorY + 1, 0, state.gridSize - 1);
  } else if (next.focusedPanel === "roster") {
    if (keyName === "up") next.selectedDrone = clampDrone(next.selectedDrone - 1);
    else if (keyName === "down") next.selectedDrone = clampDrone(next.selectedDrone + 1);
    else if (keyName === "left") next.focusedPanel = "heatmap";
    else if (keyName === "right") next.focusedPanel = "events";
  } else {
    if (keyName === "up") next.selectedEvent = clampEvent(next.selectedEvent - 1);
    else if (keyName === "down") next.selectedEvent = clampEvent(next.selectedEvent + 1);
    else if (keyName === "left") next.focusedPanel = "roster";
    else if (keyName === "right") next.focusedPanel = "heatmap";
  }
  return next;
}
