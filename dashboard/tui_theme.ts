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
  ThemeAccentToken,
  ThemeLabeledToken,
  TuiThemeSpec,
} from "./tui_types.ts";

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
  heatmapHigh: "#111111",
  heatmapMedium: "#888888",
  heatmapLegendLow: "#eeeeee",
  pulseSuccess: "#22c55e",
  backgroundFocus: "#1e293b",
  textActive: "#38bdf8",
  borderActive: "#bae6fd",
  textLight: "#e2e8f0",
  backgroundHighlight: "#1d4ed8",
  backgroundMutedBlue: "#0f1b33",
  backgroundSuccessDim: "#0b2a1b",
  backgroundWarningDim: "#2b1f0d",
  backgroundDangerDim: "#3b0d14",
  backgroundNeutral: "#111827",
} as const;

export const DRONE_ACCENT_COLORS = [
  "#378ADD",
  "#1D9E75",
  "#BA7517",
  "#D85A30",
  "#D4537E",
] as const;


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
      track: { label: "TRACK 2", fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundPrimary, border: HTML_V2_CSS_VARS.borderStrong },
      mode: { label: "TERMINAL OPS", fg: HTML_V2_CSS_VARS.textSecondary, bg: HTML_V2_CSS_VARS.backgroundSecondary, border: HTML_V2_CSS_VARS.borderTertiary },
      mesh: { label: "MESH", fg: HTML_V2_CSS_VARS.textInfo, bg: HTML_V2_CSS_VARS.backgroundInfo, border: HTML_V2_CSS_VARS.textInfo },
      source: { label: "SOURCE", fg: HTML_V2_CSS_VARS.textSecondary, bg: HTML_V2_CSS_VARS.backgroundSecondary, border: HTML_V2_CSS_VARS.borderTertiary },
      status: { label: "LIVE", fg: HTML_V2_CSS_VARS.textSuccess, bg: HTML_V2_CSS_VARS.backgroundSuccess, border: HTML_V2_CSS_VARS.backgroundSuccess },
    },
    modeChips: {
      synthetic: { label: "synthetic demo", fg: HTML_V2_CSS_VARS.textSecondary, bg: HTML_V2_CSS_VARS.backgroundPrimary, border: HTML_V2_CSS_VARS.borderTertiary },
      live: { label: "live snapshot", fg: HTML_V2_CSS_VARS.textInfo, bg: HTML_V2_CSS_VARS.backgroundInfo, border: HTML_V2_CSS_VARS.textInfo },
      replay: { label: "replay snapshot", fg: HTML_V2_CSS_VARS.textWarning, bg: HTML_V2_CSS_VARS.backgroundWarning, border: HTML_V2_CSS_VARS.borderWarning },
    },
    meshChips: {
      real: { label: "mesh=real", fg: HTML_V2_CSS_VARS.textInfo, bg: HTML_V2_CSS_VARS.backgroundInfo, border: HTML_V2_CSS_VARS.textInfo },
      stub: { label: "mesh=stub", fg: HTML_V2_CSS_VARS.textMuted, bg: HTML_V2_CSS_VARS.backgroundSecondary, border: HTML_V2_CSS_VARS.borderTertiary },
    },
  },
  stats: {
    cards: {
      coverage: { label: "coverage", shortLabel: "cov", fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundPrimary, border: HTML_V2_CSS_VARS.borderTertiary, accent: HTML_V2_CSS_VARS.textSuccess },
      entropy: { label: "avg entropy", shortLabel: "H", fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundPrimary, border: HTML_V2_CSS_VARS.borderTertiary, accent: HTML_V2_CSS_VARS.textWarning },
      auctions: { label: "auctions", shortLabel: "auc", fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundPrimary, border: HTML_V2_CSS_VARS.borderTertiary, accent: HTML_V2_CSS_VARS.textWarning },
      dropouts: { label: "dropouts", shortLabel: "drop", fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundPrimary, border: HTML_V2_CSS_VARS.borderTertiary, accent: HTML_V2_CSS_VARS.textDanger },
      bft: { label: "bft rounds", shortLabel: "bft", fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundPrimary, border: HTML_V2_CSS_VARS.borderTertiary, accent: HTML_V2_CSS_VARS.textInfo },
      elapsed: { label: "elapsed", shortLabel: "t", fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundPrimary, border: HTML_V2_CSS_VARS.borderTertiary, accent: HTML_V2_CSS_VARS.textSecondary },
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
      high: { label: "high H", glyph: "  ", fg: HTML_V2_CSS_VARS.textInverse, bg: HTML_V2_CSS_VARS.heatmapHigh, border: HTML_V2_CSS_VARS.heatmapHigh },
      medium: { label: "medium H", glyph: "  ", fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.heatmapMedium, border: HTML_V2_CSS_VARS.heatmapMedium },
      low: { label: "low H", glyph: "  ", fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.heatmapLegendLow, border: HTML_V2_CSS_VARS.heatmapLegendLow },
      target: { label: "target", glyph: "◎", fg: HTML_V2_CSS_VARS.textWarning, bg: HTML_V2_CSS_VARS.backgroundPrimary, border: HTML_V2_CSS_VARS.borderWarning },
      drone: { label: "drone", glyph: "D1", fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundPrimary, border: HTML_V2_CSS_VARS.borderStrong },
      survivor: { label: "survivor", glyph: "✦", fg: HTML_V2_CSS_VARS.textSuccess, bg: HTML_V2_CSS_VARS.backgroundSuccess, border: HTML_V2_CSS_VARS.backgroundSuccess },
    },
    thresholds: {
      high: 0.8,
      medium: 0.5,
    },
    bandColors: {
      high: HTML_V2_CSS_VARS.heatmapHigh,
      medium: HTML_V2_CSS_VARS.heatmapMedium,
      low: HTML_V2_CSS_VARS.textMuted,
    },
    droneForeground: HTML_V2_CSS_VARS.textInverse,
    emptyForeground: HTML_V2_CSS_VARS.textPrimary,
    targetBorder: HTML_V2_CSS_VARS.borderWarning,
    survivorFlashBackground: HTML_V2_CSS_VARS.pulseSuccess,
    focus: {
      idle: { fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundPrimary, border: HTML_V2_CSS_VARS.borderTertiary, accent: HTML_V2_CSS_VARS.textMuted },
      hover: { fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundInfo, border: HTML_V2_CSS_VARS.textInfo, accent: HTML_V2_CSS_VARS.textInfo },
      focused: { fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundFocus, border: HTML_V2_CSS_VARS.textWarning, accent: HTML_V2_CSS_VARS.textWarning },
      active: { fg: HTML_V2_CSS_VARS.textInverse, bg: HTML_V2_CSS_VARS.textActive, border: HTML_V2_CSS_VARS.borderActive, accent: HTML_V2_CSS_VARS.textPrimary },
    },
    cursorGlyph: "◆",
  },
  roster: {
    statusChips: {
      searching: { label: "scan", fg: HTML_V2_CSS_VARS.textSuccess, bg: HTML_V2_CSS_VARS.backgroundSuccess, border: HTML_V2_CSS_VARS.backgroundSuccess },
      transit: { label: "move", fg: HTML_V2_CSS_VARS.textInfo, bg: HTML_V2_CSS_VARS.backgroundInfo, border: HTML_V2_CSS_VARS.backgroundInfo },
      offline: { label: "off", fg: HTML_V2_CSS_VARS.textDanger, bg: HTML_V2_CSS_VARS.backgroundDanger, border: HTML_V2_CSS_VARS.borderDanger },
      idle: { label: "idle", fg: HTML_V2_CSS_VARS.textMuted, bg: HTML_V2_CSS_VARS.backgroundPrimary, border: HTML_V2_CSS_VARS.borderTertiary },
    },
    sourceLabels: {
      synthetic: { label: "synthetic demo", fg: HTML_V2_CSS_VARS.textSecondary, bg: HTML_V2_CSS_VARS.backgroundSecondary, border: HTML_V2_CSS_VARS.borderTertiary },
      live: { label: "live source", fg: HTML_V2_CSS_VARS.textInfo, bg: HTML_V2_CSS_VARS.backgroundInfo, border: HTML_V2_CSS_VARS.textInfo },
      replay: { label: "replay source", fg: HTML_V2_CSS_VARS.textWarning, bg: HTML_V2_CSS_VARS.backgroundWarning, border: HTML_V2_CSS_VARS.borderWarning },
    },
    focus: {
      idle: { fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundSecondary, border: HTML_V2_CSS_VARS.borderTertiary, accent: HTML_V2_CSS_VARS.textMuted },
      hover: { fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundInfo, border: HTML_V2_CSS_VARS.textInfo, accent: HTML_V2_CSS_VARS.textInfo },
      focused: { fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundFocus, border: HTML_V2_CSS_VARS.textWarning, accent: HTML_V2_CSS_VARS.textWarning },
      active: { fg: HTML_V2_CSS_VARS.textInverse, bg: HTML_V2_CSS_VARS.textActive, border: HTML_V2_CSS_VARS.borderActive, accent: HTML_V2_CSS_VARS.textPrimary },
    },
  },
  events: {
    tones: {
      bft: { label: "SYNC", fg: HTML_V2_CSS_VARS.textWarning, bg: HTML_V2_CSS_VARS.backgroundWarning, border: HTML_V2_CSS_VARS.borderWarning, accent: HTML_V2_CSS_VARS.textWarning },
      claim: { label: "TASK", fg: HTML_V2_CSS_VARS.textInfo, bg: HTML_V2_CSS_VARS.backgroundInfo, border: HTML_V2_CSS_VARS.textInfo, accent: HTML_V2_CSS_VARS.textInfo },
      found: { label: "FOUND", fg: HTML_V2_CSS_VARS.textSuccess, bg: HTML_V2_CSS_VARS.backgroundSuccess, border: HTML_V2_CSS_VARS.backgroundSuccess, accent: HTML_V2_CSS_VARS.textSuccess },
      stale: { label: "RISK", fg: HTML_V2_CSS_VARS.textDanger, bg: HTML_V2_CSS_VARS.backgroundDanger, border: HTML_V2_CSS_VARS.borderDanger, accent: HTML_V2_CSS_VARS.textDanger },
      mesh: { label: "LINK", fg: HTML_V2_CSS_VARS.textSecondary, bg: HTML_V2_CSS_VARS.backgroundSecondary, border: HTML_V2_CSS_VARS.borderTertiary, accent: HTML_V2_CSS_VARS.textSecondary },
      info: { label: "NOTE", fg: HTML_V2_CSS_VARS.textSecondary, bg: HTML_V2_CSS_VARS.backgroundSecondary, border: HTML_V2_CSS_VARS.borderTertiary, accent: HTML_V2_CSS_VARS.textMuted },
    },
    focus: {
      idle: { fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundSecondary, border: HTML_V2_CSS_VARS.borderTertiary, accent: HTML_V2_CSS_VARS.textMuted },
      hover: { fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundInfo, border: HTML_V2_CSS_VARS.textInfo, accent: HTML_V2_CSS_VARS.textInfo },
      focused: { fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundFocus, border: HTML_V2_CSS_VARS.textWarning, accent: HTML_V2_CSS_VARS.textWarning },
      active: { fg: HTML_V2_CSS_VARS.textInverse, bg: HTML_V2_CSS_VARS.textActive, border: HTML_V2_CSS_VARS.borderActive, accent: HTML_V2_CSS_VARS.textPrimary },
    },
  },
  footer: {
    statuses: {
      booting: { label: "initialising vertex p2p mesh...", fg: HTML_V2_CSS_VARS.textInfo, bg: HTML_V2_CSS_VARS.shellPanel, border: HTML_V2_CSS_VARS.borderSecondary, pulse: HTML_V2_CSS_VARS.textInfo },
      live: { label: "mesh healthy · streaming live updates", fg: HTML_V2_CSS_VARS.textSuccess, bg: HTML_V2_CSS_VARS.shellPanel, border: HTML_V2_CSS_VARS.borderSecondary, pulse: HTML_V2_CSS_VARS.pulseSuccess },
      stale: { label: "stale data · holding last valid snapshot", fg: HTML_V2_CSS_VARS.textWarning, bg: HTML_V2_CSS_VARS.shellPanel, border: HTML_V2_CSS_VARS.borderWarning, pulse: HTML_V2_CSS_VARS.textWarning },
      stub: { label: "in-process mesh bus initialised", fg: HTML_V2_CSS_VARS.textMuted, bg: HTML_V2_CSS_VARS.shellPanel, border: HTML_V2_CSS_VARS.borderSecondary, pulse: HTML_V2_CSS_VARS.textMuted },
      replay: { label: "replay mode · file-backed snapshot", fg: HTML_V2_CSS_VARS.textInfo, bg: HTML_V2_CSS_VARS.shellPanel, border: HTML_V2_CSS_VARS.borderSecondary, pulse: HTML_V2_CSS_VARS.textInfo },
    },
  },
  focus: {
    panels: {
      heatmap: { fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundPrimary, border: HTML_V2_CSS_VARS.textInfo, accent: HTML_V2_CSS_VARS.textActive },
      roster: { fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundPrimary, border: HTML_V2_CSS_VARS.textSuccess, accent: HTML_V2_CSS_VARS.pulseSuccess },
      events: { fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundPrimary, border: HTML_V2_CSS_VARS.textWarning, accent: HTML_V2_CSS_VARS.borderWarning },
      footer: { fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.shellPanel, border: HTML_V2_CSS_VARS.borderSecondary, accent: HTML_V2_CSS_VARS.textInfo },
      header: { fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.shellPanel, border: HTML_V2_CSS_VARS.borderStrong, accent: HTML_V2_CSS_VARS.textInfo },
    },
    cells: {
      idle: { fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundPrimary, border: HTML_V2_CSS_VARS.borderTertiary, accent: HTML_V2_CSS_VARS.textMuted },
      hover: { fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundInfo, border: HTML_V2_CSS_VARS.textInfo, accent: HTML_V2_CSS_VARS.textInfo },
      focused: { fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundFocus, border: HTML_V2_CSS_VARS.textWarning, accent: HTML_V2_CSS_VARS.textWarning },
      active: { fg: HTML_V2_CSS_VARS.textInverse, bg: HTML_V2_CSS_VARS.textActive, border: HTML_V2_CSS_VARS.borderActive, accent: HTML_V2_CSS_VARS.textPrimary },
    },
  },
  interaction: {
    chips: {
      navigate: { label: "arrows", fg: HTML_V2_CSS_VARS.textInfo, bg: HTML_V2_CSS_VARS.backgroundInfo, border: HTML_V2_CSS_VARS.textInfo },
      switch: { label: "tab", fg: HTML_V2_CSS_VARS.textWarning, bg: HTML_V2_CSS_VARS.backgroundWarning, border: HTML_V2_CSS_VARS.borderWarning },
      select: { label: "enter", fg: HTML_V2_CSS_VARS.textSuccess, bg: HTML_V2_CSS_VARS.backgroundSuccess, border: HTML_V2_CSS_VARS.textSuccess },
      click: { label: "click", fg: HTML_V2_CSS_VARS.textPrimary, bg: HTML_V2_CSS_VARS.backgroundMuted, border: HTML_V2_CSS_VARS.borderStrong },
      quit: { label: "q", fg: HTML_V2_CSS_VARS.textDanger, bg: HTML_V2_CSS_VARS.backgroundDanger, border: HTML_V2_CSS_VARS.borderDanger },
    },
  },
} as const;

export const SOURCE_MODE_LABELS: Record<SourceMode, string> = {
  synthetic: TUI_THEME.roster.sourceLabels.synthetic.label,
  live: TUI_THEME.roster.sourceLabels.live.label,
  replay: TUI_THEME.roster.sourceLabels.replay.label,
};

export const MODE_CHIP_THEME: Record<SourceMode, ThemeLabeledToken> = TUI_THEME.header.modeChips;

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

export const STAT_CARD_THEME: Record<StatCardKey, ThemeAccentToken> = TUI_THEME.stats.cards;

export const STATUS_CHIP_THEME: Record<DisplayDroneStatus, ThemeLabeledToken> = TUI_THEME.roster.statusChips;

export const SOURCE_LABEL_THEME: Record<SourceMode, ThemeLabeledToken> = TUI_THEME.roster.sourceLabels;

export const EVENT_TONE_THEME: Record<EventTone, ThemeAccentToken> = TUI_THEME.events.tones;

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
  border: HTML_V2_CSS_VARS.borderSecondary,
  textPrimary: HTML_V2_CSS_VARS.textInverse,
  textSecondary: HTML_V2_CSS_VARS.textLight,
  textMuted: HTML_V2_CSS_VARS.textSecondary,
  shellText: HTML_V2_CSS_VARS.textInverse,
} as const;

export const FOOTER_STATUS_THEME: Record<FooterStatusKind, ThemeLabeledToken & { readonly pulse: HexColor }> = TUI_THEME.footer.statuses;

export const FOOTER_THEME = {
  pulse: FOOTER_STATUS_THEME.live.pulse,
  text: HTML_V2_CSS_VARS.textMuted,
  liveText: FOOTER_STATUS_THEME.live.label,
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

export const STAT_THRESHOLDS = {
  coverage: { good: 60, warn: 30 },
  entropy: { high: 0.7, warn: 0.45 },
  auctions: { active: 1 },
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

export function isStatusDisplayKey(key: string): key is keyof typeof STATUS_DISPLAY_MAP {
  return key in STATUS_DISPLAY_MAP;
}

export function isEventToneKey(key: string): key is keyof typeof EVENT_TONE_MAP {
  return key in EVENT_TONE_MAP;
}

export function isSourceMode(value: string): value is SourceMode {
  return value in MODE_CHIP_THEME;
}

export function isDisplayDroneStatus(value: string): value is DisplayDroneStatus {
  return value in STATUS_CHIP_THEME;
}

export function statusColor(status: string): string {
  const key = isStatusDisplayKey(status) ? STATUS_DISPLAY_MAP[status] : "idle";
  return STATUS_CHIP_THEME[key].fg;
}

export function eventColor(type: string): string {
  const tone = isEventToneKey(type) ? EVENT_TONE_MAP[type] : "info";
  return EVENT_TONE_THEME[tone].fg;
}

export function entropyColor(value: number): string {
  return HEATMAP_THEME.bandColors[heatmapBandForEntropy(value)];
}

export const FOCUS_THEME = TUI_THEME.focus;
export const INTERACTION_THEME: Record<InteractionChipKind, ThemeLabeledToken> = TUI_THEME.interaction.chips;
