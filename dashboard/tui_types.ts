export type HexColor = `#${string}`;

export type MeshMode = "real" | "stub";
export type SourceMode = "synthetic" | "live" | "replay";
export type HeatmapBand = "high" | "medium" | "low";

export type HeaderTagKind = "track" | "mode" | "mesh" | "source" | "status";
export type StatCardKey = "coverage" | "entropy" | "auctions" | "dropouts" | "bft" | "elapsed";
export type StatTone = "good" | "warn" | "bad" | "neutral";
export type LegendItemKey = HeatmapBand | "target" | "drone" | "survivor";
export type FooterStatusKind = "booting" | "live" | "stale" | "stub" | "replay";
export type EventTone = "bft" | "claim" | "found" | "stale" | "mesh" | "info";
export type FocusTargetKind = "heatmap" | "roster" | "events" | "footer" | "header";
export type SelectionTone = "idle" | "hover" | "focused" | "active";
export type InteractionChipKind = "navigate" | "switch" | "select" | "click" | "quit";

export type GridTuple = readonly [number, number];
export interface GridPoint {
  readonly x: number;
  readonly y: number;
}

export type RawDroneStatus =
  | "idle"
  | "computing"
  | "claiming"
  | "claim_won"
  | "claim_lost"
  | "transiting"
  | "transit"
  | "searching"
  | "stale"
  | "offline"
  | "complete";

export type DisplayDroneStatus = "idle" | "transit" | "searching" | "offline";

export type KnownEventType =
  | "auction"
  | "bft"
  | "bft_result"
  | "bft_vote"
  | "claim"
  | "claim_lost"
  | "claim_won"
  | "failure"
  | "found"
  | "heartbeat"
  | "heartbeat_timeout"
  | "info"
  | "mesh"
  | "packet_loss"
  | "reclaim"
  | "release"
  | "stale"
  | "survivor"
  | "survivor_found"
  | "waiting"
  | "zone_priority_reclaim";

export interface SnapshotGridCell {
  readonly certainty?: number;
  readonly entropy?: number;
  readonly owner?: number;
  readonly visited?: boolean;
  readonly completed?: boolean;
  readonly x?: number;
  readonly y?: number;
}

export interface SnapshotDrone {
  readonly id: string;
  readonly alive?: boolean;
  readonly reachable?: boolean;
  readonly stale?: boolean;
  readonly status?: RawDroneStatus;
  readonly searched_cells?: number;
  readonly position?: GridTuple | number[];
  readonly target?: GridTuple | number[] | null;
  readonly claimed_cell?: GridTuple | number[] | null;
  readonly x?: number;
  readonly y?: number;
  readonly tx?: number | null;
  readonly ty?: number | null;
  readonly battery?: number;
  readonly role?: string;
}

export interface SnapshotEvent {
  readonly t?: number | string;
  readonly type?: KnownEventType;
  readonly msg?: string;
  readonly message?: string;
  readonly contest_id?: string;
  readonly drone_id?: string;
  readonly peer_id?: string;
  readonly cell?: GridTuple | number[];
}

export interface SnapshotStats {
  readonly coverage?: number;
  readonly coverage_current?: number;
  readonly coverage_completed?: number;
  readonly avg_entropy?: number;
  readonly average_entropy?: number;
  readonly auctions?: number;
  readonly dropouts?: number;
  readonly bft_rounds?: number;
  readonly elapsed?: number;
  readonly duration_elapsed?: number;
  readonly mesh_peers?: readonly string[];
  readonly pending_claims?: number;
  readonly consensus_rounds?: number;
}

export interface SnapshotSummary extends SnapshotStats {
  readonly peer_id?: string;
  readonly mesh?: string;
  readonly target?: GridTuple | number[];
  readonly drones?: readonly SnapshotDrone[];
  readonly survivor_found?: boolean;
  readonly mesh_messages?: number;
  readonly survivor_receipts?: number;
}

export interface SnapshotConfig {
  readonly target?: GridTuple | GridPoint;
  readonly mesh_mode?: MeshMode;
  readonly transport?: string;
  readonly grid_size?: number;
  readonly drone_count?: number;
  readonly tick_seconds?: number;
  readonly tick_delay_seconds?: number;
  readonly requested_drone_count?: number;
  readonly control_url?: string;
  readonly control_capabilities?: Record<string, string>;
  readonly source_mode?: SourceMode;
}

export interface RuntimeSnapshot {
  readonly t?: number;
  readonly summary?: SnapshotSummary;
  readonly stats?: SnapshotStats;
  readonly config?: SnapshotConfig;
  readonly grid?: readonly (readonly SnapshotGridCell[])[];
  readonly drones?: readonly SnapshotDrone[];
  readonly events?: readonly SnapshotEvent[];
  readonly survivor_found?: boolean;
}

export interface ThemeLabeledToken {
  readonly label: string;
  readonly fg: HexColor;
  readonly bg: HexColor;
  readonly border: HexColor;
}

export interface ThemeAccentToken extends ThemeLabeledToken {
  readonly shortLabel?: string;
  readonly accent: HexColor;
}

export interface ThemeSelectionToken {
  readonly fg: HexColor;
  readonly bg: HexColor;
  readonly border: HexColor;
  readonly accent: HexColor;
}

export interface ThemePalette {
  readonly backgroundPrimary: HexColor;
  readonly backgroundSecondary: HexColor;
  readonly backgroundMuted: HexColor;
  readonly backgroundSuccess: HexColor;
  readonly backgroundInfo: HexColor;
  readonly backgroundWarning: HexColor;
  readonly backgroundDanger: HexColor;
  readonly borderStrong: HexColor;
  readonly borderSecondary: HexColor;
  readonly borderTertiary: HexColor;
  readonly borderWarning: HexColor;
  readonly borderDanger: HexColor;
  readonly textPrimary: HexColor;
  readonly textSecondary: HexColor;
  readonly textMuted: HexColor;
  readonly textInverse: HexColor;
  readonly textSuccess: HexColor;
  readonly textInfo: HexColor;
  readonly textWarning: HexColor;
  readonly textDanger: HexColor;
  readonly shellBackground: HexColor;
  readonly shellPanel: HexColor;
}

export interface ThemeHeaderTokens {
  readonly title: string;
  readonly subtitle: string;
  readonly tags: Readonly<Record<HeaderTagKind, ThemeLabeledToken>>;
  readonly modeChips: Readonly<Record<SourceMode, ThemeLabeledToken>>;
  readonly meshChips: Readonly<Record<MeshMode, ThemeLabeledToken>>;
}

export interface ThemeStatTokens {
  readonly cards: Readonly<Record<StatCardKey, ThemeAccentToken>>;
  readonly tones: Readonly<Record<StatTone, HexColor>>;
}

export interface ThemeHeatmapTokens {
  readonly legend: Readonly<Record<LegendItemKey, ThemeLabeledToken & { readonly glyph: string }>>;
  readonly thresholds: Readonly<{ high: number; medium: number }>;
  readonly bandColors: Readonly<Record<HeatmapBand, HexColor>>;
  readonly droneForeground: HexColor;
  readonly emptyForeground: HexColor;
  readonly targetBorder: HexColor;
  readonly survivorFlashBackground: HexColor;
  readonly focus: Readonly<Record<SelectionTone, ThemeSelectionToken>>;
  readonly cursorGlyph: string;
}

export interface ThemeRosterTokens {
  readonly statusChips: Readonly<Record<DisplayDroneStatus, ThemeLabeledToken>>;
  readonly sourceLabels: Readonly<Record<SourceMode, ThemeLabeledToken>>;
  readonly focus: Readonly<Record<SelectionTone, ThemeSelectionToken>>;
}

export interface ThemeEventTokens {
  readonly tones: Readonly<Record<EventTone, ThemeAccentToken>>;
  readonly focus: Readonly<Record<SelectionTone, ThemeSelectionToken>>;
}

export interface ThemeFooterTokens {
  readonly statuses: Readonly<Record<FooterStatusKind, ThemeLabeledToken & { readonly pulse: HexColor }>>;
}

export interface ThemeFocusTokens {
  readonly panels: Readonly<Record<FocusTargetKind, ThemeSelectionToken>>;
  readonly cells: Readonly<Record<SelectionTone, ThemeSelectionToken>>;
}

export interface ThemeInteractionTokens {
  readonly chips: Readonly<Record<InteractionChipKind, ThemeLabeledToken>>;
}

export interface TuiThemeSpec {
  readonly palette: ThemePalette;
  readonly header: ThemeHeaderTokens;
  readonly stats: ThemeStatTokens;
  readonly heatmap: ThemeHeatmapTokens;
  readonly roster: ThemeRosterTokens;
  readonly events: ThemeEventTokens;
  readonly footer: ThemeFooterTokens;
  readonly focus: ThemeFocusTokens;
  readonly interaction: ThemeInteractionTokens;
}

export interface MonitorStatLine {
  readonly elapsed: number;
  readonly coverage: number;
  readonly avgEntropy: number;
  readonly auctions: number;
  readonly dropouts: number;
  readonly bftRounds: number;
  readonly meshMode: MeshMode;
  readonly staleData: boolean;
}

export interface MonitorGridCell {
  readonly x: number;
  readonly y: number;
  readonly certainty: number;
  readonly entropy: number;
  readonly owner: number;
  readonly band: HeatmapBand;
  readonly isTarget: boolean;
}

export interface MonitorDroneState {
  readonly id: string;
  readonly current: GridPoint;
  readonly target: GridPoint | null;
  readonly rawStatus: RawDroneStatus;
  readonly displayStatus: DisplayDroneStatus;
  readonly offline: boolean;
  readonly entropy: number;
  readonly accentIndex: number;
  readonly searchedCells?: number;
}

export interface MonitorEventState {
  readonly t: number;
  readonly type: KnownEventType;
  readonly msg: string;
  readonly tone: EventTone;
}

export interface MonitorViewState {
  readonly sourceMode: SourceMode;
  readonly stats: MonitorStatLine;
  readonly target: GridPoint;
  readonly grid: readonly (readonly MonitorGridCell[])[];
  readonly drones: readonly MonitorDroneState[];
  readonly events: readonly MonitorEventState[];
  readonly survivorFound: boolean;
  readonly footerMessage: string;
}

export interface WaitingViewState {
  readonly sourceMode: SourceMode;
  readonly sourceUrl: string;
  readonly spinnerFrame: string;
  readonly staleData: boolean;
}

export type CellSnapshot = SnapshotGridCell;
export type Snapshot = RuntimeSnapshot;
export type NormalizedDrone = {
  id: string;
  x: number;
  y: number;
  tx: number | null;
  ty: number | null;
  status: string;
  offline: boolean;
  entropy: number;
  searchedCells: number;
};
export type NormalizedEvent = { t: number; type: string; msg: string };
export type MonitorState = {
  elapsed: number;
  coverage: number;
  avgEntropy: number;
  auctions: number;
  dropouts: number;
  bftRounds: number;
  meshMode: MeshMode;
  target: GridPoint;
  grid: CellSnapshot[][];
  gridSize?: number;
  drones: NormalizedDrone[];
  events: NormalizedEvent[];
  survivorFound: boolean;
  staleData: boolean;
};

export function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function isSnapshot(obj: unknown): obj is Snapshot {
  if (!obj || typeof obj !== "object") return false;
  const record = obj as Record<string, unknown>;
  if (record.t !== undefined && typeof record.t !== "number") return false;
  if (record.summary !== undefined && (!record.summary || typeof record.summary !== "object")) return false;
  if (record.config !== undefined && (!record.config || typeof record.config !== "object")) return false;
  if (record.events !== undefined && !Array.isArray(record.events)) return false;
  if (record.survivor_found !== undefined && typeof record.survivor_found !== "boolean") return false;
  return Array.isArray(record.grid) && Array.isArray(record.drones) && typeof record.stats === "object" && record.stats !== null;
}
