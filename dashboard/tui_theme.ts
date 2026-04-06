import type {
  DisplayDroneStatus,
  EventTone,
  FooterStatusKind,
  FocusTargetKind,
  HeatmapBand,
  InteractionChipKind,
  HexColor,
  MeshMode,
  SelectionTone,
  SourceMode,
  StatCardKey,
  ThemeChipToken,
  ThemeEventToneToken,
  ThemeFooterStatusToken,
  ThemeLegendToken,
  ThemeSourceLabelToken,
  ThemeStatCardToken,
  TuiThemeSpec,
} from "./tui_types.ts";

/**
 * Shared OpenTUI theme constants derived from entropy_hunt_v2.html.
 *
 * The HTML reference uses a light operator surface nested inside a dark shell:
 * crisp header chips, compact stat cards, a monochrome entropy legend, semantic
 * roster chips, and a footer/status strip with live-state pulse cues. This file
 * centralizes those decisions so the OpenTUI monitor stays aligned with the
 * shipped browser surface instead of hand-tuning colors inline.
 */

export const HTML_V2_CSS_VARS = {
  backgroundPrimary: "#0f172a",
  backgroundSecondary: "#0b1220",
  backgroundMuted: "#1f2937",
  backgroundSuccess: "#052e16",
  backgroundInfo: "#172554",
  backgroundWarning: "#451a03",
  backgroundDanger: "#450a0a",
  borderStrong: "#94a3b8",
  borderSecondary: "#475569",
  borderTertiary: "#334155",
  borderWarning: "#f59e0b",
  borderDanger: "#ef4444",
  textPrimary: "#f8fafc",
  textSecondary: "#cbd5e1",
  textMuted: "#94a3b8",
  textInverse: "#f8fafc",
  textSuccess: "#4ade80",
  textInfo: "#60a5fa",
  textWarning: "#fbbf24",
  textDanger: "#f87171",
  shellBackground: "#020617",
  shellPanel: "#08111f",
} as const;

export const DRONE_ACCENT_COLORS = [
  "#378ADD",
  "#1D9E75",
  "#BA7517",
  "#D85A30",
  "#D4537E",
] as const;

const makeChip = (label: string, fg: HexColor, bg: HexColor, border: HexColor): ThemeChipToken => ({
  label,
  fg,
  bg,
  border,
});

const makeStatCard = (
  label: string,
  shortLabel: string,
  fg: HexColor,
  bg: HexColor,
  border: HexColor,
  accent: HexColor,
): ThemeStatCardToken => ({
  label,
  shortLabel,
  fg,
  bg,
  border,
  accent,
});

const makeLegendToken = (label: string, glyph: string, fg: HexColor, bg: HexColor, border: HexColor): ThemeLegendToken => ({
  label,
  glyph,
  fg,
  bg,
  border,
});

const makeEventTone = (
  label: string,
  fg: HexColor,
  bg: HexColor,
  border: HexColor,
  accent: HexColor,
): ThemeEventToneToken => ({
  label,
  fg,
  bg,
  border,
  accent,
});

const makeFooterStatus = (
  label: string,
  fg: HexColor,
  bg: HexColor,
  border: HexColor,
  pulse: HexColor,
): ThemeFooterStatusToken => ({
  label,
  fg,
  bg,
  border,
  pulse,
});

const makeSourceLabel = (label: string, fg: HexColor, bg: HexColor, border: HexColor): ThemeSourceLabelToken => ({
  label,
  fg,
  bg,
  border,
});

export const TUI_LAYOUT = {
  title: "entropy hunt",
  tag: "track 2 · search & rescue",
  gridSize: 10,
  heatmapCellChars: 2,
  heatmapBoxWidth: 56,
  maxEvents: 12,
  maxDronesVisible: 5,
  pollIntervalMs: 400,
  waitingFps: 12,
  targetFlashMs: 250,
} as const;

export const TUI_THEME: TuiThemeSpec = {
  palette: HTML_V2_CSS_VARS,
  header: {
    title: TUI_LAYOUT.title,
    subtitle: TUI_LAYOUT.tag,
    tags: {
      track: makeChip("TRACK 2", HTML_V2_CSS_VARS.textPrimary, HTML_V2_CSS_VARS.backgroundPrimary, HTML_V2_CSS_VARS.borderStrong),
      mode: makeChip("TERMINAL OPS", HTML_V2_CSS_VARS.textSecondary, HTML_V2_CSS_VARS.backgroundSecondary, HTML_V2_CSS_VARS.borderTertiary),
      mesh: makeChip("MESH", HTML_V2_CSS_VARS.textInfo, HTML_V2_CSS_VARS.backgroundInfo, HTML_V2_CSS_VARS.textInfo),
      source: makeChip("SOURCE", HTML_V2_CSS_VARS.textSecondary, HTML_V2_CSS_VARS.backgroundSecondary, HTML_V2_CSS_VARS.borderTertiary),
      status: makeChip("LIVE", HTML_V2_CSS_VARS.textSuccess, HTML_V2_CSS_VARS.backgroundSuccess, HTML_V2_CSS_VARS.backgroundSuccess),
    },
    modeChips: {
      synthetic: makeChip("synthetic demo", HTML_V2_CSS_VARS.textSecondary, HTML_V2_CSS_VARS.backgroundPrimary, HTML_V2_CSS_VARS.borderTertiary),
      live: makeChip("live snapshot", HTML_V2_CSS_VARS.textInfo, HTML_V2_CSS_VARS.backgroundInfo, HTML_V2_CSS_VARS.textInfo),
      replay: makeChip("replay snapshot", HTML_V2_CSS_VARS.textWarning, HTML_V2_CSS_VARS.backgroundWarning, HTML_V2_CSS_VARS.borderWarning),
    },
    meshChips: {
      real: makeChip("mesh=real", HTML_V2_CSS_VARS.textInfo, HTML_V2_CSS_VARS.backgroundInfo, HTML_V2_CSS_VARS.textInfo),
      stub: makeChip("mesh=stub", HTML_V2_CSS_VARS.textMuted, HTML_V2_CSS_VARS.backgroundSecondary, HTML_V2_CSS_VARS.borderTertiary),
    },
  },
  stats: {
    cards: {
      coverage: makeStatCard("coverage", "cov", HTML_V2_CSS_VARS.textPrimary, HTML_V2_CSS_VARS.backgroundPrimary, HTML_V2_CSS_VARS.borderTertiary, HTML_V2_CSS_VARS.textSuccess),
      entropy: makeStatCard("avg entropy", "H", HTML_V2_CSS_VARS.textPrimary, HTML_V2_CSS_VARS.backgroundPrimary, HTML_V2_CSS_VARS.borderTertiary, HTML_V2_CSS_VARS.textWarning),
      auctions: makeStatCard("auctions", "auc", HTML_V2_CSS_VARS.textPrimary, HTML_V2_CSS_VARS.backgroundPrimary, HTML_V2_CSS_VARS.borderTertiary, HTML_V2_CSS_VARS.textWarning),
      dropouts: makeStatCard("dropouts", "drop", HTML_V2_CSS_VARS.textPrimary, HTML_V2_CSS_VARS.backgroundPrimary, HTML_V2_CSS_VARS.borderTertiary, HTML_V2_CSS_VARS.textDanger),
      bft: makeStatCard("bft rounds", "bft", HTML_V2_CSS_VARS.textPrimary, HTML_V2_CSS_VARS.backgroundPrimary, HTML_V2_CSS_VARS.borderTertiary, HTML_V2_CSS_VARS.textInfo),
      elapsed: makeStatCard("elapsed", "t", HTML_V2_CSS_VARS.textPrimary, HTML_V2_CSS_VARS.backgroundPrimary, HTML_V2_CSS_VARS.borderTertiary, HTML_V2_CSS_VARS.textSecondary),
    },
    tones: {
      good: HTML_V2_CSS_VARS.textSuccess,
      warn: HTML_V2_CSS_VARS.textWarning,
      bad: HTML_V2_CSS_VARS.textDanger,
      neutral: HTML_V2_CSS_VARS.textPrimary,
    },
  },
  heatmap: {
    legend: {
      high: makeLegendToken("high H", "  ", HTML_V2_CSS_VARS.textInverse, "#111111", "#111111"),
      medium: makeLegendToken("medium H", "  ", HTML_V2_CSS_VARS.textPrimary, "#888888", "#888888"),
      low: makeLegendToken("low H", "  ", HTML_V2_CSS_VARS.textPrimary, "#eeeeee", "#eeeeee"),
      target: makeLegendToken("target", "◎", HTML_V2_CSS_VARS.textWarning, HTML_V2_CSS_VARS.backgroundPrimary, HTML_V2_CSS_VARS.borderWarning),
      drone: makeLegendToken("drone", "D1", HTML_V2_CSS_VARS.textPrimary, HTML_V2_CSS_VARS.backgroundPrimary, HTML_V2_CSS_VARS.borderStrong),
      survivor: makeLegendToken("survivor", "✦", HTML_V2_CSS_VARS.textSuccess, HTML_V2_CSS_VARS.backgroundSuccess, HTML_V2_CSS_VARS.backgroundSuccess),
    },
    thresholds: {
      high: 0.8,
      medium: 0.5,
    },
    bandColors: {
      high: "#111111",
      medium: "#888888",
      low: "#94a3b8",
    },
    droneForeground: HTML_V2_CSS_VARS.textInverse,
    emptyForeground: HTML_V2_CSS_VARS.textPrimary,
    targetBorder: HTML_V2_CSS_VARS.borderWarning,
    survivorFlashBackground: "#22c55e",
    focus: {
      idle: { fg: HTML_V2_CSS_VARS.textPrimary, bg: "#0f172a", border: HTML_V2_CSS_VARS.borderTertiary, accent: HTML_V2_CSS_VARS.textMuted },
      hover: { fg: HTML_V2_CSS_VARS.textPrimary, bg: "#172554", border: "#60a5fa", accent: "#60a5fa" },
      focused: { fg: HTML_V2_CSS_VARS.textPrimary, bg: "#1e293b", border: "#fbbf24", accent: "#fbbf24" },
      active: { fg: HTML_V2_CSS_VARS.textInverse, bg: "#38bdf8", border: "#bae6fd", accent: "#f8fafc" },
    },
    cursorGlyph: "◆",
  },
  roster: {
    statusChips: {
      searching: makeChip("scan", HTML_V2_CSS_VARS.textSuccess, HTML_V2_CSS_VARS.backgroundSuccess, HTML_V2_CSS_VARS.backgroundSuccess),
      transit: makeChip("move", HTML_V2_CSS_VARS.textInfo, HTML_V2_CSS_VARS.backgroundInfo, HTML_V2_CSS_VARS.backgroundInfo),
      offline: makeChip("off", HTML_V2_CSS_VARS.textDanger, HTML_V2_CSS_VARS.backgroundDanger, HTML_V2_CSS_VARS.borderDanger),
      idle: makeChip("idle", HTML_V2_CSS_VARS.textMuted, HTML_V2_CSS_VARS.backgroundPrimary, HTML_V2_CSS_VARS.borderTertiary),
    },
    sourceLabels: {
      synthetic: makeSourceLabel("synthetic demo", HTML_V2_CSS_VARS.textSecondary, HTML_V2_CSS_VARS.backgroundSecondary, HTML_V2_CSS_VARS.borderTertiary),
      live: makeSourceLabel("live source", HTML_V2_CSS_VARS.textInfo, HTML_V2_CSS_VARS.backgroundInfo, HTML_V2_CSS_VARS.textInfo),
      replay: makeSourceLabel("replay source", HTML_V2_CSS_VARS.textWarning, HTML_V2_CSS_VARS.backgroundWarning, HTML_V2_CSS_VARS.borderWarning),
    },
    focus: {
      idle: { fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundSecondary, border: HTML_V2_CSS_VARS.borderTertiary, accent: HTML_V2_CSS_VARS.textMuted },
      hover: { fg: HTML_V2_CSS_VARS.textPrimary, bg: "#172554", border: "#60a5fa", accent: "#60a5fa" },
      focused: { fg: HTML_V2_CSS_VARS.textPrimary, bg: "#1e293b", border: "#fbbf24", accent: "#fbbf24" },
      active: { fg: HTML_V2_CSS_VARS.textInverse, bg: "#38bdf8", border: "#bae6fd", accent: "#f8fafc" },
    },
  },
  events: {
    tones: {
      bft: makeEventTone("SYNC", HTML_V2_CSS_VARS.textWarning, HTML_V2_CSS_VARS.backgroundWarning, HTML_V2_CSS_VARS.borderWarning, HTML_V2_CSS_VARS.textWarning),
      claim: makeEventTone("TASK", HTML_V2_CSS_VARS.textInfo, HTML_V2_CSS_VARS.backgroundInfo, HTML_V2_CSS_VARS.textInfo, HTML_V2_CSS_VARS.textInfo),
      found: makeEventTone("FOUND", HTML_V2_CSS_VARS.textSuccess, HTML_V2_CSS_VARS.backgroundSuccess, HTML_V2_CSS_VARS.backgroundSuccess, HTML_V2_CSS_VARS.textSuccess),
      stale: makeEventTone("RISK", HTML_V2_CSS_VARS.textDanger, HTML_V2_CSS_VARS.backgroundDanger, HTML_V2_CSS_VARS.borderDanger, HTML_V2_CSS_VARS.textDanger),
      mesh: makeEventTone("LINK", HTML_V2_CSS_VARS.textSecondary, HTML_V2_CSS_VARS.backgroundSecondary, HTML_V2_CSS_VARS.borderTertiary, HTML_V2_CSS_VARS.textSecondary),
      info: makeEventTone("NOTE", HTML_V2_CSS_VARS.textSecondary, HTML_V2_CSS_VARS.backgroundSecondary, HTML_V2_CSS_VARS.borderTertiary, HTML_V2_CSS_VARS.textMuted),
    },
    focus: {
      idle: { fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundSecondary, border: HTML_V2_CSS_VARS.borderTertiary, accent: HTML_V2_CSS_VARS.textMuted },
      hover: { fg: HTML_V2_CSS_VARS.textPrimary, bg: "#172554", border: "#60a5fa", accent: "#60a5fa" },
      focused: { fg: HTML_V2_CSS_VARS.textPrimary, bg: "#1e293b", border: "#fbbf24", accent: "#fbbf24" },
      active: { fg: HTML_V2_CSS_VARS.textInverse, bg: "#38bdf8", border: "#bae6fd", accent: "#f8fafc" },
    },
  },
  footer: {
    statuses: {
      booting: makeFooterStatus("initialising vertex p2p mesh...", HTML_V2_CSS_VARS.textInfo, HTML_V2_CSS_VARS.shellPanel, HTML_V2_CSS_VARS.borderSecondary, HTML_V2_CSS_VARS.textInfo),
      live: makeFooterStatus("mesh healthy · streaming live updates", HTML_V2_CSS_VARS.textSuccess, HTML_V2_CSS_VARS.shellPanel, HTML_V2_CSS_VARS.borderSecondary, "#22c55e"),
      stale: makeFooterStatus("stale data · holding last valid snapshot", HTML_V2_CSS_VARS.textWarning, HTML_V2_CSS_VARS.shellPanel, HTML_V2_CSS_VARS.borderWarning, HTML_V2_CSS_VARS.textWarning),
      stub: makeFooterStatus("in-process mesh bus initialised", HTML_V2_CSS_VARS.textMuted, HTML_V2_CSS_VARS.shellPanel, HTML_V2_CSS_VARS.borderSecondary, HTML_V2_CSS_VARS.textMuted),
      replay: makeFooterStatus("replay mode · file-backed snapshot", HTML_V2_CSS_VARS.textInfo, HTML_V2_CSS_VARS.shellPanel, HTML_V2_CSS_VARS.borderSecondary, HTML_V2_CSS_VARS.textInfo),
    },
  },
  focus: {
    panels: {
      heatmap: { fg: HTML_V2_CSS_VARS.textPrimary, bg: "#0f172a", border: "#60a5fa", accent: "#38bdf8" },
      roster: { fg: HTML_V2_CSS_VARS.textPrimary, bg: "#0f172a", border: "#4ade80", accent: "#22c55e" },
      events: { fg: HTML_V2_CSS_VARS.textPrimary, bg: "#0f172a", border: "#fbbf24", accent: "#f59e0b" },
      footer: { fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.shellPanel, border: HTML_V2_CSS_VARS.borderSecondary, accent: HTML_V2_CSS_VARS.textInfo },
      header: { fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.shellPanel, border: HTML_V2_CSS_VARS.borderStrong, accent: HTML_V2_CSS_VARS.textInfo },
    },
    cells: {
      idle: { fg: HTML_V2_CSS_VARS.textPrimary, bg: "#0f172a", border: HTML_V2_CSS_VARS.borderTertiary, accent: HTML_V2_CSS_VARS.textMuted },
      hover: { fg: HTML_V2_CSS_VARS.textPrimary, bg: "#172554", border: "#60a5fa", accent: "#60a5fa" },
      focused: { fg: HTML_V2_CSS_VARS.textPrimary, bg: "#1e293b", border: "#fbbf24", accent: "#fbbf24" },
      active: { fg: HTML_V2_CSS_VARS.textInverse, bg: "#38bdf8", border: "#bae6fd", accent: "#f8fafc" },
    },
  },
  interaction: {
    chips: {
      navigate: makeChip("arrows", HTML_V2_CSS_VARS.textInfo, HTML_V2_CSS_VARS.backgroundInfo, HTML_V2_CSS_VARS.textInfo),
      switch: makeChip("tab", HTML_V2_CSS_VARS.textWarning, HTML_V2_CSS_VARS.backgroundWarning, HTML_V2_CSS_VARS.borderWarning),
      select: makeChip("enter", HTML_V2_CSS_VARS.textSuccess, HTML_V2_CSS_VARS.backgroundSuccess, HTML_V2_CSS_VARS.textSuccess),
      click: makeChip("click", HTML_V2_CSS_VARS.textPrimary, HTML_V2_CSS_VARS.backgroundMuted, HTML_V2_CSS_VARS.borderStrong),
      quit: makeChip("q", HTML_V2_CSS_VARS.textDanger, HTML_V2_CSS_VARS.backgroundDanger, HTML_V2_CSS_VARS.borderDanger),
    },
  },
} as const;

export const SOURCE_MODE_LABELS: Record<SourceMode, string> = Object.fromEntries(
  Object.entries(TUI_THEME.roster.sourceLabels).map(([mode, token]) => [mode, token.label]),
) as Record<SourceMode, string>;

export const MODE_CHIP_THEME: Record<SourceMode, ThemeChipToken> = TUI_THEME.header.modeChips;

export const HEATMAP_THEME = {
  legendHighLabel: TUI_THEME.heatmap.legend.high.label,
  legendLowLabel: TUI_THEME.heatmap.legend.low.label,
  gradient: [
    TUI_THEME.heatmap.bandColors.high,
    TUI_THEME.heatmap.bandColors.medium,
    TUI_THEME.heatmap.bandColors.low,
  ] as const,
  thresholds: TUI_THEME.heatmap.thresholds,
  bandColors: TUI_THEME.heatmap.bandColors,
  gridOutline: HTML_V2_CSS_VARS.borderStrong,
  targetBorder: TUI_THEME.heatmap.targetBorder,
  survivorFlashBackground: TUI_THEME.heatmap.survivorFlashBackground,
  emptyForeground: TUI_THEME.heatmap.emptyForeground,
  droneForeground: TUI_THEME.heatmap.droneForeground,
  legend: TUI_THEME.heatmap.legend,
} as const;

export const HEADER_THEME = {
  title: TUI_THEME.header.title,
  subtitle: TUI_THEME.header.subtitle,
  tags: TUI_THEME.header.tags,
  modeChips: TUI_THEME.header.modeChips,
  meshChips: TUI_THEME.header.meshChips,
} as const;

export const STAT_CARD_THEME: Record<StatCardKey, ThemeStatCardToken> = TUI_THEME.stats.cards;

export const STATUS_CHIP_THEME: Record<DisplayDroneStatus, ThemeChipToken> = TUI_THEME.roster.statusChips;

export const SOURCE_LABEL_THEME: Record<SourceMode, ThemeSourceLabelToken> = TUI_THEME.roster.sourceLabels;

export const EVENT_TONE_THEME: Record<EventTone, ThemeEventToneToken> = TUI_THEME.events.tones;

export const STAT_THEME = {
  coverage: {
    good: TUI_THEME.stats.tones.good,
    warn: TUI_THEME.stats.tones.warn,
    bad: TUI_THEME.stats.tones.bad,
  },
  entropy: HTML_V2_CSS_VARS.textWarning,
  label: HTML_V2_CSS_VARS.textMuted,
  value: HTML_V2_CSS_VARS.textInverse,
  cards: TUI_THEME.stats.cards,
} as const;

export const PANEL_THEME = {
  appBackground: HTML_V2_CSS_VARS.shellBackground,
  panelBackground: HTML_V2_CSS_VARS.shellPanel,
  shellPanelBackground: HTML_V2_CSS_VARS.shellPanel,
  border: "#475569",
  mutedBorder: "#475569",
  textPrimary: HTML_V2_CSS_VARS.textInverse,
  textSecondary: "#e2e8f0",
  textMuted: "#cbd5e1",
  shellText: HTML_V2_CSS_VARS.textInverse,
} as const;

export const FOOTER_STATUS_THEME: Record<FooterStatusKind, ThemeFooterStatusToken> = TUI_THEME.footer.statuses;

export const FOOTER_THEME = {
  pulse: FOOTER_STATUS_THEME.live.pulse,
  text: HTML_V2_CSS_VARS.textMuted,
  liveText: FOOTER_STATUS_THEME.booting.label,
  stubText: FOOTER_STATUS_THEME.stub.label,
  statuses: FOOTER_STATUS_THEME,
} as const;

export const MESH_MODE_THEME: Record<MeshMode, { readonly label: string; readonly fg: string; readonly bg: string; readonly border: string }> = {
  real: {
    label: TUI_THEME.header.meshChips.real.label,
    fg: TUI_THEME.header.meshChips.real.fg,
    bg: TUI_THEME.header.meshChips.real.bg,
    border: TUI_THEME.header.meshChips.real.border,
  },
  stub: {
    label: TUI_THEME.header.meshChips.stub.label,
    fg: TUI_THEME.header.meshChips.stub.fg,
    bg: TUI_THEME.header.meshChips.stub.bg,
    border: TUI_THEME.header.meshChips.stub.border,
  },
};

// Compatibility exports for the current imperative monitor modules.
export const COLORS = {
  bg: PANEL_THEME.appBackground,
  panelBg: PANEL_THEME.panelBackground,
  border: PANEL_THEME.border,
  text: PANEL_THEME.shellText,
  dim: PANEL_THEME.textMuted,
  success: HTML_V2_CSS_VARS.textSuccess,
  warning: HTML_V2_CSS_VARS.textWarning,
  danger: HTML_V2_CSS_VARS.textDanger,
  info: HTML_V2_CSS_VARS.textInfo,
  accent1: DRONE_ACCENT_COLORS[0],
  accent2: DRONE_ACCENT_COLORS[1],
  accent3: DRONE_ACCENT_COLORS[2],
  accent4: DRONE_ACCENT_COLORS[3],
  accent5: DRONE_ACCENT_COLORS[4],
  entropyHigh: HEATMAP_THEME.bandColors.high,
  entropyMid: HEATMAP_THEME.bandColors.medium,
  entropyLow: HEATMAP_THEME.bandColors.low,
  target: HEATMAP_THEME.targetBorder,
  targetAlt: HEATMAP_THEME.survivorFlashBackground,
  headerBg: PANEL_THEME.shellPanelBackground,
  shellText: PANEL_THEME.shellText,
} as const;

export const LAYOUT = {
  heatmapWidth: TUI_LAYOUT.heatmapBoxWidth,
  rosterHeight: 12,
  gap: 1,
  maxEvents: TUI_LAYOUT.maxEvents,
  gridSize: TUI_LAYOUT.gridSize,
  cellWidth: 3,
} as const;

export const STATUS_DISPLAY_MAP = {
  transiting: "transit",
  claiming: "transit",
  claim_won: "searching",
  claim_lost: "transit",
  stale: "offline",
  offline: "offline",
  idle: "idle",
  searching: "searching",
  transit: "transit",
} as const satisfies Record<string, DisplayDroneStatus>;

export const EVENT_TONE_MAP = {
  auction: "bft",
  bft: "bft",
  bft_result: "bft",
  bft_vote: "bft",
  claim: "claim",
  claim_lost: "claim",
  claim_won: "claim",
  failure: "stale",
  found: "found",
  heartbeat: "mesh",
  heartbeat_timeout: "stale",
  info: "info",
  mesh: "mesh",
  packet_loss: "mesh",
  reclaim: "claim",
  release: "claim",
  stale: "stale",
  survivor: "found",
  survivor_found: "found",
  waiting: "info",
  zone_priority_reclaim: "claim",
} as const satisfies Record<string, EventTone>;

export function heatmapBandForEntropy(entropy: number): HeatmapBand {
  if (entropy > HEATMAP_THEME.thresholds.high) return "high";
  if (entropy >= HEATMAP_THEME.thresholds.medium) return "medium";
  return "low";
}

export function coverageColorFor(percent: number): string {
  if (percent > 60) return STAT_THEME.coverage.good;
  if (percent >= 30) return STAT_THEME.coverage.warn;
  return STAT_THEME.coverage.bad;
}

export function statusColor(status: string): string {
  const key = (STATUS_DISPLAY_MAP[status as keyof typeof STATUS_DISPLAY_MAP] ?? "idle") as DisplayDroneStatus;
  return STATUS_CHIP_THEME[key].fg;
}

export function eventColor(type: string): string {
  const tone = EVENT_TONE_MAP[type as keyof typeof EVENT_TONE_MAP] ?? "info";
  return EVENT_TONE_THEME[tone].fg;
}

export function entropyColor(value: number): string {
  return HEATMAP_THEME.bandColors[heatmapBandForEntropy(value)];
}

export const FOCUS_THEME = TUI_THEME.focus;
export const INTERACTION_THEME: Record<InteractionChipKind, ThemeChipToken> = TUI_THEME.interaction.chips;
